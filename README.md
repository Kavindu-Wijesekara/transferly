# Transferly

Transferly is a modern command-line tool that simplifies moving files from download sources to cloud storage.

Built on top of aria2 and rclone, Transferly provides an interactive workflow for downloading, streaming, and uploading files without requiring users to manually manage transfers.

## Features

- `tsf` command with an interactive transfer workflow
- Download files from direct URLs
- Stream downloads directly to cloud storage without saving locally
- Download then upload workflows
- Upload local files to cloud storage
- Interactive cloud remote and folder selection
- Create remote folders during transfer
- Automatic filename detection
- Optional file renaming
- Bearer token authentication helper support
- Custom HTTP header helper support
- High-speed downloads using aria2
- Cloud storage support through rclone
- Transfer history under `~/.config/transferly/`
- Application files under `~/.transferly/`
- Version reporting with `tsf --version`
- `tsf self-update` placeholder command

## Supported Storage Providers

Transferly supports any storage provider supported by rclone, including:

- Google Drive
- Dropbox
- OneDrive
- Amazon S3
- Backblaze B2
- Wasabi
- SFTP
- WebDAV
- And many more

## Installation

```bash
./install.sh
```

The installer copies the application to `~/.transferly/app`, creates a virtual environment in `~/.transferly/venv`, installs Python dependencies, and writes the `tsf` launcher to `~/.local/bin/tsf`.

Make sure `~/.local/bin` is on your `PATH`.

## Usage

```bash
tsf
```

Show the installed version:

```bash
tsf --version
```

Self-update placeholder:

```bash
tsf self-update
```

## Requirements

- Python 3.10+
- aria2
- rclone
- Python packages listed in `requirements.txt`

## License

MIT
