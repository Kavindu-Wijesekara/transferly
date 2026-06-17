# Transferly

Transferly is a modern command-line tool that simplifies moving files from download sources to cloud storage.

Built on top of aria2 and rclone, Transferly provides an interactive workflow for downloading, streaming, and uploading files without requiring users to manually manage transfers.

## Features

- Download files from direct URLs
- Stream downloads directly to cloud storage without saving locally
- Download then upload workflows
- Upload local files to cloud storage
- Interactive cloud remote and folder selection
- Create remote folders during transfer
- Automatic filename detection
- Optional file renaming
- Bearer token authentication support
- Custom HTTP header support
- High-speed downloads using aria2
- Cloud storage support through rclone
- Graceful interruption handling
- VPS and seedbox friendly

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

Coming soon.

## Usage

```bash
tsf
```

## Planned Features

- Download queue management
- Transfer history
- Saved destinations
- Retry strategies
- Advanced progress interface
- Configuration profiles
- Self-update command
- Web dashboard

## Requirements

- Python 3.10+
- aria2
- rclone

## License

MIT
