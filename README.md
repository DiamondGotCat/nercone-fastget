
![](assets/preview.gif)

# FastGet
High-speed File Downloading Tool

## How
It's using Multiple Thread Download.

This is need Range-select feature, in Server-side.

## Requiments
- CPython 3.9+
- `uv` [PyPI↗︎](https://pypi.org/project/uv/) or `pip3` [PyPI↗︎](https://pypi.org/project/pip/) 
- `rich` [PyPI↗︎](https://pypi.org/project/rich/) for Modern CLI Visual
- `httpx[http2]` [PyPI↗︎](https://pypi.org/project/httpx/) for HTTP Connection

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
```
fastget [-h] [-o OUTPUT] [-t THREADS] [-X {GET,POST}] [-H HEADER] [-d DATA] [--no-verify] [--no-info] [--no-http1] [--no-http2] [-v] url
```

```
nercone@demo ~> fastget -h
usage: fastget [-h] [-o OUTPUT] [-t THREADS] [-X {GET,POST}] [-H HEADER] [-d DATA] [--no-verify]
               [--no-info] [--no-http1] [--no-http2] [-v]
               url

High-speed File Downloading Tool

positional arguments:
  url                   URL to download from.

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path to save the file. If not specified, it's inferred from the URL.
  -t THREADS, --threads THREADS
                        Number of parallel connections. (default: 8)
  -X {GET,POST}, --request {GET,POST}
                        HTTP method to use. (default: GET)
  -H HEADER, --header HEADER
                        Custom header to send with the request (e.g., 'User-Agent: my-app/1.0').
                        Can be specified multiple times.
  -d DATA, --data DATA  Data to send in a POST request.
  --no-verify           Disable SSL/TLS certificate verification.
  --no-info             Silent mode. Suppress progress bar and other info.
                        Errors are still printed to stderr.
  --no-http1            Disable HTTP/1.x and force HTTP/2.
  --no-http2            Disable HTTP/2 and force HTTP/1.x.
  -v, --version         show program's version number and exit
```

![PyPI - Version](https://img.shields.io/pypi/v/nercone-fastget)
