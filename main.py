"""Hindi Alphabet Learning App

[Prompt: TASK - Desktop app to assist with the learning of the Hindi alphabet]

This minimal PyQt6 application shows a Hindi character, its transliteration,
and an English approximation, with Next/Previous navigation and a Play button
that uses TTS for audio playback.

Implementation notes:
- Type hints and Google-style docstrings are included.
- Logging provides lightweight diagnostics.
- Audio playback now uses TTS via pyttsx3 on macOS (Sequoia).

Dependencies (add to requirements.txt):
- PyQt6

Dev deps (add to requirements-dev.txt):
- pytest
- pytest-cov
- mypy (optional if using provided mypy config)

<a href="https://www.flaticon.com/free-icons/listen" title="listen icons">Listen icons created by Freepik - Flaticon</a>
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import unicodedata
import html
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, cast

import yaml
# Optional advanced regex for grapheme cluster segmentation
try:
    import regex as _REGEX  # type: ignore
except Exception:
    _REGEX = None
from PyQt6 import QtCore
from PyQt6 import uic
from PyQt6.QtCore import QSize, QPoint, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPen, QFontMetrics
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QWidget,
    QPushButton,
    QLabel,
    QSlider,
    QToolButton,
    QRadioButton,
    QCheckBox,
    QSizePolicy,
)

from settings import (CURRENT_TTS_RATE,
                      TTS_REPEATS,
                      TTS_DELAY,
                      CURRENT_AUTO_PLAY_SOUND,
                      CURRENT_RADIO_BUTTON,
                      CONTINUOUS)

# ----------------------------------------------------------------------------
# [Prompt: IMPLEMENTATION GUIDELINES] Logging configuration
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("hindi_app")


# ----------------------------------------------------------------------------
# Helper for slugifying example fields for filenames
# ----------------------------------------------------------------------------
def _slug_filename(text: str) -> str:
    """Convert a label into a lowercase filename-friendly slug with underscores.
    Keeps ASCII letters/numbers/underscore; collapses spaces/dashes to underscores.
    """
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s.lower()


# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class HindiLetter:
    """Represents a single Hindi letter/phoneme entry."""
    symbol: str
    pronunciation: str
    english_equiv: str
    letter_type: Optional[str] = None  # "vowel" | "consonant"
    dependent_form: Optional[str] = None
    hint: Optional[str] = None
    example: Optional[str] = None      # full example line, e.g., "इंद्रधनुष (indradhanush) – Rainbow"
    example_translit: Optional[str] = None  # e.g., "indradhanush"
    example_noun: Optional[str] = None      # e.g., "rainbow"
    dependent_form_example: Optional[str] = None  # e.g., "का (kā) – Crow"


class ExampleMatraPointer(QWidget):
    """Draws a small arrow under the cluster containing the given matra in the left Hindi part of an example."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._left_text: str = ""
        self._right_text: str = ""
        self._dep: str = ""
        self._font = self.font()
        self.setMinimumHeight(22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._alignment = Qt.AlignmentFlag.AlignHCenter  # default; can be overridden

    def set_alignment(self, align: Qt.AlignmentFlag) -> None:
        self._alignment = align
        self.update()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        try:
            fm = QFontMetrics(self._font)
            # Width approx equal to left text width; height ~ 22 px for arrow room
            w = fm.horizontalAdvance(self._left_text or " ") + 8
            return QSize(max(60, w), 22)
        except Exception:
            return QSize(120, 22)

    def set_example(self, example: str, dep: str, base_font: Optional[QFont] = None) -> None:
        parts = re.split(r"\s+[\u2013-]\s+", example, maxsplit=1)
        self._left_text = parts[0] if parts else example
        self._right_text = parts[1] if len(parts) > 1 else ""
        self._dep = dep or ""
        if base_font:
            self._font = base_font
        LOGGER.debug("MatraPointer set_example: left='%s' dep='%s'", self._left_text, self._dep)
        self.updateGeometry()
        self.update()

    def clear(self) -> None:
        self._left_text, self._right_text, self._dep = "", "", ""
        self.update()

    def _cluster_positions(self, text: str) -> list[tuple[int, int]]:
        """Return (start,end) indices for grapheme clusters in text using regex \\X when available."""
        if _REGEX is None:
            return [(i, i + 1) for i in range(len(text))]
        try:
            spans = []
            for m in _REGEX.finditer(r"\X", text):
                spans.append((m.start(), m.end()))
            return spans
        except Exception:
            return [(i, i + 1) for i in range(len(text))]

    def paintEvent(self, ev) -> None:  # type: ignore[override]
        super().paintEvent(ev)
        if not self._left_text or not self._dep:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setFont(self._font)

            try:
                left = unicodedata.normalize("NFC", self._left_text)
            except Exception:
                left = self._left_text

            fm = painter.fontMetrics()
            clusters = self._cluster_positions(left)

            target_span: Optional[tuple[int, int]] = None
            for (a, b) in clusters:
                if self._dep in left[a:b]:
                    target_span = (a, b)
                    break

            if not target_span:
                LOGGER.debug("MatraPointer: no target span for dep='%s' in '%s'", self._dep, left)
                return

            start_idx, end_idx = target_span
            prefix = left[:start_idx]
            cluster_text = left[start_idx:end_idx]
            try:
                prefix_w = fm.horizontalAdvance(prefix)
                cluster_w = fm.horizontalAdvance(cluster_text)
                total_w = fm.horizontalAdvance(left)
            except Exception:
                prefix_w = len(prefix) * 10
                cluster_w = max(10, len(cluster_text) * 10)
                total_w = max(10, len(left) * 10)

            # Base offset to mirror label alignment (left/center/right)
            base_x = 0
            try:
                if self._alignment & Qt.AlignmentFlag.AlignHCenter:
                    base_x = max(0, (self.width() - total_w) // 2)
                elif self._alignment & Qt.AlignmentFlag.AlignRight:
                    base_x = max(0, self.width() - total_w)
                else:
                    base_x = 0
            except Exception:
                base_x = 0

            center_x = base_x + prefix_w + (cluster_w / 2)
            # Draw the arrow closer to the top of this thin container to reduce gap to the label above
            y = self.height() - 16
            arrow_h = 6
            pen = QPen(QColor("#0A5BD3"))
            pen.setWidth(2)
            painter.setPen(pen)

            # Optional baseline for debugging visibility
            if os.environ.get("DEBUG_ARROW"):
                painter.setPen(QPen(QColor("#A0A0A0"), 1, Qt.PenStyle.DotLine))
                painter.drawLine(0, y, self.width(), y)
                painter.setPen(pen)

            painter.drawLine(int(center_x), y, int(center_x), y - arrow_h)
            painter.drawLine(int(center_x), y - arrow_h, int(center_x) - 4, y - arrow_h + 4)
            painter.drawLine(int(center_x), y - arrow_h, int(center_x) + 4, y - arrow_h + 4)

            LOGGER.debug("MatraPointer: arrow at x=%.1f, y=%d, cluster='%s'", center_x, y, cluster_text)
        finally:
            painter.end()


class HindiTTSPlayerMac:
    """macOS-native TTS using NSSpeechSynthesizer (PyObjC), async and reliable.

    Requires: pyobjc (install with: `python3 -m pip install pyobjc`)
    """

    def __init__(self, rate: int = 200, volume: float = 1.0) -> None:
        try:
            from AppKit import NSSpeechSynthesizer  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("PyObjC not available for macOS TTS") from exc

        self._NSSpeechSynthesizer = NSSpeechSynthesizer
        self._synth = NSSpeechSynthesizer.alloc().initWithVoice_(None)
        try:
            self._synth.setRate_(rate)
        except Exception:
            pass
        try:
            self._synth.setVolume_(volume)
        except Exception:
            pass
        self._voice_id: Optional[str] = None
        self._select_hindi_voice()

    def set_rate(self, rate: int) -> None:
        try:
            self._synth.setRate_(rate)
        except Exception:
            pass

    def _select_hindi_voice(self) -> None:
        try:
            voices = self._NSSpeechSynthesizer.availableVoices()
            preferred = [
                "com.apple.speech.synthesis.voice.lekha",
                "com.apple.speech.synthesis.voice.madhur",
            ]
            for pid in preferred:
                if pid in voices:
                    self._synth.setVoice_(pid)
                    self._voice_id = pid
                    LOGGER.info("Selected macOS TTS voice: %s", pid)
                    return
            # Fallback: first Hindi-like voice
            for vid in voices:
                if "hi" in vid.lower() or "hindi" in vid.lower():
                    self._synth.setVoice_(vid)
                    self._voice_id = vid
                    LOGGER.info("Selected macOS TTS voice: %s", vid)
                    return
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not select macOS Hindi voice: %s", exc)

    @staticmethod
    def _has_devanagari(text: str) -> bool:
        return any('\u0900' <= ch <= '\u097F' for ch in text)

    def play_for(self, letter: HindiLetter) -> None:
        text = letter.symbol
        speak_text = text if (self._voice_id or not self._has_devanagari(text)) else letter.pronunciation
        try:
            # Stop any in-progress utterance, then speak asynchronously
            self._synth.stopSpeaking()
            self._synth.startSpeakingString_(speak_text)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("macOS TTS failed: %s", exc)

    def is_speaking(self) -> bool:
        """Return True while the system TTS is speaking (macOS)."""
        try:
            return bool(self._synth.isSpeaking())
        except Exception:
            return False


class HindiTTSPlayer:
    """Speak letters using system TTS via pyttsx3 (offline).

    On macOS, pyttsx3 uses NSSpeechSynthesizer, so Hindi voices like
    "Lekha" or "Madhur" (hi-IN) can be selected if installed.
    """

    def __init__(self, rate: int = 150, volume: float = 1.0) -> None:
        import pyttsx3  # local import to avoid hard dependency if unused
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)
        self._voice_id: Optional[str] = None  # remember chosen voice
        # Try to select a Hindi voice automatically on macOS.
        self._maybe_select_hindi_voice()

    def set_rate(self, rate: int) -> None:
        try:
            self._engine.setProperty("rate", int(rate))
        except Exception:
            pass

    def _maybe_select_hindi_voice(self) -> None:
        try:
            voices = self._engine.getProperty("voices")

            def is_hindi(v) -> bool:
                langs = getattr(v, "languages", []) or []
                langs_str = [bytes(l).decode(errors="ignore") if isinstance(l, (bytes, bytearray)) else str(l) for l in
                             langs]
                return any("hi" in s.lower() for s in langs_str) or "hi" in v.id.lower() or "hindi" in v.name.lower()

            preferred_ids = [
                "com.apple.speech.synthesis.voice.lekha",
                "com.apple.speech.synthesis.voice.madhur",
            ]
            by_id = {v.id: v for v in voices}
            for pid in preferred_ids:
                if pid in by_id:
                    self._engine.setProperty("voice", pid)
                    self._voice_id = pid
                    LOGGER.info("Selected TTS voice: %s", self._voice_id)
                    return
            for v in voices:
                if is_hindi(v):
                    self._engine.setProperty("voice", v.id)
                    self._voice_id = v.id
                    LOGGER.info("Selected TTS voice: %s", self._voice_id)
                    return
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not auto-select Hindi voice: %s", exc)

    @staticmethod
    def _has_devanagari(text: str) -> bool:
        return any('\u0900' <= ch <= '\u097F' for ch in text)

    def _reinit_engine(self) -> None:
        """Recreate the TTS engine and restore voice/settings (macOS nsss can get stuck)."""
        import pyttsx3
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", int(self._engine.getProperty("rate") or 150))
        self._engine.setProperty("volume", float(self._engine.getProperty("volume") or 1.0))
        if self._voice_id:
            try:
                self._engine.setProperty("voice", self._voice_id)
            except Exception:
                # If the stored voice id fails, try auto-select again
                self._maybe_select_hindi_voice()
        else:
            self._maybe_select_hindi_voice()

    def is_speaking(self) -> bool:
        """Return True if the engine is currently speaking.
        Note: runAndWait() blocks, so this will usually be False by the time we check.
        """
        try:
            return bool(getattr(self._engine, "isBusy", lambda: False)())
        except Exception:
            return False

    def play_for(self, letter: HindiLetter) -> None:
        text = letter.symbol
        speak_text = text
        # If we don't have a stored Hindi-capable voice and the text is Devanagari,
        # fall back to transliteration to avoid silence on non-Hindi system voices.
        if self._voice_id is None and self._has_devanagari(text):
            LOGGER.info("No Hindi voice selected; falling back to pronunciation '%s'", letter.pronunciation)
            speak_text = letter.pronunciation
        try:
            try:
                self._engine.stop()
            except Exception:
                pass
            self._engine.say(speak_text)
            self._engine.runAndWait()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("TTS encountered an error, reinitializing engine: %s", exc)
            self._reinit_engine()
            try:
                self._engine.stop()
            except Exception:
                pass
            try:
                self._engine.say(speak_text)
                self._engine.runAndWait()
            except Exception as exc2:  # noqa: BLE001
                LOGGER.exception("TTS failed after reinit: %s", exc2)


# ----------------------------------------------------------------------------
# YAML loader for Hindi letters (for data/letters.yaml)
# ----------------------------------------------------------------------------
def _load_letters_from_yaml(path: Path) -> List[HindiLetter]:
    """Load letters from data/letters.yaml (explicit schema) and return HindiLetter list.

    Expected YAML schema:
    letters:
      - symbol: "अ"
        type: "vowel"            # not used directly here; UI filter uses index ranges for now
        dependent_form: "..."     # optional
        pronunciation: "a"
        english_approx: "u in umbrella"
        hint: "Short neutral vowel"
        example: "कमल (kamal) – Lotus"
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to read %s: %s", path, exc)
        return []

    items = []
    if isinstance(raw, dict) and isinstance(raw.get("letters"), list):
        items = raw["letters"]
    elif isinstance(raw, list):
        # allow bare list for flexibility
        items = raw
    else:
        LOGGER.warning("letters.yaml does not contain 'letters' list; got %s", type(raw).__name__)
        return []

    out: List[HindiLetter] = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            LOGGER.warning("letters.yaml item %d is not a mapping; skipping", idx)
            continue
        symbol = str(it.get("symbol") or "").strip()
        pronunciation = str(it.get("pronunciation") or "").strip()
        english_approx = str(it.get("english_approx") or "").strip()
        hint = str(it.get("hint") or "").strip()
        letter_type = str(it.get("type") or "").strip().lower() or None
        dependent_form = str(it.get("dependent_form") or "").strip()
        dependent_form_example = str(it.get("dependent_form_example") or "").strip()

        # Choose label: prefer english_approx; fall back to hint
        try:
            english_approx_label = english_approx
            hint_label = hint
        except:
            pass

        example = str(it.get("example") or "").strip()
        example_translit = None
        example_noun = None
        if example:
            m = re.match(r"^(.*)\(([^)]+)\)\s*[-–]\s*(.*)$", example)
            if m:
                example_word, translit, noun = m.groups()
                example_translit = translit.strip()
                example_noun = noun.strip().lower()

        # Slugify for filesystem safety
        if example_noun:
            example_noun = _slug_filename(example_noun)
        if example_translit:
            example_translit = _slug_filename(example_translit)

        if not symbol or not pronunciation or not english_approx_label or not hint_label:
            LOGGER.warning(
                "Invalid item at %d: symbol=%r, pronunciation=%r, english/hint=%r; skipping",
                idx, symbol, pronunciation, english_approx_label, hint_label
            )
            continue

        out.append(HindiLetter(
            symbol=symbol,
            pronunciation=pronunciation,
            english_equiv=english_approx_label,
            letter_type=letter_type,
            dependent_form=dependent_form or None,
            hint=hint_label or None,
            example=example if example else None,
            example_translit=example_translit,
            example_noun=example_noun,
            dependent_form_example=dependent_form_example or None,
        ))
    LOGGER.info("Loaded %d letters from %s", len(out), path.name)
    return out


class MainWindow(QMainWindow):
    def _wait_until_silent(self, token: int, cont) -> None:
        """Poll the TTS engine until it finishes, then call cont()."""
        if token != getattr(self, "_play_token", 0):
            return
        try:
            speaking = False
            if hasattr(self, "audio_player") and hasattr(self.audio_player, "is_speaking"):
                try:
                    speaking = bool(self.audio_player.is_speaking())
                except Exception:
                    speaking = False
            if speaking:
                QtCore.QTimer.singleShot(100, lambda: self._wait_until_silent(token, cont))
            else:
                cont()
        except Exception:
            cont()

    def __init__(self, letters: List[HindiLetter], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hindi Alphabet Helper")
        self.letters = letters
        self.index = 0
        # Prefer macOS-native TTS when on macOS; fall back to pyttsx3 otherwise.
        if sys.platform == "darwin":
            try:
                self.audio_player = HindiTTSPlayerMac(rate=CURRENT_TTS_RATE)
            except Exception as _exc:
                LOGGER.warning("macOS TTS unavailable (%s); falling back to pyttsx3", _exc)
                self.audio_player = HindiTTSPlayer(rate=CURRENT_TTS_RATE)
        else:
            self.audio_player = HindiTTSPlayer(rate=CURRENT_TTS_RATE)

        # Build UI in code to ensure an immediate run; swap to uic.loadUi later if desired.
        uic.loadUi("ui/new_form.ui", self)
        # Bind critical widgets early so they exist before styling/logic
        self.image_label = cast(QLabel, self.findChild(QLabel, "imagePlaceholder"))
        self.status_hint = cast(QLabel, self.findChild(QLabel, "statusHint"))


        # Ensure settingsDock starts hidden
        dock = self.findChild(QWidget, "settingsDock")
        if dock is not None:
            dock.hide()

        # Ensure transparent background and predictable scaling for image area
        if self.image_label is not None:
            try:
                self.image_label.setStyleSheet("background-color: transparent;")
                self.image_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                self.image_label.setScaledContents(False)  # we'll scale manually to preserve aspect ratio
                self.image_label.setVisible(True)
                self._show_placeholder_image()
            except Exception:
                pass

        # Choose a caption label (prefer a dedicated one if the UI has it; fall back to statusHint)
        self.caption_label = cast(QLabel, self.findChild(QLabel, "imageCaption")) or self.status_hint
        if self.caption_label is not None:
            try:
                self.caption_label.setWordWrap(True)
                self.caption_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                self.caption_label.setVisible(True)
            except Exception:
                pass

        # Label under the example caption to explain the dependent form
        self.dependent_form_label = cast(QLabel, self.findChild(QLabel, "dependentFormLabel"))
        if self.dependent_form_label is not None:
            try:
                self.dependent_form_label.setWordWrap(True)
                self.dependent_form_label.setTextFormat(Qt.TextFormat.RichText)
                self.dependent_form_label.setVisible(False)
            except Exception:
                pass

        # Matra pointer: a tiny indicator under the example/caption
        self.matra_pointer = ExampleMatraPointer(self)
        self.matra_pointer.setVisible(False)
        try:
            container = self.findChild(QWidget, "matraPointerContainer")
            if container is not None and container.layout() is not None:
                container.layout().addWidget(self.matra_pointer)
                self.matra_pointer.setVisible(True)
                self.matra_pointer.updateGeometry()
                # Match pointer font and alignment to dependentFormLabel if available
                if self.dependent_form_label is not None:
                    try:
                        self.matra_pointer.set_alignment(self.dependent_form_label.alignment())
                        self.matra_pointer.setFont(self.dependent_form_label.font())
                    except Exception:
                        pass
            else:
                LOGGER.warning("matraPointerContainer not found; arrow may not display.")
        except Exception as exc:
            LOGGER.warning("Failed to insert matra pointer into container: %s", exc)


        # Bind typed Designer widgets for static analysis and autocompletion
        self.prev_btn = cast(QPushButton, self.findChild(QPushButton, "prev_btn"))
        self.play_btn = cast(QPushButton, self.findChild(QPushButton, "play_btn"))
        # After: self.play_btn = cast(QPushButton, self.findChild(QPushButton, "play_btn"))
        self._debug_play_icon()
        self.next_btn = cast(QPushButton, self.findChild(QPushButton, "next_btn"))
        # --- Settings button (⚙️)
        self.btn_settings = cast(QToolButton, self.findChild(QToolButton, "btnSettings"))
        if self.btn_settings is not None:
            self.btn_settings.clicked.connect(self.on_settings_clicked)

        self.symbol_label = cast(QLabel, self.findChild(QLabel, "symbolLabel"))
        self.pron_label = cast(QLabel, self.findChild(QLabel, "pronLabel"))
        self.english_equiv_label = cast(QLabel, self.findChild(QLabel, "englishEquivLabel"))
        self.hint_label = cast(QLabel, self.findChild(QLabel, "hintLabel"))
        self.category_label = cast(QLabel, self.findChild(QLabel, "categoryLabel"))

        self.slider_rate = cast(QSlider, self.findChild(QSlider, "sliderRate"))
        self.lbl_rate_value = cast(QLabel, self.findChild(QLabel, "lblRateValue"))
        self.btn_slower = cast(QToolButton, self.findChild(QToolButton, "btnSlower"))
        self.btn_faster = cast(QToolButton, self.findChild(QToolButton, "btnFaster"))

        # --- Auto-play interval controls (settings dock)
        self.slider_interval = cast(QSlider, self.findChild(QSlider, "sliderInterval"))
        self.lbl_interval_value = cast(QLabel, self.findChild(QLabel, "lblIntervalValue"))
        if self.slider_interval is not None:
            try:
                val = int(self.slider_interval.value())
            except Exception:
                val = 2

            # Determine unit suffix from the label's current text (e.g., "2 sec" -> unit " sec")
            self._interval_unit = " sec"
            try:
                if self.lbl_interval_value is not None:
                    current_txt = self.lbl_interval_value.text() or ""
                    m = re.match(r"\s*\d+\s*(.*)", current_txt)
                    if m and m.group(1).strip():
                        # keep a leading space before the unit for readability
                        self._interval_unit = " " + m.group(1).strip()
            except Exception:
                pass

            # Set initial label using discovered unit
            if self.lbl_interval_value is not None:
                self.lbl_interval_value.setText(f"{val}{self._interval_unit}")

            # Use slider value as the delay between letters (ms) in auto-play
            self._continuous_delay_ms = int(val) * 1000
            self.slider_interval.valueChanged.connect(self.on_interval_changed)

        # --- Filtering radio buttons
        self.rb_vowels = cast(QRadioButton, self.findChild(QRadioButton, "rbVowels"))
        self.rb_consonants = cast(QRadioButton, self.findChild(QRadioButton, "rbConsonants"))
        self.rb_both = cast(QRadioButton, self.findChild(QRadioButton, "rbBoth"))

        # Auto-play checkbox (wired to settings.CONTINUOUS)
        self.cb_autoplay = cast(QCheckBox, self.findChild(QCheckBox, "cbAutoPlay"))
        if self.cb_autoplay is not None:
            self.cb_autoplay.setChecked(bool(CONTINUOUS))
            self.cb_autoplay.stateChanged.connect(self.on_autoplay_toggled)
            self._apply_autoplay_ui(bool(CONTINUOUS))

        self._bind()
        # Initialize radio selection from settings.CURRENT_RADIO_BUTTON
        initial_choice = (str(CURRENT_RADIO_BUTTON).strip().lower() if CURRENT_RADIO_BUTTON else "both")
        if initial_choice == "vowels":
            if self.rb_vowels is not None:
                self.rb_vowels.setChecked(True)
        elif initial_choice == "consonants":
            if self.rb_consonants is not None:
                self.rb_consonants.setChecked(True)
        else:
            if self.rb_both is not None:
                self.rb_both.setChecked(True)

        # Initialize filter mode before first refresh
        self.filter_mode: str = "both"
        # Initialize filter mode before first refresh (from settings)
        if initial_choice == "vowels":
            self.filter_mode = "vowels"
        elif initial_choice == "consonants":
            self.filter_mode = "consonants"
        else:
            self.filter_mode = "both"

        # Force starting index to the first item of the selected set
        if self.filter_mode == "vowels":
            self.index = 0
        elif self.filter_mode == "consonants":
            self.index = 13  # first consonant
        else:  # both
            self.index = 0

        # Ensure starting index is visible under the current filter
        if not self._is_index_visible(self.index):
            nxt = self._next_visible_index(self.index)
            if nxt is not None:
                self.index = nxt
            else:
                prv = self._prev_visible_index(self.index)
                if prv is not None:
                    self.index = prv

        # Connect radio buttons
        if self.rb_vowels is not None:
            self.rb_vowels.toggled.connect(lambda checked: checked and self.on_filter_changed("vowels"))
        if self.rb_consonants is not None:
            self.rb_consonants.toggled.connect(lambda checked: checked and self.on_filter_changed("consonants"))
        if self.rb_both is not None:
            self.rb_both.toggled.connect(lambda checked: checked and self.on_filter_changed("both"))

        # Now safe to refresh UI (filter_mode exists)
        self._refresh()
        self._play_token = 0  # increments each Play click to cancel prior schedules

        # --- User prefs: load persisted TTS rate, initialize slider/label, wire signal
        self._prefs_path = Path("user_prefs.json")
        current_rate = int(CURRENT_TTS_RATE)
        try:
            if self._prefs_path.exists():
                with self._prefs_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "tts_rate" in data:
                        current_rate = int(data.get("tts_rate", current_rate))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not load user_prefs.json: %s", exc)
        # Initialize UI widgets
        if self.slider_rate is not None:
            self.slider_rate.setValue(current_rate)
        if self.lbl_rate_value is not None:
            self.lbl_rate_value.setText(str(current_rate))
        # Apply to current audio engine
        try:
            if hasattr(self.audio_player, "set_rate"):
                self.audio_player.set_rate(current_rate)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to apply TTS rate: %s", exc)
        # Ensure step buttons enabled state matches current value
        self._update_rate_controls_enabled(current_rate)
        # Connect signal
        if self.slider_rate is not None:
            self.slider_rate.setSingleStep(20)
            self.slider_rate.setPageStep(20)
            self.slider_rate.valueChanged.connect(self.on_rate_changed)
        if self.btn_slower is not None:
            self.btn_slower.clicked.connect(lambda: self.on_rate_step(-20))
        if self.btn_faster is not None:
            self.btn_faster.clicked.connect(lambda: self.on_rate_step(+20))
        try:
            if self.cb_autoplay is not None and self.cb_autoplay.isChecked():
                self._apply_autoplay_ui(True)
        except Exception:
            pass
            # Start continuous playback at launch if configured
        try:
            if bool(CONTINUOUS):
                self._start_continuous()
        except Exception:
            pass

    def on_rate_changed(self, value: int) -> None:
        """Handle changes from the Rate slider: update label, engine, and persist.

        Enforces 20-step increments by snapping and updating the slider value if needed.
        """
        try:
            if self.slider_rate is None:
                return
            snapped = self._snap_rate(int(value))
            # If the slider landed between steps (e.g., mouse drag), snap it.
            if snapped != int(value):
                self.slider_rate.blockSignals(True)
                self.slider_rate.setValue(snapped)
                self.slider_rate.blockSignals(False)
            final_value = snapped
            # Update UI label
            if self.lbl_rate_value is not None:
                self.lbl_rate_value.setText(str(final_value))
            # Apply to current audio engine
            if hasattr(self.audio_player, "set_rate"):
                self.audio_player.set_rate(final_value)
            # Persist to user_prefs.json
            data = {}
            if getattr(self, "_prefs_path", None) and self._prefs_path.exists():
                try:
                    with self._prefs_path.open("r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                        if not isinstance(data, dict):
                            data = {}
                except Exception:
                    data = {}
            data["tts_rate"] = int(final_value)
            try:
                with self._prefs_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Could not save user_prefs.json: %s", exc)
            # Enable/disable step buttons appropriately
            self._update_rate_controls_enabled(final_value)
            # Replay current letter using the updated rate after a delay (respect TTS_REPEATS)
            try:
                self._play_token = getattr(self, "_play_token", 0) + 1
                token = self._play_token
                repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
                self._set_busy(True)
                QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(repeats, token))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to replay after rate change: %s", exc)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("on_rate_changed failed: %s", exc)

    def on_rate_step(self, delta: int) -> None:
        """Increment/decrement the rate by a fixed delta (e.g., ±20), clamped to slider range.

        Setting the slider value will trigger on_rate_changed(), which updates TTS and persists.
        """
        if self.slider_rate is None:
            return
        try:
            cur = int(self.slider_rate.value())
            new_val = cur + int(delta)
            lo, hi = int(self.slider_rate.minimum()), int(self.slider_rate.maximum())
            if new_val < lo:
                new_val = lo
            elif new_val > hi:
                new_val = hi
            if new_val != cur:
                self.slider_rate.setValue(new_val)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("on_rate_step failed: %s", exc)

    def on_interval_changed(self, value: int) -> None:
        """Update the interval label and the continuous delay (ms) used in auto-play."""
        try:
            secs = int(value)
            unit = getattr(self, "_interval_unit", " sec")
            if self.lbl_interval_value is not None:
                self.lbl_interval_value.setText(f"{secs}{unit}")
            # Apply to continuous playback timing
            self._continuous_delay_ms = max(0, secs * 1000)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to update interval: %s", exc)

    def _snap_rate(self, value: int) -> int:
        """Snap an arbitrary rate to the nearest multiple of 20 within slider bounds."""
        if self.slider_rate is None:
            return value
        step = 20
        lo, hi = int(self.slider_rate.minimum()), int(self.slider_rate.maximum())
        snapped = int(round(value / step) * step)
        if snapped < lo:
            snapped = lo
        if snapped > hi:
            snapped = hi
        return snapped

    def _update_rate_controls_enabled(self, value: int) -> None:
        """Enable/disable Slower/Faster based on current value and slider bounds."""
        if self.slider_rate is None:
            return
        lo, hi = int(self.slider_rate.minimum()), int(self.slider_rate.maximum())
        if hasattr(self, "btn_slower") and self.btn_slower is not None:
            self.btn_slower.setEnabled(value > lo)
        if hasattr(self, "btn_faster") and self.btn_faster is not None:
            self.btn_faster.setEnabled(value < hi)

    def _is_index_visible(self, i: int) -> bool:
        if self.filter_mode == "vowels":
            return i < 13
        if self.filter_mode == "consonants":
            return i >= 13
        return True

    def _next_visible_index(self, start: int) -> Optional[int]:
        i = start + 1
        n = len(self.letters)
        while i < n:
            if self._is_index_visible(i):
                return i
            i += 1
        return None

    def _prev_visible_index(self, start: int) -> Optional[int]:
        i = start - 1
        while i >= 0:
            if self._is_index_visible(i):
                return i
            i -= 1
        return None

    def _persist_radio_choice(self, choice: str) -> None:
        """Persist CURRENT_RADIO_BUTTON in settings.py to the given choice (Title case)."""
        try:
            settings_path = Path("settings.py")
            if not settings_path.exists():
                return
            txt = settings_path.read_text(encoding="utf-8")
            # Normalize the input and build the new assignment line
            choice_norm = choice.strip().lower()
            if choice_norm not in {"vowels", "consonants", "both"}:
                choice_norm = "both"
            new_line = f'CURRENT_RADIO_BUTTON = "{choice_norm.capitalize()}"'
            # Replace existing assignment or append if missing
            pattern = re.compile(r'^\s*CURRENT_RADIO_BUTTON\s*=\s*[\'"](Vowels|Consonants|Both)[\'"]\s*$', re.MULTILINE)
            if pattern.search(txt):
                txt_new = pattern.sub(new_line, txt)
            else:
                sep = "\n" if not txt.endswith("\n") else ""
                txt_new = txt + f"{sep}{new_line}\n"
            if txt_new != txt:
                settings_path.write_text(txt_new, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not persist CURRENT_RADIO_BUTTON: %s", exc)

    def _show_placeholder_image(self) -> None:
        """Ensure the image placeholder shows a visible stub image (64x64).

        If a bundled placeholder exists at assets/images/placeholder.png, use it;
        otherwise draw a simple light grey box with a dashed border.
        """
        try:
            label = getattr(self, "image_label", None)
            if label is None:
                return
            # Try a bundled placeholder first
            pm = QPixmap("assets/images/placeholder.png")
            if pm.isNull():
                pm = QPixmap(64, 64)
                pm.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pm)
                try:
                    painter.fillRect(0, 0, 64, 64, QColor("#f5f5f5"))
                    painter.setPen(QPen(QColor("#bbbbbb"), 1, Qt.PenStyle.DashLine))
                    painter.drawRect(1, 1, 62, 62)
                finally:
                    painter.end()
            label.setPixmap(pm)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not show placeholder image: %s", exc)

    def on_filter_changed(self, mode: str) -> None:
        # Persist the user's selection back to settings.py
        """Handle radio selection; ensure a visible letter is selected and refresh."""
        title_choice = "Both"
        if mode == "vowels":
            title_choice = "Vowels"
        elif mode == "consonants":
            title_choice = "Consonants"
        self._persist_radio_choice(title_choice)
        self.filter_mode = mode
        # Jump to the first item of the selected set
        if self.filter_mode == "vowels":
            self.index = 0
        elif self.filter_mode == "consonants":
            self.index = 13  # first consonant
        else:  # both
            self.index = 0
        self._refresh()
        if CURRENT_AUTO_PLAY_SOUND:
            self._play_token = getattr(self, "_play_token", 0) + 1
            token = self._play_token
            repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
            self._set_busy(True)
            # Respect initial delay before starting playback
            QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(repeats, token))

    def _bind(self) -> None:
        """Wire up button signals."""
        self.prev_btn.clicked.connect(self.on_prev)
        self.next_btn.clicked.connect(self.on_next)
        self.play_btn.clicked.connect(self.on_play)

    def _image_path_for(self, letter: HindiLetter) -> Path:
        """Return the image file path for a given Hindi letter."""
        if letter.example_noun and letter.example_translit:
            filename = f"{letter.example_noun}_{letter.example_translit}.png"
            path = Path("assets/images") / filename
            LOGGER.info("Image candidate: %s (exists=%s)", str(path), path.exists())
            return path
        return Path("assets/images/placeholder.png")

    def _format_example_caption(self, letter: HindiLetter) -> str:
        """Return example text with the symbol highlighted (red/bold) and dependent form (blue).

        Highlights occur only in the left-hand (Hindi) part before the dash. Uses HTML escaping.
        """
        try:
            example = letter.example or ""
            if not example:
                return ""
            parts = re.split(r"\s+[\u2013-]\s+", example, maxsplit=1)
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ""

            left_esc = html.escape(left)
            right_esc = html.escape(right)

            # Highlight main symbol in red/bold
            sym = letter.symbol or ""
            if sym:
                sym_esc = html.escape(sym)
                left_esc = left_esc.replace(
                    sym_esc, f'<span style="color:#FE5000; font-weight:800;">{sym_esc}</span>'
                )

            # Highlight dependent form in bright blue
            dep = (letter.dependent_form or "").strip()
            if dep:
                dep_esc = html.escape(dep)
                left_esc = left_esc.replace(
                    dep_esc, f'<span style="color:#007AFF; font-weight:700;">{dep_esc}</span>'
                )

            if right:
                return f"{left_esc} – {right_esc}"
            return left_esc
        except Exception:
            return html.escape(letter.example or "")


    def _highlight_matra_cluster(self, text: str, dep: str) -> str:
        """Highlight the *grapheme cluster(s)* that contain the given matra (dep).

        Uses Unicode grapheme segmentation (via the third-party `regex` module's \X).
        We color the *entire* cluster that contains the matra so shaping is preserved
        (works for pre-base matras like 'ि', post-base, above-base, conjuncts, nukta, etc.).

        If `regex` is unavailable, we simply return escaped text without inline highlighting.
        """
        if not dep:
            return html.escape(text)

        # Normalize to NFC to keep combining sequences consistent across fonts/renderers
        try:
            text = unicodedata.normalize("NFC", text)
        except Exception:
            pass

        if _REGEX is None:
            # Fallback: no cluster-aware highlighting possible
            LOGGER.debug("regex module not available; skipping cluster highlighting")
            return html.escape(text)

        try:
            clusters = _REGEX.findall(r"\X", text)
        except Exception:
            # Defensive: if regex \X fails for any reason, escape and return
            return html.escape(text)

        parts: list[str] = []
        dep_str = str(dep)
        for cl in clusters:
            if dep_str and dep_str in cl:
                # Highlight the *entire* cluster containing the matra
                parts.append(
                    f'<span style="background:#E6F0FF; color:#0A5BD3; font-weight:700; border-radius:3px; padding:0 2px;">{html.escape(cl)}</span>'
                )
            else:
                parts.append(html.escape(cl))
        return "".join(parts)

    def _format_dependent_info(self, letter: HindiLetter) -> str:
        """Display the dependent form and an example cleanly.

        Layout:
          Dependent form: <matra>
          Example: <example text as-is>

        The example's left (Hindi) part will highlight the matra ONLY if it already
        appears in that text. No concatenation/injection of the matra occurs.
        """
        dep = (letter.dependent_form or "").strip()
        example = (letter.dependent_form_example or "").strip()

        if not dep:
            return ""

        dep_html = f'<span style="color:#007AFF; font-weight:700;">{html.escape(dep)}</span>'
        html_parts = [f"Dependent form: {dep_html}"]

        if example:
            try:
                # Split on en-dash or hyphen surrounded by spaces: "… – …" or "… - …"
                parts = re.split(r"\s+[\u2013-]\s+", example, maxsplit=1)
                left = parts[0]
                right = parts[1] if len(parts) > 1 else ""

                # Highlight the base consonant + matra cluster ONLY if it naturally occurs
                left_html = self._highlight_matra_cluster(left, dep)
                right_html = html.escape(right)

                # Compose "Example:" and value on the same line for output
                if right:
                    html_parts.append(f"Example: {left_html} – {right_html}")
                else:
                    html_parts.append(f"Example: {left_html}")
            except Exception as exc:
                LOGGER.warning("Failed to format dependent form example: %s", exc)

        return "<br>".join(html_parts)



    def _refresh(self) -> None:

        # --- Safety: avoid IndexError for single-entry test mode or empty list ---
        if not getattr(self, "letters", None):
            LOGGER.warning("No letters loaded; skipping _refresh.")
            return

        if not isinstance(self.index, int):
            self.index = 0

        if self.index < 0 or self.index >= len(self.letters):
            LOGGER.info("Index %d out of range (len=%d); resetting to 0", self.index, len(self.letters))
            self.index = 0


        """Refresh UI from current index."""
        letter = self.letters[self.index]
        self.symbol_label.setText(letter.symbol)
        self.pron_label.setText("'" + letter.pronunciation + "'")
        self.english_equiv_label.setText("Say: " + letter.english_equiv)
        hint_text = letter.hint or ""

        # Split on the first '.' or ',' — whichever comes first
        split_index_dot = hint_text.find(".")
        split_index_comma = hint_text.find(",")

        # Choose whichever punctuation occurs first (ignoring -1)
        if split_index_dot == -1:
            split_index = split_index_comma
        elif split_index_comma == -1:
            split_index = split_index_dot
        else:
            split_index = min(split_index_dot, split_index_comma)

        if split_index != -1:
            # Insert a newline after the punctuation
            hint_text = (
                hint_text[: split_index + 1].strip()
                + "\n"
                + hint_text[split_index + 1 :].strip()
            )

        self.hint_label.setText("Hint: " + hint_text)
        # Determine category directly from YAML type field
        lt = (letter.letter_type or "").strip().lower()
        if lt == "vowel":
            category = "स्वर (Vowels)"
        elif lt == "consonant":
            category = "व्यंजन (Consonants)"
        else:
            category = "—"
        self.category_label.setText(category)

        # Enable/disable navigation at bounds, respecting filter.
        self.prev_btn.setEnabled(self._prev_visible_index(self.index) is not None)
        self.next_btn.setEnabled(self._next_visible_index(self.index) is not None)

        try:
            image_path = self._image_path_for(letter)
            if self.image_label is not None and image_path.exists():
                self._set_scaled_image(image_path)
            # Caption under the image (use imageCaption if present, else statusHint)
            if getattr(self, "caption_label", None) is not None:
                try:
                    self.caption_label.setTextFormat(Qt.TextFormat.RichText)
                except Exception:
                    pass
                self.caption_label.setText(self._format_example_caption(letter))
                self.caption_label.setVisible(bool(letter.example))
            # Dependent form explanation under the example — show only for vowels with a matra
            if getattr(self, "dependent_form_label", None) is not None:
                lt = (letter.letter_type or "").strip().lower()
                dep = (letter.dependent_form or "").strip()
                if lt == "vowel" and dep:
                    text = self._format_dependent_info(letter)
                    self.dependent_form_label.setText(text)
                    self.dependent_form_label.setVisible(True)
                else:
                    # Hide for consonants or when no dependent form is defined
                    try:
                        LOGGER.debug(
                            "Hiding dependentFormLabel (type=%s, dep_present=%s)", lt or "", bool(dep)
                        )
                    except Exception:
                        pass
                    self.dependent_form_label.clear()
                    self.dependent_form_label.setVisible(False)
        except Exception as exc:
            LOGGER.warning("Failed to update image/caption: %s", exc)
            # Update matra pointer below the example
        try:
            dep = (letter.dependent_form or "").strip()
            ex = (letter.dependent_form_example or letter.example or "").strip()
            if hasattr(self, "matra_pointer") and self.matra_pointer is not None and dep and ex:
                base_font = self.dependent_form_label.font() if self.dependent_form_label else None
                self.matra_pointer.set_example(ex, dep, base_font)
                self.matra_pointer.updateGeometry()
                self.matra_pointer.setVisible(True)
            elif hasattr(self, "matra_pointer") and self.matra_pointer is not None:
                self.matra_pointer.clear()
                self.matra_pointer.setVisible(False)
        except Exception as exc:
            LOGGER.warning("Failed to update matra pointer: %s", exc)

    def _set_scaled_image(self, image_path: Path) -> None:
        """Set image on image_label with aspect ratio preserved and transparent background.
        Draws the scaled image centered within the label's current size.
        """
        try:
            if self.image_label is None:
                return
            pm = QPixmap(str(image_path))
            if pm.isNull():
                return
            label_size = self.image_label.size()
            if label_size.width() <= 0 or label_size.height() <= 0:
                # Fallback: use pixmap's own size
                self.image_label.setPixmap(pm)
                return
            scaled = pm.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            # Compose onto a fully transparent canvas the size of the label
            canvas = QPixmap(label_size)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            try:
                x = (label_size.width() - scaled.width()) // 2
                y = (label_size.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            finally:
                painter.end()
            self.image_label.setPixmap(canvas)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("_set_scaled_image failed: %s", exc)


    def _set_busy(self, is_busy: bool) -> None:
        """Enable/disable controls while audio is playing."""
        try:
            if hasattr(self, "play_btn") and self.play_btn is not None:
                if getattr(self, "_continuous_active", False):
                    # keep Stop enabled so user can stop mid-utterance
                    self.play_btn.setEnabled(True)
                else:
                    self.play_btn.setEnabled(not is_busy)
            if hasattr(self, "next_btn") and self.next_btn is not None:
                if is_busy:
                    self.next_btn.setEnabled(False)
                else:
                    self.next_btn.setEnabled(self._next_visible_index(self.index) is not None)
            if hasattr(self, "prev_btn") and self.prev_btn is not None:
                if is_busy:
                    self.prev_btn.setEnabled(False)
                else:
                    self.prev_btn.setEnabled(self._prev_visible_index(self.index) is not None)
            if hasattr(self, "btn_slower") and self.btn_slower is not None and self.slider_rate is not None:
                self.btn_slower.setEnabled((not is_busy) and (self.slider_rate.value() > self.slider_rate.minimum()))
            if hasattr(self, "btn_faster") and self.btn_faster is not None and self.slider_rate is not None:
                self.btn_faster.setEnabled((not is_busy) and (self.slider_rate.value() < self.slider_rate.maximum()))
        except Exception:
            # Be defensive; UI state changes shouldn't crash playback
            pass

    def _play_repeated(self, times_left: int, token: int) -> None:
        """Play current letter now; if more repeats remain, schedule the next in 2s.

        Args:
            times_left: how many total plays remain including this one
            token: a monotonically increasing value to cancel previous schedules
        """
        # If a new Play was clicked, abandon old schedules
        if token != getattr(self, "_play_token", 0):
            return
        self._set_busy(True)
        letter = self.letters[self.index]

        # Perform actual playback for this repeat
        try:
            if hasattr(self, "audio_player") and hasattr(self.audio_player, "play_for"):
                self.audio_player.play_for(letter)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Playback failed: %s", exc)

        # After starting playback, wait until TTS actually finishes before advancing
        def _after_done() -> None:
            if token != getattr(self, "_play_token", 0):
                return
            if times_left > 1:
                # Gap between repeats
                QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(times_left - 1, token))
            else:
                # After final play, re-enable controls and, if in continuous mode, advance after interval
                QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._set_busy(False))
                if getattr(self, "_continuous_active", False) and token == getattr(self, "_play_token", 0):
                    next_gap = int(getattr(self, "_continuous_delay_ms", 3000))
                    QtCore.QTimer.singleShot(next_gap, lambda: self._continuous_advance_and_play(token))

        self._wait_until_silent(token, _after_done)

    def _apply_autoplay_ui(self, enabled: bool) -> None:
        """When auto-play is enabled, disable all nav/rate buttons except Play.
        When disabled, restore normal states using existing refresh helpers.
        """
        try:
            # Play button should always be enabled
            if hasattr(self, "play_btn") and self.play_btn is not None:
                self.play_btn.setEnabled(True)

            if enabled:
                # Disable navigation and rate step buttons completely in auto mode
                if hasattr(self, "prev_btn") and self.prev_btn is not None:
                    self.prev_btn.setEnabled(False)
                if hasattr(self, "next_btn") and self.next_btn is not None:
                    self.next_btn.setEnabled(False)
                if hasattr(self, "btn_slower") and self.btn_slower is not None:
                    self.btn_slower.setEnabled(False)
                if hasattr(self, "btn_faster") and self.btn_faster is not None:
                    self.btn_faster.setEnabled(False)

                # Show Stop icon/text while continuous is enabled
                self._set_play_icon_stop()

            else:
                # Restore normal initial state as on app load
                try:
                    self._refresh()
                except Exception:
                    pass
                if hasattr(self, "slider_rate") and self.slider_rate is not None:
                    try:
                        current_rate_val = int(self.slider_rate.value())
                        if hasattr(self, "_update_rate_controls_enabled"):
                            self._update_rate_controls_enabled(current_rate_val)
                    except Exception:
                        pass

                    # NEW: restore ear icon/text when continuous is disabled
                    self._set_play_icon_ear()
        except Exception:
            # Don't let UI toggling crash the app
            pass

    def on_settings_clicked(self) -> None:
        """Toggle Settings: if hidden, show floating at top-left; if visible, hide."""
        try:
            dock = getattr(self, "settingsDock", None)
            if dock is None:
                dock = self.findChild(QWidget, "settingsDock")
            if dock is None:
                LOGGER.warning("settingsDock not found in UI")
                return

            if not dock.isVisible():
                self._show_settings_floating_top_west()
            else:
                dock.hide()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to toggle settings panel: %s", exc)

    def _show_settings_floating_top_west(self) -> None:
        """Show settingsDock as a floating window at the top-left (west) of the app."""
        try:
            dock = getattr(self, "settingsDock", None)
            if dock is None:
                dock = self.findChild(QWidget, "settingsDock")
                if dock is None:
                    LOGGER.warning("settingsDock not found; cannot show settings.")
                    return

            # Make the dock float on top and size it sensibly
            try:
                dock.setFloating(True)
            except Exception:
                pass
            try:
                minw = max(250, getattr(dock, 'minimumWidth', lambda: 250)() if callable(
                    getattr(dock, 'minimumWidth', None)) else 250)
            except Exception:
                minw = 250
            try:
                h = max(300, min(self.height() - 40, 600))
            except Exception:
                h = 500
            try:
                dock.resize(minw, h)
            except Exception:
                pass

            # Position near the top-left of the main window with a small inset
            try:
                top_left = self.frameGeometry().topLeft()
                dock.move(top_left + QPoint(20, 20))
            except Exception:
                pass

            dock.show()
            try:
                dock.raise_()
                dock.activateWindow()
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("_show_settings_floating_top_west failed: %s", exc)

    def _debug_play_icon(self) -> None:
        """Log detailed diagnostics about the Play button icon visibility."""
        try:
            if not hasattr(self, "play_btn") or self.play_btn is None:
                LOGGER.warning("play_btn not found; cannot debug icon")
                return

            # 1) What Qt thinks about the icon currently set via .ui
            icon_obj = self.play_btn.icon()
            try:
                is_null = icon_obj.isNull()
            except Exception:
                is_null = True
            icon_size = self.play_btn.iconSize() if hasattr(self.play_btn, "iconSize") else QSize()
            LOGGER.info(
                "Play icon state: isNull=%s, iconSize=%sx%s",
                is_null,
                icon_size.width(),
                icon_size.height(),
            )

            # 2) Paths & where we're running from
            cwd = os.getcwd()
            app_dir = Path(__file__).resolve().parent  # src dir
            rel_path = Path("assets/icons/play.png")
            abs_from_cwd = (Path(cwd) / rel_path).resolve()
            # If main.py is in project root/src, parent of app_dir is likely the project root:
            abs_from_app = (app_dir.parent / rel_path).resolve()
            LOGGER.info("CWD=%s, app_dir=%s", cwd, str(app_dir))
            LOGGER.info("Icon candidates: from CWD=%s, from app_dir.parent=%s", str(abs_from_cwd), str(abs_from_app))

            # 3) Probe each candidate path and log pixmap load outcome (without setting it)
            for probe in (abs_from_cwd, abs_from_app, rel_path):
                try:
                    p = Path(probe)
                    exists = p.exists()
                    LOGGER.info("Probe '%s': exists=%s", str(p), exists)
                    if exists:
                        pm = QPixmap(str(p))
                        LOGGER.info(
                            "Pixmap from '%s': isNull=%s, size=%sx%s",
                            str(p), pm.isNull(), pm.width(), pm.height()
                        )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("Probe failed for '%s': %s", str(probe), exc)

            # 4) Check if any stylesheet might strip icons
            try:
                ss = self.play_btn.styleSheet() or ""
                LOGGER.info("play_btn stylesheet length=%d", len(ss))
            except Exception:
                pass

        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("_debug_play_icon encountered an error: %s", exc)

    def _set_play_icon_stop(self) -> None:
        """Set the Play button to show the custom stop icon and label."""
        try:
            if not getattr(self, "play_btn", None):
                return
            icon_path = Path("assets/icons/stop_playing.png")
            if icon_path.exists():
                self.play_btn.setIcon(QIcon(str(icon_path)))
                self.play_btn.setIconSize(QSize(24, 24))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to set stop icon: %s", exc)

    def _set_play_icon_ear(self) -> None:
        """Restore the ear icon and remove any text so it's icon-only."""
        try:
            if not getattr(self, "play_btn", None):
                return
            icon_path = Path("assets/icons/play.png")
            if icon_path.exists():
                self.play_btn.setIcon(QIcon(str(icon_path)))
                self.play_btn.setIconSize(QSize(24, 24))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to set ear icon: %s", exc)

    def _start_continuous(self) -> None:
        """Begin continuous playback cycle (3s interval between letters)."""
        try:
            self._continuous_active = True
            self._apply_autoplay_ui(True)
            self._set_play_icon_stop()
            # cancel any prior plays
            self._play_token = getattr(self, "_play_token", 0) + 1
            token = self._play_token
            repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
            self._play_repeated(repeats, token)  # start immediately
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("_start_continuous failed: %s", exc)

    def _stop_continuous(self) -> None:
        """Stop continuous playback cycle and restore UI/icon state."""
        try:
            self._continuous_active = False
            # cancel scheduled callbacks
            self._play_token = getattr(self, "_play_token", 0) + 1
            self._apply_autoplay_ui(False)
            self._set_play_icon_ear()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("_stop_continuous failed: %s", exc)

    def _continuous_advance_and_play(self, token: int) -> None:
        """Advance to next visible letter (wrapping) and play again if still active."""
        try:
            if not getattr(self, "_continuous_active", False):
                return
            if token != getattr(self, "_play_token", 0):
                return
            # compute next visible index (wrap if needed)
            nxt = self._next_visible_index(self.index)
            if nxt is None:
                # wrap to the first item of the selected set
                nxt = 13 if self.filter_mode == "consonants" else 0
            self.index = nxt
            self._refresh()
            # play current
            repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
            self._play_repeated(repeats, token)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("_continuous_advance_and_play failed: %s", exc)

    def on_autoplay_toggled(self, state: int) -> None:
        """Persist the Auto-play checkbox state to settings.CONTINUOUS and apply UI."""
        try:
            enabled = bool(state)
            settings_path = Path("settings.py")
            if settings_path.exists():
                txt = settings_path.read_text(encoding="utf-8")
                new_line = f'CONTINUOUS = {enabled}'
                pattern = re.compile(r'^\s*CONTINUOUS\s*=\s*(True|False)\s*$', re.MULTILINE)
                if pattern.search(txt):
                    txt_new = pattern.sub(new_line, txt)
                else:
                    sep = "\n" if not txt.endswith("\n") else ""
                    txt_new = txt + f"{sep}{new_line}\n"
                if txt_new != txt:
                    settings_path.write_text(txt_new, encoding="utf-8")
            LOGGER.info("Auto-play checkbox toggled: %s", enabled)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to persist CONTINUOUS state: %s", exc)
        finally:
            # Always apply UI state regardless of persistence outcome
            try:
                self._apply_autoplay_ui(enabled)
            except Exception:
                pass

            # NEW: start/stop continuous playback to match checkbox
            try:
                if enabled:
                    self._start_continuous()
                else:
                    self._stop_continuous()
            except Exception:
                pass

    # ----------------------------------------------------------------------------
    # Navigation + Audio
    # ----------------------------------------------------------------------------
    def on_prev(self) -> None:
        """Go to previous letter if available; optionally auto-play sound with initial delay."""
        if self.index > 0:
            prev_i = self._prev_visible_index(self.index)
            if prev_i is None:
                return
            self.index = prev_i
            self._refresh()
            if CURRENT_AUTO_PLAY_SOUND:
                self._play_token = getattr(self, "_play_token", 0) + 1
                token = self._play_token
                repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
                self._set_busy(True)
                QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(repeats, token))

    def on_next(self) -> None:
        """Go to next letter if available; optionally auto-play sound with initial delay."""
        if self.index < len(self.letters) - 1:
            next_i = self._next_visible_index(self.index)
            if next_i is None:
                return
            self.index = next_i
            self._refresh()
            if CURRENT_AUTO_PLAY_SOUND:
                self._play_token = getattr(self, "_play_token", 0) + 1
                token = self._play_token
                repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
                self._set_busy(True)
                QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(repeats, token))

    def on_play(self) -> None:
        """Play the associated sound for the current letter (with repeats)."""
        # NEW: If continuous mode is active, Play behaves as Stop
        if getattr(self, "_continuous_active", False):
            self._stop_continuous()
            return

        try:
            # Invalidate any queued repeats from prior clicks
            self._play_token = getattr(self, "_play_token", 0) + 1
            token = self._play_token
            # Mark UI busy and start immediate play then schedule repeats
            self._set_busy(True)
            repeats = int(TTS_REPEATS) if TTS_REPEATS and int(TTS_REPEATS) > 0 else 1
            self._play_repeated(repeats, token)
        except Exception as exc:  # noqa: BLE001 - deliberate broad catch for UI safety
            LOGGER.exception("Failed to play audio: %s", exc)
            QMessageBox.warning(
                self,
                "Audio Error",
                "Unable to play audio. See logs for details.",
            )


