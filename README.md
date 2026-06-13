# Speakr

Free, local voice dictation for macOS. Works in any app — VS Code, Chrome, Notes, Slack, anywhere.

No subscription. No API key. No data leaves your machine. Ever.

Powered by [OpenAI Whisper](https://github.com/openai/whisper) running fully on your device.

---

## How it works

1. Hold **Right Option (⌥)** anywhere while you type
2. Speak
3. Release — text is corrected and pasted instantly

The mic icon in your menu bar turns **red** while recording so you always know it's listening.

---

## Install

```bash
git clone https://github.com/Eashan1401/speakr.git
cd speakr
chmod +x install.sh && ./install.sh
```

That's it. The script handles Python deps, Java (for grammar correction), and adds a `speakr` command to your shell.

**One permission required (one-time):**
System Settings → Privacy & Security → Accessibility → add your terminal app

---

## Run

```bash
speakr
```

Or if you haven't restarted your terminal yet:

```bash
cd speakr && source .venv/bin/activate && python speakr.py
```

---

## Features

- **Works everywhere** — any text field in any app
- **Grammar correction** — spoken English is automatically cleaned up before pasting ("i dont know what you is talking" → "I don't know what you are talking about")
- **Live waveform** — animated overlay shows recording is active
- **Menu bar indicator** — mic icon turns red while recording, fades when done
- **100% local** — Whisper runs on your CPU, grammar engine runs on your machine, nothing is sent anywhere
- **Zero ongoing cost** — no API, no subscription, no tokens

---

## Privacy

Everything runs on your device:

| Component | Where it runs |
|-----------|--------------|
| Speech recognition | Local (faster-whisper, CPU) |
| Grammar correction | Local (LanguageTool Java server) |
| Text paste | Local (macOS AppleScript) |
| Network calls | None |

Your audio and text never leave your Mac.

---

## Model sizes

Swap models with `SPEAKR_MODEL=small python speakr.py`:

| Model | Size | Notes |
|-------|------|-------|
| `tiny` | 39 MB | Fastest, lower accuracy |
| `base` | 74 MB | Default — good balance |
| `small` | 244 MB | Better accuracy |
| `medium` | 769 MB | Great accuracy |
| `large-v3` | 1.5 GB | Best accuracy |

---

## Disable grammar correction

```bash
SPEAKR_POLISH=0 python speakr.py
```

## Disable sounds

Speakr plays a click when you start recording and a pop when text is pasted. To turn off:

```bash
SPEAKR_SOUND=0 python speakr.py
```

## Screen sharing / privacy mode

Hides all transcribed text from the terminal (text still pastes normally):

```bash
SPEAKR_SILENT=1 python speakr.py
```

---

## Requirements

- macOS 13+ (Ventura or later)
- Python 3.10+
- Homebrew (for Java install)
- ~500 MB disk (model + deps + grammar engine)

---

## Built with

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech recognition
- [language-tool-python](https://github.com/jxmorris12/language_tool_python) — grammar correction
- [PyQt6](https://pypi.org/project/PyQt6/) — overlay UI
- [pynput](https://github.com/moses-palmer/pynput) — global hotkeys
- [sounddevice](https://python-sounddevice.readthedocs.io/) — mic capture
