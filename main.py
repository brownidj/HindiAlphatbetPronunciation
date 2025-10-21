"""Hindi Alphabet Learning App

[Prompt: TASK - Desktop app to assist with the learning of the Hindi alphabet]

This minimal PyQt6 application shows a Hindi character, its transliteration,
and an English approximation, with Next/Previous navigation and a Play button
that attempts to play an associated sound from assets/audio/.

It builds the UI in code so it runs immediately. You can later replace the
programmatic UI with a Qt Designer `.ui` by swapping `build_ui_in_code=True`
below and using `uic.loadUi("ui/main_window.ui", self)`.

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
"""

from __future__ import annotations

import logging
import re
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, cast

from PyQt6 import QtCore
from PyQt6 import uic
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QSoundEffect
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
)

from settings import (CURRENT_TTS_RATE,
                      TTS_REPEATS,
                      TTS_DELAY,
                      CURRENT_AUTO_PLAY_SOUND,
                      CURRENT_RADIO_BUTTON)

# ----------------------------------------------------------------------------
# [Prompt: IMPLEMENTATION GUIDELINES] Logging configuration
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("hindi_app")


# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class HindiLetter:
    """Represents a single Hindi letter/phoneme entry.

    Attributes:
        symbol: The Devanagari character(s).
        pronunciation: A simple transliteration for the sound.
        english_equiv: English word/phrase hint for the sound.
        audio_basename: Optional basename for the .wav file in assets/audio/.
    """

    symbol: str
    pronunciation: str
    english_equiv: str
    audio_basename: Optional[str] = None


def _dataset() -> List[HindiLetter]:
    """Return the ordered dataset of vowels (स्वर) then consonants (व्यंजन).

    Returns:
        A list of HindiLetter in the required order.
    """

    vowels: List[HindiLetter] = [
        HindiLetter("अ", "a", 'as in "America"', "a"),
        HindiLetter("आ", "aa", 'as in "father"', "aa"),
        HindiLetter("इ", "i", 'as in "bit"', "i"),
        HindiLetter("ई", "ee", 'as in "beet"', "ee"),
        HindiLetter("उ", "u", 'as in "put"', "u"),
        HindiLetter("ऊ", "oo", 'as in "boot"', "oo"),
        HindiLetter("ए", "e", 'as in "they"', "e"),
        HindiLetter("ऐ", "ai", 'as in "aisle"', "ai"),
        HindiLetter("ओ", "o", 'as in "go"', "o"),
        HindiLetter("औ", "au", 'as in "cow"', "au"),
        HindiLetter("अं", "am", 'nasalized "a"', "am"),
        HindiLetter("अः", "ah", 'aspirated "a"', "ah"),
        HindiLetter("ऋ", "ri", 'as in "river"', "ri"),
    ]

    consonants: List[HindiLetter] = [
        HindiLetter("क", "ka", 'as in "kite"', "ka"),
        HindiLetter("ख", "kha", 'as in "khaki"', "kha"),
        HindiLetter("ग", "ga", 'as in "go"', "ga"),
        HindiLetter("घ", "gha", 'aspirated "g"', "gha"),
        HindiLetter("ङ", "nga", 'as in "sing"', "nga"),
        HindiLetter("چ" if False else "च", "cha", 'as in "chair"', "cha"),
        HindiLetter("छ", "chha", 'aspirated "ch"', "chha"),
        HindiLetter("ज", "ja", 'as in "jam"', "ja"),
        HindiLetter("झ", "jha", 'aspirated "j"', "jha"),
        HindiLetter("ञ", "nya", 'as in "canyon"', "nya"),
        HindiLetter("ट", "ta", 'retroflex "t"', "ta_retroflex"),
        HindiLetter("ठ", "tha", 'aspirated retroflex "t"', "tha_retroflex"),
        HindiLetter("ड", "da", 'retroflex "d"', "da_retroflex"),
        HindiLetter("ढ", "dha", 'aspirated retroflex "d"', "dha_retroflex"),
        HindiLetter("ण", "na", 'retroflex "n"', "na_retroflex"),
        HindiLetter("त", "ta", 'dental "t"', "ta_dental"),
        HindiLetter("थ", "tha", 'aspirated dental "t"', "tha_dental"),
        HindiLetter("द", "da", 'dental "d"', "da_dental"),
        HindiLetter("ध", "dha", 'aspirated dental "d"', "dha_dental"),
        HindiLetter("न", "na", 'as in "nap"', "na"),
        HindiLetter("प", "pa", 'as in "pen"', "pa"),
        HindiLetter("फ", "pha", 'as in "photo"', "pha"),
        HindiLetter("ब", "ba", 'as in "bat"', "ba"),
        HindiLetter("भ", "bha", 'aspirated "b"', "bha"),
        HindiLetter("म", "ma", 'as in "man"', "ma"),
        HindiLetter("य", "ya", 'as in "yes"', "ya"),
        HindiLetter("र", "ra", 'as in "run"', "ra"),
        HindiLetter("ल", "la", 'as in "lamp"', "la"),
        HindiLetter("व", "va", 'as in "van"', "va"),
        HindiLetter("श", "sha", 'as in "shut"', "sha"),
        HindiLetter("ष", "shha", 'retroflex "sh"', "shha"),
        HindiLetter("स", "sa", 'as in "sun"', "sa"),
        HindiLetter("ह", "ha", 'as in "hat"', "ha"),
        HindiLetter("क्ष", "ksha", 'combination of "k" and "sh"', "ksha"),
        HindiLetter("त्र", "tra", 'combination of "t" and "r"', "tra"),
        HindiLetter("ज्ञ", "gya", 'combination of "g" and "ya"', "gya"),
    ]

    return vowels + consonants


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