def ensure_runtime_dirs() -> None:
    """Ensure minimal runtime directories exist (non-fatal if they don't)."""
    # No longer need to create assets/audio.
    pass


def main() -> int:
    """Application entry point.

    Returns:
        Process exit code.
    """
    ensure_runtime_dirs()

    # Try to load letters from data/letters.yaml (explicit schema).
    data_path = Path("data/letters.yaml")
    letters: Optional[List[HindiLetter]] = None
    try:
        if data_path.exists():
            letters = _load_letters_from_yaml(data_path)
            if not letters:
                raise RuntimeError("letters.yaml could not be loaded or contained no letters")
        else:
            raise FileNotFoundError("data/letters.yaml not found")
    except Exception as exc:
        LOGGER.error("Could not load letters.yaml: %s", exc)
        raise RuntimeError("letters.yaml could not be loaded or contained no letters") from exc

    LOGGER.info(
        "Using %d letters (source: %s)",
        len(letters or []),
        "letters.yaml"
    )
    try:
        img_dir = Path("assets/images")
        if img_dir.exists():
            count = len([p for p in img_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
            LOGGER.info("Found %d images in %s", count, str(img_dir))
    except Exception:
        pass

    app = QApplication([])
    app.setFont(QFont("Kohinoor Devanagari"))
    win = MainWindow(letters)
    win.resize(480, 1024)  # respect new_form.ui geometry & layout hints
    win.show()
    return app.exec()


#
# [Prompt: TASK] Migrated from PyQt5 to PyQt6 (imports, enums, app.exec)
# ----------------------------------------------------------------------------
# [Prompt: CODE CHANGES PROTOCOL] Entry point kept but replaced implementation.
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(main())
    # [Prompt: remove stray nested on_settings_clicked; method now lives on MainWindow]

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        try:
            # Re-apply scaling to fit the new label size
            letter = self.letters[self.index]
            image_path = self._image_path_for(letter)
            if self.image_label is not None and image_path.exists():
                self._set_scaled_image(image_path)
        except Exception:
            pass