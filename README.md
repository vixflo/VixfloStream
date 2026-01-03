# VixfloStream Downloader (local web)

Aplicație locală (Windows) care descarcă video (MP4) sau audio (MP3) din link-uri suportate de `yt-dlp` (YouTube, TikTok, Facebook etc.) și oferă fișierul pentru download din browser.

## Instalare

1. Deschide un terminal în acest folder.
2. Instalează dependențele:

```bat
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. (Opțional, recomandat pentru MP3) Instalează **FFmpeg** și asigură-te că `ffmpeg` este în `PATH`.

## Rulare

- Dublu click pe `run.bat` sau rulează:

```bat
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips *
```

Apoi deschide: http://127.0.0.1:8000

### Start automat (recomandat)

- Local: rulează `start_local_auto.bat`
- HTTPS prin Apache: rulează `start_https_auto.bat` (și asigură-te că Apache e configurat)

### Fără fereastră de consolă (backend ascuns)

- Dublu click pe `start_backend_hidden.vbs` ca să repornești backend-ul pentru Apache fără să îți stea o fereastră CMD deschisă.
	- Dacă era deja pornit (versiune veche), îl oprește și pornește versiunea nouă.
	- Loguri: `logs/backend_bg.log` și `logs/backend_bg.err.log`

## Rulare prin XAMPP (URL: https://vixflodev.ro/VixfloStream/)

Aplicația FastAPI rulează tot pe `127.0.0.1:8000`, iar Apache (XAMPP) o expune la URL-ul dorit prin reverse-proxy.

1. În Apache activează modulele: `rewrite`, `proxy`, `proxy_http`, `headers`.
2. Asigură-te că pentru folderul `htdocs` (sau acest proiect) ai `AllowOverride All` (ca să fie citit fișierul `.htaccess`).
3. Pornește serverul FastAPI (ex. cu `run.bat`).
4. Configurează local domeniul `vixflodev.ro` către PC-ul tău (hosts file) și un VirtualHost SSL în Apache.
5. Accesează: https://vixflodev.ro/VixfloStream/

Proiectul include un `.htaccess` care face proxy spre `127.0.0.1:8000` și setează headerele `X-Forwarded-*` (inclusiv `X-Forwarded-Prefix: /VixfloStream`). HTTPS-ul este gestionat de Apache (certificat local, ex. mkcert).

## Build EXE (desktop)

Proiectul are 3 moduri de utilizare (Windows 10/11):

1) **Browser (local)**: pornește serverul local și deschide UI în browserul implicit.
2) **Server-only (pentru Apache/XAMPP)**: pornește doar backend-ul pe un port fix (implicit `8000`).
3) **Desktop app (Electron)**: aplicație de tip „desktop” (portable + installer) care pornește backend-ul automat.

### 1) Browser (local) – EXE (PyInstaller)

Construiește un EXE care pornește serverul local și îți deschide automat în browser (local sau URL-ul setat prin `AVE_OPEN_URL`):

```bat
.\build_exe.bat
```

Rezultatul este în `dist\VixfloStreamDownloader.exe`.

### 2) Server-only (pentru Apache/XAMPP) – EXE (PyInstaller)

Construiește backend-ul (fără auto-open browser):

```bat
.\build_backend_exe.bat
```

Rezultatul este în `dist\VixfloStreamBackend.exe` (implicit pornește pe `127.0.0.1:8000`).

### 3) Desktop app (Electron) – Portable + Installer

În `desktop-electron/`:

```bat
npm run dist
```

Artefacte:
- `desktop-electron\dist\VixfloStream Downloader 0.1.0.exe` (portable)
- `desktop-electron\dist\VixfloStream Downloader Setup 0.1.0.exe` (installer)

Installerul creează 3 shortcut-uri (Desktop + Start Menu):
- **VixfloStream Downloader** (Desktop/Electron)
- **VixfloStream Downloader (Browser)**
- **VixfloStream Downloader (Server)**

## Unde se salvează fișierele

Fișierele sunt salvate în `downloads/` (subfolder per job).

- În dezvoltare: `downloads/` din proiect.
- În EXE/installer: dacă folderul de lângă EXE nu este „writable” (ex. `Program Files`), aplicația folosește automat:
	- `%LOCALAPPDATA%\VixfloStream Downloader\downloads`

Logurile Uvicorn pentru build-urile fără consolă sunt scrise în mod similar (în `%LOCALAPPDATA%\VixfloStream Downloader\logs` dacă nu se poate lângă EXE).

## Note

- Pentru conținut privat / care necesită autentificare, poate fi nevoie de cookies (neimplementat încă în UI).
- Dacă MP3 nu funcționează, verifică: http://127.0.0.1:8000/diagnostics

## FFmpeg (verificare)

În PowerShell, comanda `where` este alias pentru `Where-Object`. Folosește `where.exe`:

```powershell
where.exe ffmpeg
ffmpeg -version
```