class HindiAudioPlayer:
    """Plays letter sounds from the assets/audio directory if present."""

    def __init__(self, audio_dir: Path) -> None:
        self._audio_dir = audio_dir
        self._effect = QSoundEffect()
        self._effect.setVolume(0.9)

    def play_for(self, letter: HindiLetter) -> None:
        """Attempt to play the sound for the given letter.

        Args:
            letter: The HindiLetter whose audio should be played.
        """
        if not letter.audio_basename:
            LOGGER.info("No audio basename for %s", letter.symbol)
            self._notify_missing_audio(letter)
            return

        wav_path = self._audio_dir / f"{letter.audio_basename}.wav"
        if not wav_path.exists():
            LOGGER.warning("Audio file not found: %s", wav_path)
            self._notify_missing_audio(letter)
            return

        url = QtCore.QUrl.fromLocalFile(str(wav_path))
        self._effect.setSource(url)
        self._effect.play()
        LOGGER.info("Playing %s", wav_path.name)

    @staticmethod
    def _notify_missing_audio(letter: HindiLetter) -> None:
        # Lightweight, non-blocking user feedback via log only.
        LOGGER.info(
            "Audio missing for '%s' (%s). Place a .wav in assets/audio/",
            letter.symbol,
            letter.pronunciation,
        )


