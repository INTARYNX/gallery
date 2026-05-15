# Intarynx's Gallery

Generative canvas at the edge of algorithms, aesthetics, and not taking itself too seriously.

🌐 Live: [upstride.ch](https://upstride.ch)

## Structure

- `index.html` — gallery frontend
- `artworks.json` — list of canvas (id + title)
- `artworks/` — HTML canvas files
- `screenshots/` — auto-generated previews
- `new/` — drop new HTML files here before running the pipeline
- `screenshot_pipeline.py` — automation script

## Pipeline

The pipeline imports new artworks, captures screenshots, syncs to the server, and pushes to git.

```bash
python -m venv venv
venv\Scripts\activate
pip install playwright paramiko
playwright install chromium
python screenshot_pipeline.py
```

### What it does

1. Moves `.html` files from `new/` to `artworks/` and adds them to `artworks.json`
2. Moves orphaned files (in `artworks/` but not in JSON) to `found/`
3. Takes screenshots of canvas missing in `screenshots/`
4. Syncs files to the production server via SFTP
5. Commits and pushes changes to git

## License

All artworks © Intarynx. All rights reserved.