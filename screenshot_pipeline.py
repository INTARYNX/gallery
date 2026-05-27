import os
import json
import shutil
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import paramiko

NEW_DIR = Path("new")
ARTWORKS_DIR = Path("artworks")
SCREENSHOTS_DIR = Path("screenshots")
FOUND_DIR = Path("found")
JSON_FILE = Path("artworks.json")
WAIT_SECONDS = 10
CLICK_DELAY = 1
VIEWPORT = {"width": 800, "height": 600}

# ── SSH config ──
SSH_HOST = "fournier-digital.ch"
SSH_PORT = 22
SSH_USER = "almalinux"
REMOTE_DIR = "/opt/www/upstride_ch"
SYNC_PATHS = ["index.html", "artworks.json", "intarynx.jpg", "favicon.ico", "artworks", "screenshots"]

# ── Git config ──
GIT_ENABLED = True
GIT_BRANCH = "main"


def id_to_title(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").title()


def load_json():
    if JSON_FILE.exists():
        return json.loads(JSON_FILE.read_text(encoding="utf-8"))
    return []


def save_json(data):
    JSON_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def import_new_files():
    if not NEW_DIR.exists():
        return []
    imported = []
    data = load_json()
    known_ids = {a["id"] for a in data}
    for f in NEW_DIR.glob("*.html"):
        stem = f.stem
        dest = ARTWORKS_DIR / f.name
        if dest.exists():
            print(f"[SKIP NEW] {f.name} already in artworks/")
            f.unlink()
            continue
        shutil.move(str(f), str(dest))
        if stem not in known_ids:
            entry = {"id": stem, "title": id_to_title(stem)}
            data.insert(0, entry)
            known_ids.add(stem)
            imported.append(stem)
            print(f"[NEW] {f.name} -> artworks/ + JSON")
        else:
            print(f"[MOVE] {f.name} -> artworks/ (already in JSON)")
    if imported:
        save_json(data)
    return imported


def move_orphans():
    FOUND_DIR.mkdir(exist_ok=True)
    data = load_json()
    known_ids = {a["id"] for a in data}
    for f in ARTWORKS_DIR.glob("*.html"):
        if f.stem not in known_ids:
            dest = FOUND_DIR / f.name
            shutil.move(str(f), str(dest))
            print(f"[ORPHAN] {f.name} -> found/")


async def capture(playwright, html_file: Path):
    out = SCREENSHOTS_DIR / f"{html_file.stem}.png"
    if out.exists():
        print(f"[SKIP] {html_file.name} (already exists)")
        return
    browser = await playwright.chromium.launch(
        headless=False,
        args=[
            "--use-gl=angle",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--enable-gpu-rasterization",
        ],
    )
    context = await browser.new_context(viewport=VIEWPORT)
    page = await context.new_page()
    await page.goto(html_file.resolve().as_uri())
    await asyncio.sleep(CLICK_DELAY)
    await page.mouse.click(VIEWPORT["width"] / 2, VIEWPORT["height"] / 2)
    await asyncio.sleep(WAIT_SECONDS)
    await page.screenshot(path=str(out), full_page=False)
    await browser.close()
    print(f"[OK] {html_file.name} -> {out}")


# ── SSH sync ──
def remote_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def remote_mkdirs(sftp, path):
    parts = path.replace("\\", "/").strip("/").split("/")
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else f"/{p}"
        if not remote_exists(sftp, cur):
            sftp.mkdir(cur)


def needs_upload(sftp, local: Path, remote: str):
    try:
        rstat = sftp.stat(remote)
        return local.stat().st_size != rstat.st_size or local.stat().st_mtime > rstat.st_mtime
    except FileNotFoundError:
        return True


def sync_path(sftp, local: Path, remote: str):
    if local.is_file():
        if needs_upload(sftp, local, remote):
            remote_mkdirs(sftp, str(Path(remote).parent).replace("\\", "/"))
            sftp.put(str(local), remote)
            print(f"[UP] {local} -> {remote}")
        else:
            print(f"[SKIP] {local} unchanged")
    elif local.is_dir():
        remote_mkdirs(sftp, remote)
        for child in local.iterdir():
            sync_path(sftp, child, f"{remote}/{child.name}")


def sync_to_server():
    print(f"\n=== Syncing to {SSH_USER}@{SSH_HOST}:{REMOTE_DIR} ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, allow_agent=True, look_for_keys=False)
    sftp = client.open_sftp()
    try:
        for p in SYNC_PATHS:
            local = Path(p)
            if not local.exists():
                print(f"[SKIP] {p} does not exist locally")
                continue
            sync_path(sftp, local, f"{REMOTE_DIR}/{p}")
    finally:
        sftp.close()
        client.close()
    print("=== Sync complete ===")


# ── Git sync ──
def git_sync():
    if not GIT_ENABLED:
        return
    print("\n=== Git sync ===")
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if not status.stdout.strip():
            print("[GIT] Nothing to commit")
            return
        subprocess.run(["git", "add", "-A"], check=True)
        msg = f"Update gallery {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push", "origin", GIT_BRANCH], check=True)
        print(f"[GIT] Pushed: {msg}")
    except subprocess.CalledProcessError as e:
        print(f"[GIT ERR] {e}")
    except FileNotFoundError:
        print("[GIT ERR] git not found in PATH")


async def main():
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    ARTWORKS_DIR.mkdir(exist_ok=True)

    print("\n=== Importing new files ===")
    import_new_files()

    print("\n=== Moving orphans ===")
    move_orphans()

    print("\n=== Capturing screenshots ===")
    files = list(ARTWORKS_DIR.glob("*.html"))
    if files:
        async with async_playwright() as p:
            for f in files:
                try:
                    await capture(p, f)
                except Exception as e:
                    print(f"[ERR] {f.name}: {e}")

    sync_to_server()
    git_sync()


if __name__ == "__main__":
    asyncio.run(main())