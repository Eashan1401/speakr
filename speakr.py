#!/usr/bin/env python3
"""
Speakr — free, local voice dictation for macOS.
Hold Right Option (⌥) to record, release to transcribe and paste.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import pyperclip
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from pynput import keyboard as kb
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

# ── Config ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE  = 16_000
MODEL        = os.getenv("SPEAKR_MODEL", "base")   # tiny|base|small|medium|large-v3
LANG         = os.getenv("SPEAKR_LANG",  "en")      # en|de|es|fr|it|nl|pt|auto…
HOTKEY       = kb.Key.alt_r                          # Hold Right Option (⌥)
MIN_SEC      = 0.25                                   # ignore accidental taps
BAR_COUNT    = 22

# Bake Homebrew Java path so LanguageTool always finds it
_java = "/opt/homebrew/opt/openjdk/bin"
if _java not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _java + ":" + os.environ.get("PATH", "")

HALLUCINATIONS = frozenset({
    "", ".", "..", "...", "you", "you.", "thank you", "thank you.",
    "thanks", "thanks.", "bye", "bye.", "okay", "okay.", "ok", "ok.",
    "so", "so.", "and", "and.", "huh", "huh.",
})

# Set SPEAKR_SILENT=1 to suppress transcribed text in terminal (screen-share privacy)
SILENT = os.getenv("SPEAKR_SILENT", "0") == "1"
# Set SPEAKR_SOUND=0 to disable click sounds
SOUND  = os.getenv("SPEAKR_SOUND",  "1") == "1"
# ──────────────────────────────────────────────────────────────────────────────


def _play(name: str) -> None:
    """Play a macOS system sound in a background thread (non-blocking)."""
    if not SOUND:
        return
    threading.Thread(
        target=lambda: subprocess.run(
            ["afplay", f"/System/Library/Sounds/{name}.aiff"],
            capture_output=True,
        ),
        daemon=True,
    ).start()


def _sanitize_app_name(name: str) -> str:
    """Remove chars that could break an AppleScript string literal."""
    return name.replace('"', "").replace("\\", "").replace("\n", "").replace("\r", "")[:64]


class AudioRecorder:
    """Captures mic audio via sounddevice with real-time RMS level tracking."""

    def __init__(self) -> None:
        self._lock   = threading.Lock()
        self._chunks : list[np.ndarray] = []
        self._levels : list[float]      = []
        self._stream = None

    def start(self) -> None:
        self._chunks, self._levels = [], []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=512, callback=self._cb,
        )
        self._stream.start()

    def _cb(self, data: np.ndarray, frames, time_info, status) -> None:
        with self._lock:
            self._chunks.append(data.copy())
            self._levels.append(float(np.sqrt(np.mean(data ** 2))))

    def bar_levels(self) -> list[float]:
        """Return BAR_COUNT normalised RMS levels (0.0–1.0) for waveform display."""
        with self._lock:
            raw = list(self._levels[-BAR_COUNT:]) if self._levels else []
        MAX_RMS = 0.07
        normed  = [min(1.0, v / MAX_RMS) for v in raw]
        while len(normed) < BAR_COUNT:
            normed.insert(0, 0.1)
        return normed

    def stop(self) -> tuple[np.ndarray, float]:
        """Stop recording; return (audio_array, duration_in_seconds)."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            chunks = list(self._chunks)
            self._chunks.clear()   # free memory immediately
            self._levels.clear()
        audio = (np.concatenate(chunks).flatten()
                 if chunks else np.zeros(SAMPLE_RATE, dtype="float32"))
        return audio, len(audio) / SAMPLE_RATE


