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
- A static web server for the `frontend` folder, such as VS Code Live Server

Verify the required tools after installing them:

```text
python --version
ffmpeg -version
deno --version
```

### Install FFmpeg and Deno

| Platform | FFmpeg | Deno |
| --- | --- | --- |
| Windows | `winget install Gyan.FFmpeg` | `winget install DenoLand.Deno` |
| macOS | `brew install ffmpeg` | `brew install deno` |
| Linux | Install `ffmpeg` with your distribution package manager | Follow the [official Deno installation instructions](https://docs.deno.com/runtime/getting_started/installation/) |

For example, on Ubuntu or Debian, install FFmpeg with `sudo apt update && sudo apt install ffmpeg`.

## Setup

Clone the repository and change into it:

```bash
git clone https://github.com/vikash-si/youtube_downloader_website.git
cd youtube_downloader_website
```

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` for the current terminal session and activate again. In Command Prompt, use `.venv\Scripts\activate.bat` instead.

## Run locally

### Helper scripts (recommended)

The helper scripts create the virtual environment, install Python dependencies, and manage the FastAPI process. Install FFmpeg and Deno first using the platform instructions above.

**macOS and Linux**

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh setup
./scripts/dev.sh start
./scripts/dev.sh restart
./scripts/dev.sh stop
```

**Windows PowerShell**

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 start
.\scripts\dev.ps1 restart
.\scripts\dev.ps1 stop
```

If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, then run the command again.

### Manual start

Start the API from the activated virtual environment:

**macOS and Linux**

```bash
python backend/main.py
```

**Windows**

```powershell
python backend\main.py
```

Serve the `frontend` folder with VS Code Live Server on port 5500, then open `index.html` in a browser. The frontend is configured to call the API at `http://127.0.0.1:8000`.

## Notes

YouTube can require a Proof-of-Origin token for some media streams. This is an upstream YouTube/yt-dlp restriction and can produce HTTP 403 responses even when metadata is available. Keep yt-dlp current and refer to the [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) when that occurs.

Do not commit browser cookies, downloads, virtual environments, or local yt-dlp source checkouts. They are intentionally excluded by `.gitignore`.
