/// App-wide defaults (analogous to Python’s settings.py constants).
library constants;

/// ===== TTS defaults =====
const int kDefaultTtsRateWpm   = 160;   // words-per-minute
const int kDefaultTtsRepeats   = 2;     // how many times to repeat
const int kDefaultTtsDelayMs   = 2000;  // delay between repeats (milliseconds)

/// ===== App behaviour defaults =====
const bool kDefaultContinuous = false;  // auto-play off by default
const String kDefaultCurrentRadioButton = "Vowels"; // Vowels, Consonants, Both
const double kDefaultPlaybackVolume = 0.5; // 0.0 to 1.0
const String kDefaultVoice = "auto"; // system TTS voice
const bool kDefaultContinuousMode = false;

/// ===== File and logging defaults =====
const String kLogFile = "hindi_app.log";
const String kDataPath = "data/letters.yaml";
const String kAssetsImagePath = "assets/images/";
const String kAssetsFontPath = "assets/fonts/Noto_Sans_Devanagari/static/NotoSansDevanagari-Regular.ttf";

/// ===== UI layout defaults =====
const int kUiPadding = 8;
const int kUiSpacing = 6;
const int kUiMinWindowWidth = 1280;
const int kUiMinWindowHeight = 800;
const double kUiSymbolFontSize = 196.0;

/// ===== Debug defaults =====
const bool kDebugMode = false;
const bool kVerboseLogging = true;