class Transcriber:
    """Wraps faster-whisper; filters common hallucinations on silence."""

    def __init__(self) -> None:
        print(f"Loading Whisper '{MODEL}'…", end=" ", flush=True)
        self.model = WhisperModel(MODEL, device="cpu", compute_type="int8")
        print("ready.  Hold ⌥ Right to dictate.\n")

    def run(self, audio: np.ndarray) -> str:
        rms = float(np.sqrt(np.mean(audio ** 2)))
        dur = len(audio) / SAMPLE_RATE
        if not SILENT:
            print(f"   [{dur:.1f}s  rms={rms:.4f}]", flush=True)
        # Write to a restricted temp dir; always delete even on error
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="speakr_")
        try:
            os.close(fd)
            sf.write(path, audio, SAMPLE_RATE)
            lang = None if LANG == "auto" else LANG
            segs, _ = self.model.transcribe(
                path, beam_size=3, language=lang,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            raw = " ".join(s.text for s in segs).strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if raw.lower().rstrip(".,!?") in HALLUCINATIONS:
            if not SILENT:
                print(f"   [filtered: {raw!r}]", flush=True)
            return ""
        return raw


class Polisher:
    """Grammar + English correction using LanguageTool (100% local, zero cost).

    Loads in a background thread so it doesn't delay Whisper startup.
    Disable with: SPEAKR_POLISH=0 python speakr.py
    """

    def __init__(self) -> None:
        self._tool  = None
        self._ready = threading.Event()

        if os.getenv("SPEAKR_POLISH", "1") == "0":
            self._ready.set()
            return

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            import language_tool_python
            lt_lang = {"en": "en-US", "de": "de-DE", "es": "es", "fr": "fr",
                       "it": "it", "nl": "nl", "pt": "pt-BR"}.get(LANG, "en-US")
            print(f"  Starting grammar engine ({lt_lang})…", end=" ", flush=True)
            self._tool = language_tool_python.LanguageTool(lt_lang)
            print("ready.")
        except Exception as e:
            print(f"\n⚠  Grammar engine unavailable: {e}")
        finally:
            self._ready.set()

    def polish(self, text: str) -> str:
        self._ready.wait(timeout=30)
        if not self._tool or not text:
            return text
        try:
            import language_tool_python
            matches = self._tool.check(text)
            return language_tool_python.utils.correct(text, matches)
        except Exception:
            # Server may have died — attempt one silent restart
            try:
                import language_tool_python
                self._tool = language_tool_python.LanguageTool("en-US")
                matches = self._tool.check(text)
                return language_tool_python.utils.correct(text, matches)
            except Exception:
                self._tool = None
                return text


def _paste(text: str, target_app: str = "") -> None:
    """Re-focus target app, clipboard swap, Cmd-V, restore clipboard."""
    try:
        saved = pyperclip.paste()
    except Exception:
        saved = ""
    pyperclip.copy(text)
    if target_app:
        safe = _sanitize_app_name(target_app)
        subprocess.run(
            ["osascript", "-e", f'tell application "{safe}" to activate'],
            capture_output=True, timeout=3,
        )
        time.sleep(0.15)
    subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "v" using command down'],
        capture_output=True, timeout=3,
    )
    time.sleep(0.12)
    try:
        pyperclip.copy(saved)
    except Exception:
        pass


class _Bus(QObject):
    """Qt signals for crossing the pynput-thread → main-thread boundary."""
    show_rec  = pyqtSignal()
    show_tx   = pyqtSignal()
    show_text = pyqtSignal(str)   # final text to display briefly before paste
    do_hide   = pyqtSignal()


