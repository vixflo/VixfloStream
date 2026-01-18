from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
import math
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import time

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from dotenv import load_dotenv


def _user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_PRODUCT_NAME
    return Path.home() / APP_PRODUCT_NAME


def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False

def _project_dir() -> Path:
    # When bundled with PyInstaller (onefile/onedir), assets are extracted to sys._MEIPASS.
    # We keep templates/static in that extracted folder, but write downloads next to the EXE.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[1]


PROJECT_DIR = _project_dir()

# Allow configuration via a local .env file next to the project.
load_dotenv(PROJECT_DIR / ".env")

APP_BUILD = datetime.now(timezone.utc).isoformat(timespec="seconds")

# Branding (shown in UI footer and window titles)
APP_PRODUCT_NAME = "VixfloStream Downloader"
APP_BRAND_NAME = "VixfloTech Software"
APP_VERSION = "0.1.0"

DEFAULT_HTTP_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
}

TEMPLATES_DIR = PROJECT_DIR / "templates"
STATIC_DIR = PROJECT_DIR / "static"
ASSETS_DIR = PROJECT_DIR / "assets"

if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    candidate = exe_dir / "downloads"
    if _ensure_writable_dir(candidate):
        DOWNLOADS_DIR = candidate
    else:
        DOWNLOADS_DIR = _user_data_dir() / "downloads"
else:
    DOWNLOADS_DIR = PROJECT_DIR / "downloads"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

class ForwardedPrefixMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "x-forwarded-prefix") -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next):
        # Handle X-Forwarded-Proto (https from Apache)
        proto = request.headers.get("x-forwarded-proto")
        if proto:
            request.scope["scheme"] = proto

        # Handle X-Forwarded-Host (vixflodev.ro from Apache)
        host = request.headers.get("x-forwarded-host")
        if host:
            # Update server tuple (host, port) - use 443 for https
            port = 443 if request.scope.get("scheme") == "https" else 80
            request.scope["server"] = (host, port)

        # Handle X-Forwarded-Prefix (/VixfloStream)
        prefix = request.headers.get(self._header_name)
        if prefix:
            prefix = prefix.strip()
            if not prefix.startswith("/"):
                prefix = "/" + prefix
            prefix = prefix.rstrip("/")
            request.scope["root_path"] = prefix

            # Some reverse-proxy setups forward the full prefixed path (e.g. /AVEProiect/static/...)
            # instead of stripping it. If that happens, strip it here so routing/static files work.
            path = request.scope.get("path") or ""
            if path == prefix or path.startswith(prefix + "/"):
                new_path = path[len(prefix) :]
                if not new_path:
                    new_path = "/"
                request.scope["path"] = new_path
                request.scope["raw_path"] = new_path.encode("utf-8")
        return await call_next(request)


class BuildHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-AVE-Build"] = APP_BUILD
        response.headers["X-AVE-Frozen"] = "1" if getattr(sys, "frozen", False) else "0"
        return response


app = FastAPI(title=APP_PRODUCT_NAME, version=APP_VERSION)
app.add_middleware(ForwardedPrefixMiddleware)
app.add_middleware(BuildHeaderMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Make branding available everywhere (even if a route forgets to pass it).
templates.env.globals.update(
    app_product_name=APP_PRODUCT_NAME,
    app_brand_name=APP_BRAND_NAME,
    app_version=APP_VERSION,
)


def _template_base_context(request: Request) -> dict[str, object]:
    root_path = request.scope.get("root_path", "") or ""
    return {
        "request": request,
        "root_path": root_path,
        "app_product_name": APP_PRODUCT_NAME,
        "app_brand_name": APP_BRAND_NAME,
        "app_version": APP_VERSION,
    }


DownloadType = Literal["video", "audio"]
AudioFormat = Literal["mp3", "original"]


@dataclass
class Job:
    id: str
    status: Literal["queued", "running", "done", "error"]
    download_type: DownloadType
    audio_format: AudioFormat
    url: str
    filename: str | None = None
    error: str | None = None


@dataclass
class Preview:
    url: str
    title: str | None
    uploader: str | None
    description: str | None
    duration: int | None
    thumbnail: str | None
    webpage_url: str | None
    extractor: str | None
    warning: str | None
    needs_cookies: bool
    _ts: float


_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, Job] = {}
_futures: dict[str, Future[None]] = {}
_preview_cache: dict[str, Preview] = {}
_preview_lock = __import__("threading").Lock()


