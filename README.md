
<img width="1920" alt="fastget" src="https://github.com/user-attachments/assets/fb4b6013-f65b-4c34-ae86-848011e7bfcf" />

# FastGet
High-speed File Downloading Tool

## How
It's using Multiple Thread Download.

This is need Range-select feature, in Server-side.

## Requiments
- CPython 3.9+
- `uv` [PyPI↗︎](https://pypi.org/project/uv/) or `pip3` [PyPI↗︎](https://pypi.org/project/pip/) 
- `nercone-modern` [PyPI↗︎](https://pypi.org/project/nercone-modern/) for Modern CLI Visual
- `httpx[http2]` [PyPI↗︎](https://pypi.org/project/httpx/) for HTTP Connection
- `uvloop` [PyPI↗︎](https://pypi.org/project/uvloop/) for Fast Asynchronous Processing (non-Windows only)

## Installation

### uv (recommended)
```
uv tool install nercone-fastget
```

### pip3

**System Python:**
```
pip3 install nercone-fastget --break-system-packages
```

**Venv Python:**
```
pip3 install nercone-fastget
```

## Update

### uv
```
uv tool install nercone-fastget --upgrade
```

### pip3

**System Python:**
```
pip3 install nercone-fastget --upgrade --break-system-packages
```

**Venv Python:**
```
pip3 install nercone-fastget --upgrade
```

## Usage

### Show helps
```
fastget [-h] [--help]
```

```
nercone@demo ~/Downloads> fastget -h
usage: fastget [-h] [-o OUTPUT] [-X {GET,POST}] [-d DATA] [-H HEADER] [-t THREADS] [-p] [-s] [-m] [--no-verify] [--no-info] [--no-http1] [--no-http2] url

Modern High-Performance Downloader

positional arguments:
  url                   Target URL

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        File destination
  -X {GET,POST}, --method {GET,POST}
                        HTTP method (GET/POST)
  -d DATA, --data DATA  Data for POST method
  -H HEADER, --header HEADER
                        Custom Headers
  -t THREADS, --threads THREADS
                        Number of threads to use for downloading
  -p, --print           Output data directly to stdout without saving to a file
  -s, --storage, --low-memory
                        Utilize storage efficiently to reduce memory usage during internal processes such as downloading and merging.
  -m, --memory, --low-storage
                        Utilize memory efficiently to reduce maximum concurrent storage usage during internal processes such as downloading and merging.
  --no-verify           In the case of HTTPS, if a secure connection cannot be established, the system will continue to operate normally.
  --no-info             Suppresses all displays such as progress bars. If --print is used, only data is output to stdout.
  --no-http1            Do not use HTTP/1 or HTTP/1.1
  --no-http2            Do not use HTTP/2
```

### Download
```
fastget [-o OUTPUT] [-X {GET,POST}] [-d DATA] [-H HEADER] [-t THREADS] [-p] [-s] [-m] [--no-verify] [--no-info] [--no-http1] [--no-http2] url
```

```
nercone@demo ~> fastget https://download.fedoraproject.org/pub/fedora/linux/releases/43/Server/aarch64/iso/Fedora-Server-netinst-aarch64-43-1.6.iso
[2025-12-05T17:24:31Z INFO     fastget] File size: 1,198,647,296 bytes
[2025-12-05T17:24:31Z INFO     fastget] Connection Type: HTTPS (HTTP/1.1, TLS, Verified)
[2025-12-05T17:24:31Z INFO     fastget] Threads: 8
[-------------------------------------] Total DONE No Message
[-------------------------------------] DL #1 DONE No Message
[-------------------------------------] DL #2 DONE No Message
[-------------------------------------] DL #3 DONE No Message
[-------------------------------------] DL #4 DONE No Message
[-------------------------------------] DL #5 DONE No Message
[-------------------------------------] DL #6 DONE No Message
[-------------------------------------] DL #7 DONE No Message
[-------------------------------------] DL #8 DONE No Message
[-------------------------------------] Marge DONE No Message
[2025-12-05T17:24:46Z INFO     fastget] Completed in 16222.00ms
[2025-12-05T17:24:46Z INFO     fastget] Saved to: Fedora-Server-netinst-aarch64-43-1.6.iso
```

![PyPI - Version](https://img.shields.io/pypi/v/nercone-fastget)