class Overlay(QWidget):
    """Dark pill-shaped floating window at screen bottom-centre.

    REC state: animated waveform bars driven by live audio RMS + pulsing red dot.
    TX state:  three bouncing dots while transcribing.
    """

    REC  = "rec"
    TX   = "tx"
    TEXT = "text"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(320, 68)

        self._state        = ""
        self._bars         = [0.2] * BAR_COUNT
        self._smooth       = [0.2] * BAR_COUNT
        self._frame        = 0
        self._display_text = ""
        self._text_alpha   = 0      # 0-255, fades in then out

        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(50)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_state(self, state: str, bars: list[float] | None = None) -> None:
        self._state = state
        if bars:
            self._bars = bars
        if state and not self.isVisible():
            self._reposition()
            self.show()

    def set_text(self, text: str) -> None:
        self._state        = self.TEXT
        self._text_alpha   = 0
        # Truncate to ~38 chars; keep word boundaries
        if len(text) > 38:
            cut = text[:36].rsplit(" ", 1)[0]
            self._display_text = cut + " …"
        else:
            self._display_text = text
        if not self.isVisible():
            self._reposition()
            self.show()

    def hide_overlay(self) -> None:
        self._state = ""
        self.hide()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            screen.height() - 130,
        )

    def _tick(self) -> None:
        self._frame += 1
        if self._state:
            for i in range(BAR_COUNT):
                self._smooth[i] += (self._bars[i] - self._smooth[i]) * 0.30
            if self._state == self.TEXT:
                self._text_alpha = min(255, self._text_alpha + 25)   # fade in
            self.update()

    # ── Paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, _):                                    # noqa: N802
        if not self._state:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 34, 34)
        p.setBrush(QBrush(QColor(14, 14, 14, 240)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

        if self._state == self.REC:
            self._paint_waveform(p)
        elif self._state == self.TX:
            self._paint_dots(p)
        else:
            self._paint_text(p)

    def _paint_waveform(self, p: QPainter) -> None:
        W, H  = self.width(), self.height()
        pad   = 22
        avail = W - 2 * pad
        gap   = 3
        bw    = (avail - (BAR_COUNT - 1) * gap) / BAR_COUNT
        cy    = H / 2
        maxH  = H - 18
        t     = self._frame * 0.06

        for i, v in enumerate(self._smooth):
            wobble = 0.08 * math.sin(t * 3.2 + i * 0.6)
            h = max(5.0, (v + wobble) * maxH)
            α = min(255, 160 + int(90 * i / BAR_COUNT))
            p.setBrush(QBrush(QColor(255, 255, 255, α)))
            p.setPen(Qt.PenStyle.NoPen)
            rx = pad + i * (bw + gap)
            p.drawRoundedRect(int(rx), int(cy - h / 2), max(1, int(bw)), int(h), 2, 2)

        # Pulsing red record indicator
        pulse = 0.5 + 0.5 * math.sin(self._frame * 0.18)
        r = int(4 + 2 * pulse)
        p.setBrush(QBrush(QColor(255, 55, 45)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(W - 16 - r, 10, r * 2, r * 2)

    def _paint_dots(self, p: QPainter) -> None:
        W, H    = self.width(), self.height()
        dr, gap = 6, 12
        total   = 3 * dr * 2 + 2 * gap
        x0      = (W - total) / 2

        for i in range(3):
            phase = self._frame * 0.20 - i * 1.15
            oy = math.sin(phase) * 7
            α  = int(100 + 155 * (math.sin(phase + 0.9) * 0.5 + 0.5))
            p.setBrush(QBrush(QColor(255, 255, 255, min(255, max(30, α)))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(
                int(x0 + i * (dr * 2 + gap)),
                int(H / 2 - dr + oy),
                dr * 2, dr * 2,
            )


    def _paint_text(self, p: QPainter) -> None:
        W, H = self.width(), self.height()
        α = self._text_alpha

        # Small checkmark dot on the left (green, like Wispr Flow's "done" state)
        p.setBrush(QBrush(QColor(52, 199, 89, α)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(18, H // 2 - 5, 10, 10)

        # Transcribed text
        font = QFont(".AppleSystemUIFont", 14)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, α))
        rect = self.rect().adjusted(38, 0, -14, 0)
        p.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._display_text)


def _draw_mic(color: QColor, dot: QColor | None = None) -> QIcon:
    """Mic silhouette in `color`; optional red recording dot top-right."""
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(8, 2, 6, 9, 3, 3)
    pen = QPen(color, 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawArc(5, 7, 12, 9, 0, -180 * 16)
    p.drawLine(11, 16, 11, 20)
    p.drawLine(8, 20, 14, 20)
    if dot:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dot))
        p.drawEllipse(15, 0, 7, 7)
    p.end()
    return QIcon(px)


def _tray_icon(state: str = "idle") -> QIcon:
    if state == "rec":
        return _draw_mic(QColor(255, 55, 45, 230), dot=QColor(255, 55, 45))
    if state == "tx":
        return _draw_mic(QColor(180, 180, 180, 180))
    return _draw_mic(QColor(255, 255, 255, 210))


class Speakr:
    """Main application — wires audio, transcription, UI, and hotkeys."""

    def __init__(self) -> None:
        self.qt = QApplication(sys.argv)
        self.qt.setQuitOnLastWindowClosed(False)

        self.bus      = _Bus()
        self.ui       = Overlay()
        self.rec      = AudioRecorder()
        self.polisher = Polisher()      # starts grammar engine in background
        self.tx       = Transcriber()   # blocks until Whisper model loads (parallel)

        self._recording   = False
        self._target_app  = ""

        # Cross-thread signal wiring (auto queued — thread-safe)
        self.bus.show_rec.connect(self._on_rec)
        self.bus.show_tx.connect(self._on_tx)
        self.bus.show_text.connect(self.ui.set_text)
        self.bus.do_hide.connect(self._on_hide)

        # Timer: push fresh bar heights while recording (main thread)
        wt = QTimer()
        wt.timeout.connect(self._refresh_bars)
        wt.start(55)
        self._wt = wt

        # System tray
        tray = QSystemTrayIcon(_tray_icon("idle"), self.qt)
        m = QMenu()
        m.addAction("Speakr  —  Hold ⌥ Right to dictate")
        m.addSeparator()
        m.addAction("Quit", self.qt.quit)
        tray.setContextMenu(m)
        tray.show()
        self._tray = tray

        # Global hotkey listener in daemon thread
        kbl = kb.Listener(on_press=self._kp, on_release=self._kr)
        kbl.daemon = True
        kbl.start()
        self._kbl = kbl

        self._check_accessibility()

    # ── Tray state helpers (main thread) ──────────────────────────────────────

    def _on_rec(self) -> None:
        self._tray.setIcon(_tray_icon("rec"))
        self._tray.setToolTip("Speakr — recording…")
        self.ui.set_state(Overlay.REC)

    def _on_tx(self) -> None:
        self._tray.setIcon(_tray_icon("tx"))
        self._tray.setToolTip("Speakr — transcribing…")
        self.ui.set_state(Overlay.TX)

    def _on_hide(self) -> None:
        self._tray.setIcon(_tray_icon("idle"))
        self._tray.setToolTip("Speakr — Hold ⌥ Right to dictate")
        self.ui.hide_overlay()

    # ── Accessibility check ────────────────────────────────────────────────────

    @staticmethod
    def _check_accessibility() -> None:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            capture_output=True, timeout=3,
        )
        if r.returncode != 0:
            print("\n⚠️  Hotkey won't work until you grant Accessibility permission:")
            print("   System Settings → Privacy & Security → Accessibility")
            print("   Click + and add your terminal app (Terminal, iTerm2, Warp…)\n")
        else:
            print("✓  Accessibility OK — hotkey active.\n")

    # ── Hotkey callbacks (pynput thread) ───────────────────────────────────────

    def _kp(self, key) -> None:
        if key == HOTKEY and not self._recording:
            self._recording = True
            try:
                r = subprocess.run(
                    ["osascript", "-e",
                     "tell application \"System Events\" to get name of first process whose frontmost is true"],
                    capture_output=True, text=True, timeout=2,
                )
                self._target_app = r.stdout.strip()
            except Exception:
                self._target_app = ""
            _play("Tink")
            self.rec.start()
            self.bus.show_rec.emit()

    def _kr(self, key) -> None:
        if key == HOTKEY and self._recording:
            self._recording = False
            audio, dur = self.rec.stop()
            if dur < MIN_SEC:
                self.bus.do_hide.emit()
                return
            self.bus.show_tx.emit()
            threading.Thread(target=self._worker, args=(audio,), daemon=True).start()

    # ── Worker thread (transcription + paste) ──────────────────────────────────

    def _worker(self, audio: np.ndarray) -> None:
        try:
            text = self.tx.run(audio)
            if not text:
                if not SILENT:
                    print("→  (nothing detected — speak while holding ⌥)", flush=True)
                return

            text = self.polisher.polish(text)
            if not SILENT:
                print(f"→  {text}", flush=True)

            self.bus.show_text.emit(text)
            time.sleep(0.8)           # brief preview in overlay
            _paste(text, self._target_app)
            _play("Pop")
            time.sleep(0.25)
        except Exception as exc:
            if not SILENT:
                print(f"⚠  {exc}", flush=True)
        finally:
            self.bus.do_hide.emit()   # always hide, even on crash

    # ── Main-thread helpers ────────────────────────────────────────────────────

    def _refresh_bars(self) -> None:
        if self._recording:
            self.ui.set_state(Overlay.REC, self.rec.bar_levels())

    def run(self) -> None:
        sys.exit(self.qt.exec())


if __name__ == "__main__":
    Speakr().run()