def _human_duration(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None

    try:
        sec = float(seconds)
    except Exception:
        return None

    if not math.isfinite(sec) or sec < 0:
        return None

    total = int(round(sec))
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _fix_mojibake(text: str | None) -> str | None:
    if not text:
        return text

    # Heuristic: some extractors occasionally return text that looks like UTF-8 bytes
    # decoded as Windows-1252/latin-1 (e.g. "â€™" instead of "’").
    markers = ("â", "Ã", "ð")
    if not any(m in text for m in markers):
        return text

    before = sum(text.count(m) for m in markers)

    candidates: list[str] = []
    for enc in ("cp1252", "latin-1"):
        try:
            candidates.append(text.encode(enc, errors="ignore").decode("utf-8", errors="ignore"))
        except Exception:
            continue

    best = text
    best_score = before
    for c in candidates:
        score = sum(c.count(m) for m in markers)
        if score < best_score:
            best = c
            best_score = score

    return best


def _safe_remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _sanitize_filename(name: str, max_len: int = 140) -> str:
    # Keep Unicode, but remove characters invalid on Windows filesystems.
    invalid = '<>:"/\\|?*'
    cleaned = "".join(("_" if (c in invalid or ord(c) < 32) else c) for c in name)
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.strip(" .")
    if not cleaned:
        cleaned = "download"

    # Limit length to avoid Windows MAX_PATH issues.
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" .")
    return cleaned


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(1, 100):
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
    return path


def _pick_latest_file(folder: Path) -> Path:
    files = [p for p in folder.glob("*") if p.is_file()]
    if not files:
        raise RuntimeError("Nu s-a generat niciun fișier.")
    return max(files, key=lambda p: p.stat().st_mtime)


def _best_thumbnail(info: dict | object) -> str | None:
    if not isinstance(info, dict):
        return None
    thumb = info.get("thumbnail")
    if isinstance(thumb, str) and thumb.strip():
        return thumb.strip()

    thumbs = info.get("thumbnails")
    if not isinstance(thumbs, list) or not thumbs:
        return None

    best_url: str | None = None
    best_score = -1
    for t in thumbs:
        if not isinstance(t, dict):
            continue
        url = t.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        w = t.get("width")
        h = t.get("height")
        score = 0
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            score = w * h
        if score >= best_score:
            best_score = score
            best_url = url.strip()

    return best_url


def _maybe_cookiefile() -> str | None:
    env = os.getenv("AVE_COOKIES_FILE")
    if env:
        p = Path(env)
        if p.exists() and p.is_file():
            return str(p)

    default = PROJECT_DIR / "cookies.txt"
    if default.exists() and default.is_file():
        return str(default)
    return None


