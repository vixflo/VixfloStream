from __future__ import annotations

import os
import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
import sys

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
    # In PyInstaller `--noconsole`, Uvicorn's default logging formatter can crash
    # because it may call `stream.isatty()` on a missing/None stream.
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


def _open_when_ready(open_url: str, health_url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if 200 <= resp.status < 300:
                    webbrowser.open(open_url)
                    return
        except Exception:
            time.sleep(0.3)

    webbrowser.open(open_url)


def main() -> None:
    try:
        host = os.environ.get("AVE_HOST", "127.0.0.1")

        # Prefer a random free port to avoid conflicts with Apache/Uvicorn instances.
        env_port = os.environ.get("AVE_PORT")
        fixed_port = int(env_port) if env_port else None

        sock: socket.socket | None = None
        port: int
        if fixed_port is not None:
            port = fixed_port
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, 0))
            sock.listen(128)
            port = int(sock.getsockname()[1])

        # URL-ul pe care îl deschide aplicația în browser.
        # Pentru testare/local: http://127.0.0.1:8000/
        # Pentru Apache/HTTPS: setează AVE_OPEN_URL=https://vixflodev.ro/VixfloStream/
        open_url = os.environ.get("AVE_OPEN_URL", f"http://{host}:{port}/")

        health_url = f"http://{host}:{port}/health"

        opener = threading.Thread(
            target=_open_when_ready,
            args=(open_url, health_url),
            daemon=True,
        )
        opener.start()

        log_level = os.environ.get("AVE_LOG_LEVEL", "info")

        log_config = None
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            log_dir = _pick_writable_dir(
                os.path.join(exe_dir, "logs"),
                os.path.join(_appdata_dir(), "logs"),
                os.path.join(os.environ.get("TEMP", os.getcwd()), "VixfloStreamDownloader", "logs"),
            )
            log_config = _safe_uvicorn_log_config(
                os.path.join(log_dir, "uvicorn-launcher.log"),
                level=log_level,
            )

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

        # If we created our own socket (random port), pass it to Uvicorn so it uses that port.
        if sock is not None:
            server.run(sockets=[sock])
        else:
            server.run()
    except Exception as exc:  # noqa: BLE001
        _write_fatal_log("VixfloStreamDownloader-fatal.log", exc)
        raise


if __name__ == "__main__":
    main()
