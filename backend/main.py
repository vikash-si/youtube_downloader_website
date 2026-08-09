import os
import subprocess
import json
import sys
import shutil
import threading
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from typing import Callable, Dict, List, Optional
import tempfile
import re

app = FastAPI(title="YouTube Downloader", version="1.0.0")

# Allow the standalone frontend served by VS Code Live Server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Length", "Content-Disposition"],
)

# Ensure downloads directory exists
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
downloads_dir = os.path.join(project_dir, "downloads")
os.makedirs(downloads_dir, exist_ok=True)

# Use the interpreter that launched FastAPI. This prevents yt-dlp from being
# accidentally run with macOS's legacy /usr/bin/python3 (currently Python 3.9).
YT_DLP_COMMAND = [sys.executable, "-m", "yt_dlp"]
deno_path = shutil.which("deno")
if deno_path:
    YT_DLP_COMMAND += ["--js-runtimes", f"deno:{deno_path}"]

# A Netscape-format YouTube cookies file can be supplied outside the project
# through YT_DLP_COOKIES. Keep it out of the web root and source control.
cookies_path = os.environ.get("YT_DLP_COOKIES")
if cookies_path and os.path.isfile(cookies_path):
    YT_DLP_COMMAND += ["--cookies", cookies_path]

class VideoInfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    quality: Optional[str] = None
    output_format: str = "mp4"

OUTPUT_FORMATS = {"mp4", "mkv", "mp3", "aac"}
MEDIA_TYPES = {
    "mp4": "video/mp4",
    "mkv": "video/x-matroska",
    "mp3": "audio/mpeg",
    "aac": "audio/aac",
}

download_jobs: Dict[str, dict] = {}
download_jobs_lock = threading.Lock()

def validate_youtube_url(url: str) -> bool:
    """Validate if the URL is a YouTube URL"""
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=.*$',
        r'^https?://(www\.)?youtu\.be/.*$'
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    return False