def _looks_like_youtube(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def _ffmpeg_dir() -> Path | None:
    """Return directory containing ffmpeg.exe/ffprobe.exe if found."""
    env = os.getenv("AVE_FFMPEG_PATH")
    if env:
        p = Path(env)
        if p.is_dir():
            ff = p / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            fp = p / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
            if ff.exists() or fp.exists():
                return p
        if p.exists() and p.is_file():
            return p.parent

    # Common local bundles in this project
    candidates = [
        PROJECT_DIR / "ffmpeg" / "bin",
        PROJECT_DIR / "tools" / "ffmpeg" / "bin",
    ]
    for d in candidates:
        if (d / "ffmpeg.exe").exists() or (d / "ffprobe.exe").exists():
            return d

    which = shutil.which("ffmpeg")
    if which:
        return Path(which).resolve().parent
    return None


def _run_ytdlp(job_id: str) -> None:
    job = _jobs[job_id]
    job.status = "running"

    import yt_dlp  # local import so app can still start if deps missing

    class _JobLogger:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def _add(self, level: str, msg: str) -> None:
            text = f"[{level}] {msg}".strip()
            self.lines.append(text)
            if len(self.lines) > 200:
                self.lines = self.lines[-200:]

        def debug(self, msg: str) -> None:
            if os.getenv("AVE_YTDLP_VERBOSE"):
                self._add("debug", msg)

        def warning(self, msg: str) -> None:
            self._add("warning", msg)

        def error(self, msg: str) -> None:
            self._add("error", msg)

    logger = _JobLogger()

    job_dir = DOWNLOADS_DIR / job_id
    _safe_remove_tree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    cookiefile = _maybe_cookiefile()

    ffmpeg_dir = _ffmpeg_dir()

    # IMPORTANT (Windows): some platforms (notably Facebook) produce titles with characters
    # that are illegal in filenames (e.g. '|'), causing "unable to open for writing".
    # Download using a safe template, then rename after download.
    common_opts: dict[str, object] = {
        "outtmpl": str(job_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "socket_timeout": 20,
        "logger": logger,
        "http_headers": DEFAULT_HTTP_HEADERS,
        "user_agent": DEFAULT_HTTP_HEADERS["User-Agent"],
        "windowsfilenames": True,
    }
    if cookiefile:
        common_opts["cookiefile"] = cookiefile

    # Let yt-dlp find ffmpeg/ffprobe even if not in PATH (via AVE_FFMPEG_PATH or local bundle).
    if ffmpeg_dir:
        common_opts["ffmpeg_location"] = str(ffmpeg_dir)
    else:
        # Avoid failing on container "fixup" steps that require ffmpeg.
        common_opts["fixup"] = "never"

    # No YouTube-specific config needed; yt-dlp handles client selection automatically.
    # Forcing specific player_client can cause PO Token issues.

    if job.download_type == "audio":
        # MP3 needs FFmpeg. If FFmpeg isn't installed, we still download audio
        # in the best available original container (m4a/webm/etc.).
        if job.audio_format == "mp3" and ffmpeg_dir:
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        else:
            # Either "original" requested or no ffmpeg available.
            ydl_opts = {**common_opts, "format": "bestaudio/best"}
    else:
        # Fără FFmpeg, combinarea (bestvideo + bestaudio) poate eșua.
        # Ca să funcționeze out-of-the-box, alegem un format "best" într-un singur fișier.
        # Dacă FFmpeg este disponibil, folosim calitate maximă (video+audio) și merge în MP4.
        if ffmpeg_dir:
            ydl_opts = {**common_opts, "format": "bv*+ba/best", "merge_output_format": "mp4"}
        else:
            ydl_opts = {**common_opts, "format": "best[ext=mp4]/best"}

    try:
        info: object | None = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            extracted = ydl.extract_info(job.url, download=True)
            extracted_dict = extracted if isinstance(extracted, dict) else None
            if extracted_dict and extracted_dict.get("_type") in {"playlist", "multi_video"}:
                entries = extracted_dict.get("entries") or []
                first = entries[0] if entries else None
                info = first if isinstance(first, dict) else extracted_dict
            else:
                info = extracted_dict

        produced = _pick_latest_file(job_dir)
        if produced.stat().st_size <= 0:
            raise RuntimeError("Fișierul descărcat este gol (0 bytes).")

        # Rename to a nicer, sanitized name for the user.
        if isinstance(info, dict):
            title = _fix_mojibake(info.get("title")) or "download"
            vid = info.get("id") or job_id
            ext = produced.suffix
            desired_name = _sanitize_filename(f"{title} [{vid}]") + ext
            target = _dedupe_path(produced.with_name(desired_name))
            try:
                produced.rename(target)
                produced = target
            except Exception:
                # If rename fails for any reason, keep the safe id-based filename.
                pass

        job.filename = produced.name
        job.status = "done"

    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        base = str(exc) or exc.__class__.__name__
        hint = ""
        low = base.lower()
        url_low = job.url.lower()
        if "video unavailable" in low or "unavailable" in low:
            hint = "\n\nSugestie: clipul e indisponibil (privat/șters/region/age). Încearcă alt link sau folosește cookies."
        elif "downloaded file is empty" in low or "0 bytes" in low:
            hint = "\n\nSugestie: poate fi blocare/403 sau format indisponibil. Încearcă Video (MP4) sau setează cookies."
        elif "unsupported url" in low:
            hint = "\n\nSugestie: link invalid/neacceptat. Încearcă un link direct către clip."
        elif "facebook" in url_low and not cookiefile:
            hint = "\n\nSugestie (Facebook): deseori e nevoie de cookies ca să meargă stabil. Setează AVE_COOKIES_FILE sau pune un cookies.txt în proiect."

        log_tail = ""
        if logger.lines:
            log_tail = "\n\nDetalii (yt-dlp):\n" + "\n".join(logger.lines[-25:])
        job.error = base + hint + log_tail


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        _template_base_context(request),
    )


@app.get("/api/preview")
def preview(url: str):
    url = (url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL gol")

    now = time.time()
    with _preview_lock:
        cached = _preview_cache.get(url)
        if cached and (now - cached._ts) < 180:
            return {
                "ok": True,
                "url": cached.url,
                "title": cached.title,
                "uploader": cached.uploader,
                "description": cached.description,
                "duration": cached.duration,
                "duration_text": _human_duration(cached.duration),
                "thumbnail": cached.thumbnail,
                "webpage_url": cached.webpage_url,
                "extractor": cached.extractor,
                "warning": cached.warning,
                "needs_cookies": cached.needs_cookies,
            }

    import yt_dlp

    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "retries": 2,
        "socket_timeout": 15,
        "http_headers": DEFAULT_HTTP_HEADERS,
        "user_agent": DEFAULT_HTTP_HEADERS["User-Agent"],
    }

    cookiefile = _maybe_cookiefile()
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    if _looks_like_youtube(url):
        ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android", "web_safari"]}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            info = ydl.extract_info(url, download=False)

        # Sometimes extract_info returns a playlist/container.
        if isinstance(info, dict) and info.get("_type") in {"playlist", "multi_video"}:
            entries = info.get("entries") or []
            info = entries[0] if entries else info

        extractor = (info.get("extractor_key") if isinstance(info, dict) else None) or (
            info.get("extractor") if isinstance(info, dict) else None
        )

        title = _fix_mojibake((info.get("title") if isinstance(info, dict) else None))
        uploader = _fix_mojibake((info.get("uploader") if isinstance(info, dict) else None))
        description = _fix_mojibake((info.get("description") if isinstance(info, dict) else None))
        thumbnail = _best_thumbnail(info) if isinstance(info, dict) else None
        webpage_url = (info.get("webpage_url") if isinstance(info, dict) else None)

        needs_cookies = False
        warning: str | None = None
        if isinstance(extractor, str) and extractor.lower().startswith("facebook"):
            # Facebook often blocks metadata unless cookies are provided.
            # Return a non-fatal hint so UI can guide the user.
            if not cookiefile:
                needs_cookies = True
                if not title or not thumbnail or not description:
                    warning = (
                        "Facebook: preview poate fi limitat fără cookies. "
                        "Dacă nu apar titlu/poză/descriere, setează cookies (AVE_COOKIES_FILE sau cookies.txt)."
                    )

        p = Preview(
            url=url,
            title=title,
            uploader=uploader,
            description=description,
            duration=(info.get("duration") if isinstance(info, dict) else None),
            thumbnail=thumbnail,
            webpage_url=webpage_url,
            extractor=extractor,
            warning=warning,
            needs_cookies=needs_cookies,
            _ts=now,
        )

        with _preview_lock:
            _preview_cache[url] = p

        return {
            "ok": True,
            "url": p.url,
            "title": p.title,
            "uploader": p.uploader,
            "description": p.description,
            "duration": p.duration,
            "duration_text": _human_duration(p.duration),
            "thumbnail": p.thumbnail,
            "webpage_url": p.webpage_url,
            "extractor": p.extractor,
            "warning": p.warning,
            "needs_cookies": p.needs_cookies,
        }

    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": url, "error": str(exc) or exc.__class__.__name__}


@app.post("/download", response_class=HTMLResponse)
def start_download(
    request: Request,
    url: str = Form(...),
    download_type: DownloadType = Form(...),
    audio_format: AudioFormat = Form("mp3"),
):
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL gol")

    job_id = uuid.uuid4().hex
    job = Job(
        id=job_id,
        status="queued",
        download_type=download_type,
        audio_format=audio_format,
        url=url,
    )
    _jobs[job_id] = job

    future = _executor.submit(_run_ytdlp, job_id)
    _futures[job_id] = future

    # IMPORTANT (Apache / reverse-proxy):
    # Do not issue redirects that may expose the backend host (127.0.0.1:8000).
    # Render the job page directly so all navigation stays on the same origin.
    return templates.TemplateResponse(
        "job.html",
        {
            **_template_base_context(request),
            "job": job,
        },
        status_code=200,
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job inexistent")

    return templates.TemplateResponse(
        "job.html",
        {
            **_template_base_context(request),
            "job": job,
        },
    )


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job inexistent")
    return {
        "id": job.id,
        "status": job.status,
        "download_type": job.download_type,
        "audio_format": job.audio_format,
        "filename": job.filename,
        "error": job.error,
    }


@app.get("/files/{job_id}")
def download_file(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job inexistent")
    if job.status != "done" or not job.filename:
        raise HTTPException(status_code=409, detail="Fișierul nu este gata")

    file_path = DOWNLOADS_DIR / job_id / job.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fișierul nu a fost găsit")

    return FileResponse(
        path=str(file_path),
        filename=job.filename,
        media_type="application/octet-stream",
    )


@app.get("/health")
def health():
    return {"ok": True, "downloads_dir": str(DOWNLOADS_DIR)}


def _ffmpeg_in_path() -> bool:
    return _ffmpeg_dir() is not None


@app.get("/diagnostics")
def diagnostics():
    return {
        "build": APP_BUILD,
        "ffmpeg_in_path": _ffmpeg_in_path(),
        "ffmpeg_location": str(_ffmpeg_dir()) if _ffmpeg_dir() else None,
        "downloads_dir": str(DOWNLOADS_DIR),
        "cwd": os.getcwd(),
    }


@app.get("/debug/build")
def debug_build():
    return {
        "build": APP_BUILD,
        "frozen": bool(getattr(sys, "frozen", False)),
        "project_dir": str(PROJECT_DIR),
        "downloads_dir": str(DOWNLOADS_DIR),
    }