class MainWindow(QMainWindow):
    """Main application window with navigation and audio."""

    def __init__(self, letters: List[HindiLetter], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hindi Alphabet Helper")
        self.letters = letters
        self.index = 0
        # [Prompt: TASK] Old audio player using .wav files:
        # self.audio_player = HindiAudioPlayer(audio_dir=Path("assets/audio"))
        # [Prompt: TASK] Prefer macOS-native TTS when on macOS; fall back to pyttsx3 otherwise.
        if sys.platform == "darwin":
            try:
                self.audio_player = HindiTTSPlayerMac(rate=CURRENT_TTS_RATE)
            except Exception as _exc:
                LOGGER.warning("macOS TTS unavailable (%s); falling back to pyttsx3", _exc)
                self.audio_player = HindiTTSPlayer(rate=CURRENT_TTS_RATE)
        else:
            self.audio_player = HindiTTSPlayer(rate=CURRENT_TTS_RATE)

        # Build UI in code to ensure immediate run; swap to uic.loadUi later if desired.
        uic.loadUi("ui/form.ui", self)
        # Bind typed Designer widgets for static analysis and autocompletion
        self.prev_btn = cast(QPushButton, self.findChild(QPushButton, "prev_btn"))
        self.play_btn = cast(QPushButton, self.findChild(QPushButton, "play_btn"))
        self.next_btn = cast(QPushButton, self.findChild(QPushButton, "next_btn"))

        self.symbol_label = cast(QLabel, self.findChild(QLabel, "symbolLabel"))
        self.pron_label = cast(QLabel, self.findChild(QLabel, "pronLabel"))
        self.eng_label = cast(QLabel, self.findChild(QLabel, "engLabel"))
        self.category_label = cast(QLabel, self.findChild(QLabel, "categoryLabel"))
        self.status_hint = cast(QLabel, self.findChild(QLabel, "statusHint"))

        self.slider_rate = cast(QSlider, self.findChild(QSlider, "sliderRate"))
        self.lbl_rate_value = cast(QLabel, self.findChild(QLabel, "lblRateValue"))
        self.btn_slower = cast(QToolButton, self.findChild(QToolButton, "btnSlower"))
        self.btn_faster = cast(QToolButton, self.findChild(QToolButton, "btnFaster"))

        # --- Filtering radio buttons
        self.rb_vowels = cast(QRadioButton, self.findChild(QRadioButton, "rbVowels"))
        self.rb_consonants = cast(QRadioButton, self.findChild(QRadioButton, "rbConsonants"))
        self.rb_both = cast(QRadioButton, self.findChild(QRadioButton, "rbBoth"))

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

    # [Prompt: UI/UX requirements] Panel showing character, transliteration, hints.
    # def _build_ui(self) -> None:
    #     """Create widgets and layouts programmatically."""
    #     central = QWidget(self)
    #     root_v = QVBoxLayout(central)
    #
    #     # Title area (optional categorization label)
    #     self.category_label = QLabel("स्वर / व्यंजन")
    #     self.category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     self.category_label.setObjectName("categoryLabel")
    #     root_v.addWidget(self.category_label)
    #
    #     grid = QGridLayout()
    #     root_v.addLayout(grid)
    #
    #     # Large symbol
    #     self.symbol_label = QLabel("अ")
    #     self.symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     self.symbol_label.setObjectName("symbolLabel")
    #     self.symbol_label.setStyleSheet("font-size: 96px; line-height: 1.1;")
    #     grid.addWidget(self.symbol_label, 0, 0, 1, 3)
    #
    #     # Transliteration and English equivalent
    #     self.pron_label = QLabel("a")
    #     self.pron_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     self.pron_label.setObjectName("pronLabel")
    #     self.pron_label.setStyleSheet("font-size: 28px;")
    #     grid.addWidget(self.pron_label, 1, 0, 1, 3)
    #
    #     self.eng_label = QLabel('as in "America"')
    #     self.eng_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     self.eng_label.setObjectName("engLabel")
    #     self.eng_label.setStyleSheet("font-size: 20px; color: #555;")
    #     grid.addWidget(self.eng_label, 2, 0, 1, 3)
    #
    #     # Controls row
    #     controls = QHBoxLayout()
    #     root_v.addLayout(controls)
    #
    #     self.prev_btn: QPushButton = QPushButton("◀ Previous")
    #     self.play_btn: QPushButton = QPushButton("Play ▶")
    #     self.next_btn: QPushButton = QPushButton("Next ▶")
    #     controls.addWidget(self.prev_btn)
    #     controls.addWidget(self.play_btn)
    #     controls.addWidget(self.next_btn)
    #
    #     # Status hint
    #     self.status_hint = QLabel(
    #         'Place .wav files in assets/audio/ (e.g., "a.wav", "ka.wav").'
    #     )
    #     self.status_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     self.status_hint.setObjectName("statusHint")
    #     self.status_hint.setStyleSheet("font-size: 12px; color: #888;")
    #     root_v.addWidget(self.status_hint)
    #
    #     self.setCentralWidget(central)

    def _bind(self) -> None:
        """Wire up button signals."""
        self.prev_btn.clicked.connect(self.on_prev)
        self.next_btn.clicked.connect(self.on_next)
        self.play_btn.clicked.connect(self.on_play)

    def _refresh(self) -> None:
        """Refresh UI from current index."""
        letter = self.letters[self.index]
        self.symbol_label.setText(letter.symbol)
        self.pron_label.setText(letter.pronunciation)
        self.eng_label.setText(letter.english_equiv)

        # Category label for first 13 entries (vowels), then consonants.
        category = "स्वर (Vowels)" if self.index < 13 else "व्यंजन (Consonants)"
        self.category_label.setText(category)

        # Enable/disable navigation at bounds, respecting filter.
        self.prev_btn.setEnabled(self._prev_visible_index(self.index) is not None)
        self.next_btn.setEnabled(self._next_visible_index(self.index) is not None)

    def _set_busy(self, is_busy: bool) -> None:
        """Enable/disable controls while audio is playing."""
        try:
            if hasattr(self, "play_btn") and self.play_btn is not None:
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
        self._set_busy(True)  # <-- add this
        letter = self.letters[self.index]

        # Perform actual playback for this repeat
        try:
            if hasattr(self, "audio_player") and hasattr(self.audio_player, "play_for"):
                self.audio_player.play_for(letter)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Playback failed: %s", exc)

        if times_left > 1:
            QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._play_repeated(times_left - 1, token))
        else:
            # After final play, re-enable controls. Use a small delay to accommodate async engines.
            QtCore.QTimer.singleShot(TTS_DELAY, lambda: self._set_busy(False))

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
    """Ensure minimal runtime directories exist (non-fatal if they don't).

    Creates the assets/audio directory so users know where to put .wav files.
    """
    audio_dir = Path("assets/audio")
    try:
        audio_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.warning("Could not create %s: %s", audio_dir, exc)


def main() -> int:
    """Application entry point.

    Returns:
        Process exit code.
    """
    ensure_runtime_dirs()

    letters = _dataset()

    app = QApplication([])
    app.setFont(QFont("Kohinoor Devanagari"))
    win = MainWindow(letters)
    win.resize(500, 436)  # respect form.ui geometry & layout hints
    win.show()
    return app.exec()


#
# [Prompt: TASK] Migrated from PyQt5 to PyQt6 (imports, enums, app.exec)
# ----------------------------------------------------------------------------
# [Prompt: CODE CHANGES PROTOCOL] Entry point kept but replaced implementation.
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(main())