def run_yt_dlp_command(args: List[str]) -> dict:
    """Run yt-dlp command and return JSON output"""
    try:
        result = subprocess.run(
            YT_DLP_COMMAND + args,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp error: {e.stderr}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON parsing error: {str(e)}")

def get_video_info(url: str) -> dict:
    """Get video information using yt-dlp"""
    if not validate_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    # Get video info in JSON format
    info = run_yt_dlp_command(["-J", url])
    
    # Extract relevant information
    title = info.get("title", "Unknown Title")
    thumbnail = info.get("thumbnail", "")
    duration = info.get("duration", 0)
    
    # The download command combines a video-only format with the best M4A
    # audio stream. Include that audio in the displayed estimate.
    audio_formats = [
        fmt for fmt in info.get("formats", [])
        if fmt.get("acodec") not in (None, "none")
        and fmt.get("protocol") not in {"m3u8", "m3u8_native"}
    ]
    preferred_audio_formats = [fmt for fmt in audio_formats if fmt.get("ext") == "m4a"]
    best_audio = max(
        preferred_audio_formats or audio_formats,
        key=get_format_filesize,
        default=None,
    )
    best_audio_size = get_format_filesize(best_audio, duration) if best_audio else 0

    # Process formats
    formats = []
    if "formats" in info:
        for fmt in info["formats"]:
            # The quality picker is for video downloads. Exclude audio-only
            # streams, which otherwise show up as a confusing "Unknown" row.
            if fmt.get("vcodec") in (None, "none"):
                continue

            # Avoid YouTube's HLS playlists (for example, format 95). They can
            # expire or reject individual fragments with HTTP 403, whereas the
            # direct DASH/HTTPS streams are more reliable for server downloads.
            if fmt.get("protocol") in {"m3u8", "m3u8_native"}:
                continue
                
            # Skip formats that are not MP4 compatible or have no ext
            if not fmt.get("ext"):
                continue
                
            # Only include formats that can be merged into MP4
            quality = get_quality_label(fmt)
            if fmt.get("ext") in ["webm", "mp4"] and quality != "Unknown":
                format_info = {
                    "format_id": fmt["format_id"],
                    "quality": quality,
                    "resolution": fmt.get("resolution", "Unknown"),
                    "ext": fmt.get("ext", "unknown"),
                    "filesize": get_format_filesize(fmt, duration) + (
                        best_audio_size if fmt.get("acodec") in (None, "none") else 0
                    )
                }
                formats.append(format_info)
    
    # Remove duplicates and sort by quality
    unique_formats = []
    seen_qualities = set()
    for fmt in sorted(formats, key=lambda x: get_quality_value(x["quality"]), reverse=True):
        if fmt["quality"] not in seen_qualities:
            unique_formats.append(fmt)
            seen_qualities.add(fmt["quality"])
    
    # Keep only top 6 qualities
    unique_formats = unique_formats[:6]
    
    return {
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration,
        "formats": unique_formats
    }

def get_format_filesize(format_info: Optional[dict], duration: Optional[float] = None) -> int:
    """Return the exact size, yt-dlp estimate, or a bitrate-based estimate."""
    if not format_info:
        return 0
    known_size = format_info.get("filesize") or format_info.get("filesize_approx")
    if known_size:
        return known_size

    # YouTube often omits a size for adaptive formats. tbr is kilobits/sec, so
    # it can still provide a useful approximate size for the quality picker.
    bitrate_kbps = format_info.get("tbr")
    if bitrate_kbps and duration:
        return int(float(bitrate_kbps) * 1000 * float(duration) / 8)
    return 0

def get_quality_label(format_info: dict) -> str:
    """Convert format info to quality label"""
    resolution = format_info.get("resolution", "")
    if not resolution or resolution == "Unknown":
        return "Unknown"
    
    # Extract width and height
    res_parts = resolution.split('x')
    if len(res_parts) != 2:
        return "Unknown"
    
    try:
        width = int(res_parts[0])
        if width >= 3840:
            return "2160p"
        elif width >= 2560:
            return "1440p"
        elif width >= 1920:
            return "1080p"
        elif width >= 1280:
            return "720p"
        elif width >= 854:
            return "480p"
        elif width >= 640:
            return "360p"
        else:
            return "Unknown"
    except ValueError:
        return "Unknown"

def get_quality_value(quality: str) -> int:
    """Convert quality label to numeric value for sorting"""
    quality_map = {
        "2160p": 6,
        "1440p": 5,
        "1080p": 4,
        "720p": 3,
        "480p": 2,
        "360p": 1
    }
    return quality_map.get(quality, 0)

@app.get("/api/health")
async def health_check():
    """Check if all required components are available"""
    try:
        # Check yt-dlp
        subprocess.run(YT_DLP_COMMAND + ["--version"], 
                      capture_output=True, check=True)
        
        # Check ffmpeg
        subprocess.run(["ffmpeg", "-version"], 
                      capture_output=True, check=True)
        
        return {
            "status": "healthy",
            "yt_dlp_available": True,
            "ffmpeg_available": True,
            "python_version": sys.version.split()[0]
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {
            "status": "unhealthy",
            "yt_dlp_available": False,
            "ffmpeg_available": False,
            "python_version": sys.version.split()[0]
        }

@app.post("/api/info")
async def get_video_info_endpoint(request: VideoInfoRequest):
    """Get video information"""
    try:
        info = get_video_info(request.url)
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching video info: {str(e)}")

def download_media(
    request: DownloadRequest,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> tuple[str, str, str, str]:
    """Download media and return its path, filename, MIME type, and temp directory."""
    try:
        if not validate_youtube_url(request.url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        if request.output_format not in OUTPUT_FORMATS:
            raise HTTPException(status_code=400, detail="Unsupported output format")
        
        info = run_yt_dlp_command(["-J", request.url])
        selected_format = None
        for fmt in info.get("formats", []):
            if fmt.get("format_id") == request.format_id:
                selected_format = fmt
                break
        
        if not selected_format and request.quality:
            # YouTube may return different format IDs on a subsequent metadata
            # request. Resolve the same displayed quality again, preferring MP4.
            matching_formats = [
                fmt for fmt in info.get("formats", [])
                if fmt.get("vcodec") not in (None, "none")
                and get_quality_label(fmt) == request.quality
                and fmt.get("protocol") not in {"m3u8", "m3u8_native"}
            ]
            selected_format = next(
                (fmt for fmt in matching_formats if fmt.get("ext") == "mp4"),
                matching_formats[0] if matching_formats else None,
            )

        if not selected_format:
            raise HTTPException(status_code=400, detail="Selected quality is no longer available. Please fetch the video details again.")
        
        temp_dir = tempfile.mkdtemp(prefix="youtube-download-")
        output_template = os.path.join(temp_dir, "video.%(ext)s")

        is_audio_download = request.output_format in {"mp3", "aac"}
        has_video = selected_format.get("vcodec") not in (None, "none")
        has_audio = selected_format.get("acodec") not in (None, "none")
        # Video-only formats download video and audio separately. Combine
        # those two raw yt-dlp percentages into one overall progress value.
        download_phase_count = 2 if has_video and not has_audio and not is_audio_download else 1
        format_selector = "bestaudio/best" if is_audio_download else selected_format["format_id"]
        if has_video and not has_audio and not is_audio_download:
            # Quality formats from YouTube are commonly video-only. Pair the
            # selected resolution with the best available audio stream.
            format_selector = f"{selected_format['format_id']}+bestaudio[ext=m4a]/bestaudio"
        
        cmd = [
            *YT_DLP_COMMAND,
            "--no-playlist",
            "--no-part",
            "-f", format_selector,
            "-o", output_template,
            "--print", "after_move:filepath",
            request.url
        ]
        if is_audio_download:
            cmd[3:3] = ["--extract-audio", "--audio-format", request.output_format]
        else:
            cmd[3:3] = [
                "--merge-output-format", request.output_format,
                "--remux-video", request.output_format,
            ]
        output_lines = []
        if progress_callback:
            progress_state = {"phase": 0, "last_raw": 0.0, "last_overall": 0.0}

            def report_progress(raw_progress: float) -> None:
                # A large drop means yt-dlp moved from the video stream to the
                # audio stream. Keep the UI progress monotonic across phases.
                if raw_progress + 5 < progress_state["last_raw"]:
                    progress_state["phase"] += 1
                progress_state["last_raw"] = raw_progress
                phase = min(progress_state["phase"], download_phase_count - 1)
                overall = ((phase + raw_progress / 100) / download_phase_count) * 100
                overall = max(progress_state["last_overall"], min(99, overall))
                progress_state["last_overall"] = overall
                progress_callback(overall)

            # --newline makes each yt-dlp update parseable as it happens.
            cmd[3:3] = [
                # --print (used to obtain the final path) implies --quiet;
                # explicitly re-enable progress output for job updates.
                "--progress",
                "--newline",
                "--progress-template", "download:__PROGRESS__%(progress._percent_str)s",
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in process.stdout or []:
                output_lines.append(line)
                match = re.search(r"__PROGRESS__\s*([0-9]+(?:\.[0-9]+)?)%", line)
                if match:
                    report_progress(float(match.group(1)))
            return_code = process.wait()
            error_output = "".join(output_lines)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_lines = result.stdout.splitlines()
            return_code = result.returncode
            error_output = result.stderr

        if return_code != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Download failed: {error_output}")

        output_paths = [line.strip() for line in output_lines if os.path.isfile(line.strip())]
        downloaded_path = output_paths[-1] if output_paths else ""
        if not os.path.isfile(downloaded_path) or os.path.getsize(downloaded_path) == 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail="yt-dlp did not produce a downloadable media file")

        return (
            downloaded_path,
            f"{info.get('title', 'video')}.{request.output_format}",
            MEDIA_TYPES[request.output_format],
            temp_dir,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

def update_download_job(job_id: str, **values) -> None:
    with download_jobs_lock:
        if job_id in download_jobs:
            download_jobs[job_id].update(values)

def process_download_job(job_id: str, request: DownloadRequest) -> None:
    try:
        update_download_job(job_id, status="downloading", progress=0)
        path, filename, media_type, temp_dir = download_media(
            request,
            lambda progress: update_download_job(job_id, progress=round(progress, 1)),
        )
        update_download_job(
            job_id,
            status="completed",
            progress=100,
            path=path,
            filename=filename,
            media_type=media_type,
            temp_dir=temp_dir,
        )
    except HTTPException as error:
        update_download_job(job_id, status="failed", error=str(error.detail))
    except Exception:
        update_download_job(job_id, status="failed", error="Download failed")

def cleanup_download_job(job_id: str, temp_dir: str) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)
    with download_jobs_lock:
        download_jobs.pop(job_id, None)

@app.post("/api/download/start")
async def start_download(request: DownloadRequest):
    """Start a download job so the client can display yt-dlp's progress."""
    if not validate_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    if request.output_format not in OUTPUT_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported output format")

    job_id = uuid.uuid4().hex
    with download_jobs_lock:
        download_jobs[job_id] = {"status": "preparing", "progress": 0}
    threading.Thread(target=process_download_job, args=(job_id, request), daemon=True).start()
    return {"job_id": job_id}

@app.get("/api/download/{job_id}/status")
async def get_download_status(job_id: str):
    with download_jobs_lock:
        job = download_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Download job not found")
        return {key: job[key] for key in ("status", "progress", "error") if key in job}

@app.get("/api/download/{job_id}/file")
async def get_download_file(job_id: str):
    with download_jobs_lock:
        job = download_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Download job not found")
        if job["status"] == "failed":
            raise HTTPException(status_code=500, detail=job.get("error", "Download failed"))
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Download is not ready")
        path, filename, media_type, temp_dir = (
            job["path"], job["filename"], job["media_type"], job["temp_dir"]
        )

    return FileResponse(
        path=path,
        filename=filename,
        media_type=media_type,
        background=BackgroundTask(cleanup_download_job, job_id, temp_dir),
    )

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    """Backward-compatible single-request download endpoint."""
    path, filename, media_type, temp_dir = download_media(request)
    return FileResponse(
        path=path,
        filename=filename,
        media_type=media_type,
        background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
