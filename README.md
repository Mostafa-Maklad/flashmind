<div align="center">

# ⚡ FlashMind

**A lightweight desktop overlay that periodically flashes images and notes on your screen — so knowledge sticks.**

*No browser. No notifications. No interruptions. Just a small window that slides in, shows you something worth remembering, and disappears.*

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)](https://github.com/Mostafa-Maklad/flashmind)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Arabic Support](https://img.shields.io/badge/Arabic-Supported-orange?style=flat-square)](https://github.com/Mostafa-Maklad/flashmind)

</div>

---

## What is it?

FlashMind is a **spaced-repetition-style desktop reminder** built with Python and Tkinter. You feed it folders of images or text files, and it periodically shows them in a small, non-intrusive overlay while you work.

Think of it like the dhikr reminder apps on your phone — except for anything you want to learn: security techniques, architecture diagrams, code snippets, quotes, vocabulary, whatever you want burned into your memory.

---

## Screenshots

> *Overlay slides in from the side, shows content, disappears after a few seconds — never steals focus.*

| Image overlay | Note overlay | Main window |
|:---:|:---:|:---:|
| Fits image to your configured size | Scrollable text, Arabic supported | Categories + Settings |

---

## Features

### Core
- **Periodic overlay** — shows content every N seconds (fully configurable)
- **Non-intrusive** — slides in from the side, auto-dismisses, never steals keyboard focus
- **Smart shuffle** — avoids repeating recent items, cycles through everything evenly

### Content
- **Images**: `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.webp`
- **Notes**: `.txt` `.md` — each double-newline-separated paragraph becomes its own card
- **Inline notes** — write notes directly in the app and assign them to a category
- **Append to file** — write a note and append it to any `.txt` / `.md` file on disk

### Categories
- Create unlimited categories (Security, Quotes, Architecture, Language, etc.)
- Each category has its own color badge shown on the overlay
- Point a category at whole **folders** or individual **files**
- Toggle categories on/off without deleting them

### Display
- **Auto-fits images** to your configured overlay size while preserving aspect ratio
- **Image bg opacity** slider — 0% means the image floats with no visible background box
- **Note font size** control — separate from UI font size
- Scrollbar on notes — long content never gets cut off
- Slide-in animation with progress bar showing time until auto-dismiss

### Customization (Settings tab)
| Setting | Description |
|---|---|
| Show every | Interval between displays (10s – 3600s) |
| Display duration | How long the overlay stays visible (2s – 60s) |
| Window size | Width × Height in pixels — your configured max |
| Position | Bottom-right / Bottom-left / Top-right / Top-left / Center |
| Note font size | Text size inside note overlays (8pt – 42pt) |
| Overlay opacity | Transparency of the overlay window |
| Image bg opacity | 0% = no background behind image; 100% = full background |
| Theme | Dark / Light |

### Language
- **Arabic text** is fully supported — uses `arabic-reshaper` + `python-bidi` to properly connect and display Arabic characters in the correct reading direction

---

## Installation

### Requirements
- Python 3.8 or higher
- Tkinter (included with standard Python on Windows/macOS; on Linux: `sudo apt install python3-tk`)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/Mostafa-Maklad/flashmind.git
cd flashmind

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python flashmind.py
```

### Dependencies

```
pillow          — image loading and rendering
arabic-reshaper — Arabic letter shaping (connects letters correctly)
python-bidi     — right-to-left text rendering
```

All three install automatically via `pip install -r requirements.txt`.

---

## Quick Start

1. **Run** `python flashmind.py`
2. Go to **Categories** tab → click **+ New Category**
3. Name your category (e.g. "Security Notes") and pick a color
4. Click **📁 Folder** to point it at a folder of images or `.txt` files
5. Set your interval in **Settings** (e.g. 300 seconds = every 5 minutes)
6. Click **Apply Settings** — done

The overlay will start appearing automatically after the first interval. Click **▶ Show Now** to test it immediately.

---

## Content Tips

**Text files** — separate entries with a blank line:
```
SQL injection bypasses UNION-based attacks

XSS filter evasion: use event handlers like onerror, onload

SSRF targets internal metadata endpoints like 169.254.169.254
```
Each block becomes a separate card shown at random.

**Images** — drop any screenshots, infographics, cheatsheets, diagrams, or memes into a folder and point a category at it.

**Mixed category** — point a category at a folder that contains both images and `.txt` files. FlashMind handles them all together.

---

## Config

Settings are saved automatically to `~/.flashmind_config.json`.  
Delete the file to reset everything to defaults.

---

## License

MIT — free to use, modify, and distribute.

---

<div align="center">

Made by [@Mostafa-Maklad](https://github.com/Mostafa-Maklad)

</div>
