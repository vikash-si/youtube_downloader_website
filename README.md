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

Serve the `frontend` folder with VS Code Live Server on port 5500, then open `index.html` in a browser. The frontend detects this local-development port and calls the API at port `8000` on the same host.

## Local network hosting

The backend binds to all local interfaces by default. To share the website with devices on the same Wi-Fi or Ethernet network, serve the frontend from the repository root:

```bash
python3 -m http.server 5500 --bind 0.0.0.0 --directory frontend
```

For this Mac's current LAN address (`192.168.1.4`), open the site from another device at:

```text
http://192.168.1.4:5500
```

The frontend automatically sends API requests to `http://192.168.1.4:8000` when it is opened through that address. If macOS Firewall is enabled, allow incoming connections for Python or Terminal. This configuration is for the local network only; do not expose these ports to the public internet through router port forwarding.

## Production deployment with Apache

Use a reverse proxy rather than exposing FastAPI on port `8000`. Serve the `frontend` folder as Apache's document root and proxy `/api/` requests to the local FastAPI process.

```apache
DocumentRoot "/www/wwwroot/example.com/frontend"

ProxyRequests Off
ProxyPreserveHost On
ProxyPass /api/ http://127.0.0.1:8000/api/ connectiontimeout=5 timeout=3600
ProxyPassReverse /api/ http://127.0.0.1:8000/api/

<Directory "/www/wwwroot/example.com/frontend">
    Require all granted
</Directory>
```

Run the backend through a process manager such as Supervisor, with one process because download-job progress is stored in memory:

```text
/usr/bin/env PATH=/usr/local/bin:/usr/bin:/bin /www/wwwroot/example.com/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Use HTTPS for the public site. Keep port `8000` private and allow public access only through Apache on ports `80` and `443`.

### Optional YouTube cookies

YouTube can require an authenticated session for requests from a server IP. If you use a cookies file, export it in Netscape `cookies.txt` format, keep it outside the document root, and pass its location through `YT_DLP_COOKIES`:

```text
YT_DLP_COOKIES=/www/wwwroot/example.com/private/youtube-cookies.txt
```

The application reads this variable when it starts. Restart the process after replacing the file. Cookies are sensitive session credentials: never commit, publish, or share them, and expect YouTube to expire or block them.

## Notes

YouTube can require a Proof-of-Origin token for some media streams. This is an upstream YouTube/yt-dlp restriction and can produce HTTP 403 responses even when metadata is available. Keep yt-dlp current and refer to the [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) when that occurs.

Do not commit browser cookies, downloads, virtual environments, or local yt-dlp source checkouts. They are intentionally excluded by `.gitignore`.
