# FastGet
High-speed File Downloading Tool

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

## How it works?
FastGet uses the HTTP Range header to download files in parallel by splitting them into multiple blocks.

This allows for high-speed downloads in environments with high bandwidth.

The downside is that it cannot be used if the server does not support the Range header, and it requires sufficient bandwidth availability on both the server and the client side.
