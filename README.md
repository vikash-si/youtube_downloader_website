# YouTube Downloader Website

A local FastAPI and vanilla JavaScript web application for retrieving YouTube metadata and downloading video or audio in selected formats.

## Features

- YouTube URL validation and video metadata lookup
- Resolution picker with estimated download sizes
- MP4 and MKV video output, with audio automatically merged when necessary
- MP3 and AAC audio-only output
- Live yt-dlp download progress in the browser
- Responsive quality grid and user-friendly error messages

## Requirements

- Python 3.10 or newer
- FFmpeg available on your `PATH`
- Deno available on your `PATH` (recommended by yt-dlp for current YouTube JavaScript challenges)

## Setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

On macOS with Homebrew, install the media and JavaScript dependencies with:

```bash
brew install ffmpeg deno
```

## Run locally

Start the API:

```bash
.venv/bin/python backend/main.py
```

Serve the `frontend` folder with VS Code Live Server (port 5500), then open `index.html` in the browser. The frontend is configured to call the API at `http://127.0.0.1:8000`.

## Notes

YouTube can require a Proof-of-Origin token for some media streams. This is an upstream YouTube/yt-dlp restriction and can produce HTTP 403 responses even when metadata is available. Keep yt-dlp current and refer to the [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) when that occurs.

Do not commit browser cookies, downloads, virtual environments, or local yt-dlp source checkouts. They are intentionally excluded by `.gitignore`.
