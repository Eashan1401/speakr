# Speakr

Free, local voice dictation for macOS. Works in any app, any text field.
Powered by [OpenAI Whisper](https://github.com/openai/whisper) running fully on your device — no subscriptions, no API keys, nothing leaving your machine.

## What it does

Hold **Right Option (⌥)** anywhere. Speak. Release. Text appears at your cursor.

- Live waveform animation while recording
- Bouncing dots while transcribing
- Automatically pastes into whatever app is focused
- Works in any text field: messages, emails, code editors, notes, browsers

## Install

```bash
git clone https://github.com/YOUR_USERNAME/speakr.git
cd speakr
./install.sh
```

Then grant **Accessibility** permission to your terminal (System Settings → Privacy & Security → Accessibility → add your terminal app). Required once.

## Run

```bash
source .venv/bin/activate && python speakr.py
```

The first launch downloads the Whisper model (~74MB for the default `base` model). After that, it's instant.

Add a shell alias so you can start it from anywhere:

```bash
echo "alias speakr='cd /path/to/speakr && source .venv/bin/activate && python speakr.py'" >> ~/.zshrc
```

## Model sizes

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | 39 MB | fastest | lower |
| `base` | 74 MB | fast | good ← default |
| `small` | 244 MB | moderate | better |
| `medium` | 769 MB | slower | great |
| `large-v3` | 1.5 GB | slow | best |

```bash
SPEAKR_MODEL=small python speakr.py
```

## Requirements

- macOS 13+ (Ventura or later)
- Python 3.10+
- ~500MB disk space (model + deps)

## Sharing with friends

Push to GitHub. They clone and run `./install.sh`. That's it.

## How it works

1. `pynput` listens globally for Right Option keydown
2. `sounddevice` streams mic audio at 16kHz
3. On keyup, audio is written to a temp WAV and passed to `faster-whisper`
4. Transcribed text is set as clipboard contents, then `osascript` simulates Cmd+V
5. Clipboard is restored to its previous contents

All processing is local. No network calls during transcription.
