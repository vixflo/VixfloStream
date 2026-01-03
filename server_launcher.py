from __future__ import annotations

import os
import sys
import time
import traceback

import uvicorn


def _appdata_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return os.path.join(base, "VixfloStream Downloader")
    return os.path.join(os.path.expanduser("~"), "VixfloStream Downloader")


def _pick_writable_dir(*candidates: str) -> str:
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            try:
                os.remove(probe)
            except Exception:
                pass
            return d
        except Exception:
            continue
    return candidates[0] if candidates else os.getcwd()


def _get_asgi_app():
    # IMPORTANT for PyInstaller builds:
    # If we pass a string like "app.main:app", Uvicorn imports it dynamically at
    # runtime and PyInstaller may not bundle the local `app` package.
    from app.main import app as asgi_app  # noqa: WPS433

    return asgi_app


def _safe_uvicorn_log_config(log_path: str, level: str) -> dict:
    # Uvicorn's default LOGGING_CONFIG may call `stream.isatty()`. In PyInstaller
    # `--noconsole` mode, streams can be missing/None, causing a crash at startup.
    # Use a simple file-based config instead.
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "formatter": "default",
                "filename": log_path,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["file"], "level": level.upper(), "propagate": False},
            "uvicorn.error": {"handlers": ["file"], "level": level.upper(), "propagate": False},
            "uvicorn.access": {"handlers": ["file"], "level": level.upper(), "propagate": False},
        },
    }


def _write_fatal_log(where: str, exc: BaseException) -> None:
    try:
        exe_dir = os.path.dirname(os.path.abspath(getattr(__import__("sys"), "executable", "")))
        log_dir = _pick_writable_dir(
            os.path.join(exe_dir, "logs"),
            os.path.join(_appdata_dir(), "logs"),
            os.path.join(os.environ.get("TEMP", os.getcwd()), "VixfloStreamDownloader", "logs"),
        )
        path = os.path.join(log_dir, where)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== FATAL ===\n")
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("\n")
            f.write(repr(exc))
            f.write("\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass


def main() -> None:
    try:
        host = os.environ.get("AVE_HOST", "127.0.0.1")
        port = int(os.environ.get("AVE_PORT", "8000"))

        log_level = os.environ.get("AVE_LOG_LEVEL", "info")

        # When frozen with PyInstaller, prefer logging to a file next to the EXE.
        log_config = None
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            log_dir = _pick_writable_dir(
                os.path.join(exe_dir, "logs"),
                os.path.join(_appdata_dir(), "logs"),
                os.path.join(os.environ.get("TEMP", os.getcwd()), "VixfloStreamDownloader", "logs"),
            )
            log_config = _safe_uvicorn_log_config(
                os.path.join(log_dir, "uvicorn-backend.log"),
                level=log_level,
            )

        # Server-only launcher: no browser auto-open.
        asgi_app = _get_asgi_app()
        config = uvicorn.Config(
            asgi_app,
            host=host,
            port=port,
            log_level=log_level,
            log_config=log_config,
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as exc:  # noqa: BLE001
        _write_fatal_log("VixfloStreamBackend-fatal.log", exc)
        raise


if __name__ == "__main__":
    main()
