import sys
import numpy as np
import pytest

sys.path.insert(0, "/Users/eashankarnani/Documents/Speakr")


# ── AudioRecorder tests ───────────────────────────────────────────────────────

def test_bar_levels_returns_correct_count():
    from speakr import AudioRecorder, BAR_COUNT
    rec = AudioRecorder()
    assert len(rec.bar_levels()) == BAR_COUNT


def test_bar_levels_normalised_0_to_1():
    from speakr import AudioRecorder
    rec = AudioRecorder()
    with rec._lock:
        rec._levels = [0.01, 0.05, 0.10, 0.20]
    levels = rec.bar_levels()
    assert all(0.0 <= v <= 1.0 for v in levels)


def test_bar_levels_high_rms_capped_at_1():
    from speakr import AudioRecorder
    rec = AudioRecorder()
    with rec._lock:
        rec._levels = [999.0] * 5
    levels = rec.bar_levels()
    assert all(v <= 1.0 for v in levels)


def test_stop_returns_tuple_audio_duration():
    from speakr import AudioRecorder, SAMPLE_RATE
    rec = AudioRecorder()
    fake = np.zeros((SAMPLE_RATE, 1), dtype="float32")
    with rec._lock:
        rec._chunks = [fake]
    audio, dur = rec.stop()
    assert isinstance(audio, np.ndarray)
    assert abs(dur - 1.0) < 0.01


# ── _paste tests ──────────────────────────────────────────────────────────────

def test_paste_sets_clipboard_content(monkeypatch):
    import subprocess as _sp
    from speakr import _paste
    import pyperclip

    clipboard_written = []
    monkeypatch.setattr(pyperclip, "copy", lambda t: clipboard_written.append(t))
    monkeypatch.setattr(pyperclip, "paste", lambda: "previous_content")
    monkeypatch.setattr(_sp, "run", lambda *a, **kw: None)

    _paste("hello world")

    assert "hello world" in clipboard_written
    assert "previous_content" in clipboard_written


def test_paste_restores_clipboard_on_empty_previous(monkeypatch):
    import subprocess as _sp
    from speakr import _paste
    import pyperclip

    clipboard_written = []
    monkeypatch.setattr(pyperclip, "copy", lambda t: clipboard_written.append(t))
    monkeypatch.setattr(pyperclip, "paste", lambda: "")
    monkeypatch.setattr(_sp, "run", lambda *a, **kw: None)

    _paste("test")
    assert clipboard_written[0] == "test"
