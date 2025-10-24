/// App-wide defaults (analogous to Python’s settings.py constants).
library constants;

/// ===== TTS defaults =====
const int kDefaultTtsRateWpm   = 160;   // words-per-minute
const int kDefaultTtsRepeats   = 2;     // how many times to repeat
const int kDefaultTtsDelaySec = 2000; // gap between repeats (seconds)

/// ===== App behaviour defaults =====
const bool kDefaultContinuous = false;  // auto-play off by default