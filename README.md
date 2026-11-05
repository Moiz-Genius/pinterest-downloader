# 📌 Pinterest Ultra-Fast Downloader CLI

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org/)
[![HTTP Client](https://img.shields.io/badge/Client-HTTPX%20Async-00599C.svg)](https://www.python-httpx.org/)
[![Parser](https://img.shields.io/badge/HTML%20Parser-BeautifulSoup4-orange.svg)](https://www.crummy.com/software/BeautifulSoup/)
[![CLI UI](https://img.shields.io/badge/UI-Rich-magenta.svg)](https://github.com/Textualize/rich)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Moiz-Genius/pinterest-downloader/pulls)

A lightweight, blazing-fast asynchronous Python CLI tool that extracts and downloads original-quality images, high-definition videos (MP4 1080p/720p), and animated GIFs from any Pinterest URL or `pin.it` short link.

---

## ✨ Features

- ⚡ **Ultra-Fast Asynchronous Engine**: Built with `httpx` async client and parallel chunk streaming for maximum download speeds.
- 🎯 **Highest Resolution Auto-Detection**:
  - Automatically fetches uncompressed original images directly from `i.pinimg.com/originals/`.
  - Discovers the highest available bitrate video streams (1080p / 720p).
  - Handles animated GIFs without degradation.
- 🔗 **Smart URL Resolution**: Resolves both short redirects (`https://pin.it/...`) and canonical URLs (`https://www.pinterest.com/pin/...`).
- 💻 **Dual Execution Modes**:
  - **Interactive Mode**: Launch the interactive terminal prompt to download multiple pins sequentially without restarting.
  - **Direct CLI Mode**: Pass one or more URLs via command-line arguments for scripts and automation.
- 📊 **Rich Terminal Interface**: Live progress bars, transfer rates in MB/s, file size metrics, and styled metadata cards.

---

## 📋 Prerequisites

- **Python**: Version 3.10 or higher
- Compatible with Windows, macOS, and Linux

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Moiz-Genius/pinterest-downloader.git
cd pinterest-downloader
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

*(Dependencies: `httpx>=0.27.0`, `beautifulsoup4>=4.12.0`, `rich>=13.7.0`)*

---

## 💡 How to Use

### Option A: Interactive Mode (Easiest)

Simply run the CLI without arguments:

```bash
python main.py
```

Paste any Pinterest link at the prompt and press Enter:
```text
[*] Paste Pinterest URL: https://pin.it/xxxxxxx
```
Type `exit` or `q` whenever you want to close the tool.

---

### Option B: Direct Command-Line Mode

Download a single pin:
```bash
python main.py "https://pin.it/xxxxxxx"
```

Download multiple pins in sequence:
```bash
python main.py "https://pin.it/111" "https://www.pinterest.com/pin/222"
```

Save to a custom destination directory:
```bash
python main.py "https://pin.it/xxxxxxx" -o "./my_saved_pins"
```

Tune parallel chunks for high-bandwidth connections:
```bash
python main.py "https://pin.it/xxxxxxx" -c 8
```

---

## 📁 Project Structure

```text
pinterest-downloader/
├── main.py              # CLI entry point (interactive REPL & CLI argument parser)
├── downloader.py        # Asynchronous media parser & multi-chunk streaming engine
├── requirements.txt     # Python package requirements
├── .gitignore           # Ignores downloaded media, caches & temp files
└── README.md            # Documentation & usage guide
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
