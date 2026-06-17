# Transferly

Transferly is a modern interactive CLI transfer manager for Linux servers, VPSs, seedboxes, and desktops. It orchestrates downloads, cloud streaming, and uploads by delegating transfer work to **aria2** and **rclone**.

## Command

```bash
tsf
tsf --version
tsf self-update
```

## Features

- Stream URL → Cloud with `aria2c` piped to `rclone rcat`
- Download URL → Upload using `aria2c` and `rclone copyto`
- Download URL Only with resume support
- Upload existing local files to rclone remotes
- Interactive cloud browser with folder creation and back/cancel navigation
- Reusable authentication options: no auth, bearer token, custom headers, cookie file
- Filename detection by `Content-Disposition`, final redirect URL, then manual prompt
- Automatic download strategies: aria2 direct, aria2 browser User-Agent, aria2 custom headers, wget fallback
- SQLite transfer history
- Rich terminal UI and graceful Ctrl+C cleanup
- XDG-style configuration under `~/.config/transferly/`

## Installation

From a cloned repository:

```bash
./install.sh
```

One-command GitHub installation once published:

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/transferly/main/install.sh | bash
```

The installer:

1. Detects apt/dnf/pacman systems.
2. Installs Python, aria2, rclone, rsync, and git.
3. Creates `~/.transferly/venv/`.
4. Installs Python packages from `requirements.txt`.
5. Copies the app to `~/.transferly/app/`.
6. Creates config/log directories.
7. Registers `~/.local/bin/tsf`.
8. Verifies installation with `tsf --version`.

Make sure `~/.local/bin` is on your `PATH`.

## Main Menu

```text
Transferly

Select Action
1. Stream URL → Cloud
2. Download URL → Upload
3. Download URL Only
4. Upload Local File
5. Browse Cloud Storage
6. Transfer History
7. Settings
8. Exit
```

## Configuration

- Config: `~/.config/transferly/config.json`
- History: `~/.config/transferly/history.db`
- Logs: `~/.config/transferly/logs/`
- App: `~/.transferly/app/`
- Virtual environment: `~/.transferly/venv/`
- Launcher: `~/.local/bin/tsf`

Settings currently include default remote, default transfer mode, cleanup behavior, download directory, and history display limit.

## Security

Transferly never stores cloud credentials. Cloud authentication remains managed by rclone. Bearer tokens, cookies, and sensitive URL query parameters are redacted before history/log display paths.

## Requirements

- Python 3.11+
- aria2
- rclone
- Linux target: Ubuntu 22.04+, Ubuntu 24.04+, Debian 12+
- Secondary support: Fedora and Arch Linux

## License

MIT
