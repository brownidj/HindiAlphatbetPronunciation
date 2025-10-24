#!/usr/bin/env zsh
set -euo pipefail

# --- locations
ROOT_DIR="$(pwd)"
FL_DIR="${ROOT_DIR}/flutter"
APP_DIR="${FL_DIR}/hindi_alphabet"

echo "Creating flutter app at: ${APP_DIR}"

mkdir -p "${FL_DIR}"
cd "${FL_DIR}"

# 1) Create a new Flutter app
flutter create --platforms=ios,macos,android,web -e hindi_alphabet


cd "${APP_DIR}"

# 1b) Bump macOS deployment target to 10.15 for flutter_tts compatibility
if [[ -f macos/Podfile ]]; then
  sed -E -i.bak "s/platform :osx, '10\.[0-9]+'/platform :osx, '10.15'/" macos/Podfile || true
fi
# Also adjust Xcode project deployment target where present
if [[ -f macos/Runner.xcodeproj/project.pbxproj ]]; then
  sed -E -i.bak "s/MACOSX_DEPLOYMENT_TARGET = 10\.[0-9]+;/MACOSX_DEPLOYMENT_TARGET = 10.15;/g" macos/Runner.xcodeproj/project.pbxproj || true
fi
# Some Flutter templates keep it in xcconfig files as well
if [[ -f macos/Runner/Configs/Debug.xcconfig ]]; then
  sed -E -i.bak "s/MACOSX_DEPLOYMENT_TARGET\s*=\s*10\.[0-9]+/MACOSX_DEPLOYMENT_TARGET = 10.15/" macos/Runner/Configs/Debug.xcconfig || true
fi
if [[ -f macos/Runner/Configs/Release.xcconfig ]]; then
  sed -E -i.bak "s/MACOSX_DEPLOYMENT_TARGET\s*=\s*10\.[0-9]+/MACOSX_DEPLOYMENT_TARGET = 10.15/" macos/Runner/Configs/Release.xcconfig || true
fi

# 2) Ensure asset folders
mkdir -p assets/images data assets/fonts lib/features/letters/{data,domain,presentation/widgets} lib/services

# 3) Copy data & images from your existing project if present
#    Adjust paths if your repo differs
if [[ -f "${ROOT_DIR}/data/letters.yaml" ]]; then
  cp -f "${ROOT_DIR}/data/letters.yaml" data/letters.yaml
else
  # minimal fallback so the app runs
  cat > data/letters.yaml <<'YAML'
letters:
  - symbol: "अ"
    type: "vowel"
    pronunciation: "a"
    english_approx: "'u' as in umbrella"
    hint: "Short neutral vowel."
    example: "अनार (anar) – Pomegranate"
YAML
fi

if [[ -d "${ROOT_DIR}/assets/images" ]]; then
  rsync -a --delete "${ROOT_DIR}/assets/images/" assets/images/
fi

# 4) Pubspec with deps + assets/fonts (uses Noto Sans Devanagari by default)
cat > pubspec.yaml <<'PUB'
name: hindi_alphabet
description: Hindi alphabet learning app (Flutter port)
publish_to: "none"
version: 0.1.0+1

environment:
  sdk: ">=3.3.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter
  yaml: ^3.1.2
  flutter_tts: ^3.8.3
  shared_preferences: ^2.2.3
  characters: ^1.3.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^4.0.0

flutter:
  uses-material-design: true
  assets:
    - data/letters.yaml
    - assets/images/
  fonts:
    - family: NotoSansDevanagari
      fonts:
        - asset: assets/fonts/Noto_Sans_Devanagari/static/NotoSansDevanagari-Regular.ttf
PUB

# 5) Minimal font if you don't have one in repo (download stub message)
if [[ ! -f assets/fonts/Noto_Sans_Devanagari/static/NotoSansDevanagari-Regular.ttf ]]; then
  echo "NOTE: Please add NotoSansDevanagari-Regular.ttf into assets/fonts/Noto_Sans_Devanagari/static/"
fi

# 6) Domain model
cat > lib/features/letters/domain/hindi_letter.dart <<'DART'
class HindiLetter {
  final String symbol;
  final String pronunciation;
  final String englishApprox;
  final String? type; // "vowel"|"consonant"
  final String? dependentForm;
  final String? hint;
  final String? example;
  final String? dependentFormExample;
  final String? exampleNounSlug;
  final String? exampleTranslitSlug;

  const HindiLetter({
    required this.symbol,
    required this.pronunciation,
    required this.englishApprox,
    this.type,
    this.dependentForm,
    this.hint,
    this.example,
    this.dependentFormExample,
    this.exampleNounSlug,
    this.exampleTranslitSlug,
  });

  String? get imageFileName {
    if (exampleNounSlug == null || exampleTranslitSlug == null) return null;
    return 'assets/images/${exampleNounSlug!}_${exampleTranslitSlug!}.png';
  }
}
DART

# 7) Repository (loads YAML)
cat > lib/features/letters/data/letters_repository.dart <<'DART'
import 'package:flutter/services.dart' show rootBundle;
import 'package:yaml/yaml.dart';
import '../../letters/domain/hindi_letter.dart';

String _slug(String s) {
  final lower = s.toLowerCase();
  final cleaned = lower
    .replaceAll(RegExp(r"[^a-z0-9]+"), "_")
    .replaceAll(RegExp(r"_+"), "_")
    .replaceAll(RegExp(r"^_|_$"), "");
  return cleaned;
}

class LettersRepository {
  Future<List<HindiLetter>> loadLetters() async {
    final raw = await rootBundle.loadString('data/letters.yaml');
    final doc = loadYaml(raw);
    final items = (doc is Map && doc['letters'] is List) ? (doc['letters'] as List) : <dynamic>[];
    return items.map<HindiLetter>((it) {
      final m = Map<String, dynamic>.from(it as Map);
      // Parse example slugs
      String? example = (m['example'] ?? '').toString().trim();
      String? nounSlug;
      String? translitSlug;
      if (example.isNotEmpty) {
        final re = RegExp(r'^(.*)\(([^)]+)\)\s*[-–]\s*(.*)$');
        final match = re.firstMatch(example);
        if (match != null) {
          final noun = match.group(3)?.trim() ?? '';
          final translit = match.group(2)?.trim() ?? '';
          nounSlug = _slug(noun);
          translitSlug = _slug(translit);
        }
      }
      return HindiLetter(
        symbol: (m['symbol'] ?? '').toString(),
        pronunciation: (m['pronunciation'] ?? '').toString(),
        englishApprox: (m['english_approx'] ?? '').toString(),
        type: (m['type'] ?? '').toString(),
        dependentForm: (m['dependent_form'] ?? '').toString().isEmpty ? null : m['dependent_form'],
        hint: (m['hint'] ?? '').toString().isEmpty ? null : m['hint'],
        example: example.isEmpty ? null : example,
        dependentFormExample: (m['dependent_form_example'] ?? '').toString().isEmpty ? null : m['dependent_form_example'],
        exampleNounSlug: nounSlug,
        exampleTranslitSlug: translitSlug,
      );
    }).toList(growable: false);
  }
}
DART

# 8) TTS service
cat > lib/services/tts_service.dart <<'DART'
import 'dart:async';
import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  final _tts = FlutterTts();
  int rateWpm;
  int repeats;
  Duration gap;

  TtsService({required this.rateWpm, required this.repeats, required this.gap});

  Future<void> init() async {
    await _tts.setLanguage('hi-IN');
    await _tts.setSpeechRate(_wpmToFlutterRate(rateWpm));
  }

  double _wpmToFlutterRate(int wpm) {
    // Tunable mapping; start with ~0.5 at ~160WPM
    return (wpm / 300).clamp(0.2, 1.0);
  }

  Future<void> setRate(int wpm) async {
    rateWpm = wpm;
    await _tts.setSpeechRate(_wpmToFlutterRate(wpm));
  }

  Future<void> speakRepeats(String text) async {
    for (var i = 0; i < repeats; i++) {
      await _tts.stop();
      await _tts.speak(text);
      if (i < repeats - 1) {
        await Future.delayed(gap);
      }
    }
  }

  Future<void> stop() => _tts.stop();
}
DART

# 9) Prefs
cat > lib/services/prefs_service.dart <<'DART'
import 'package:shared_preferences/shared_preferences.dart';

class PrefsService {
  static const kRate = 'tts_rate';
  static const kRepeats = 'tts_repeats';
  static const kDelaySec = 'tts_delay_sec';
  static const kFilter = 'current_radio_button'; // Vowels|Consonants|Both
  static const kContinuous = 'continuous';

  Future<void> saveRate(int v) async => (await SharedPreferences.getInstance()).setInt(kRate, v);
  Future<int> loadRate({int def = 160}) async => (await SharedPreferences.getInstance()).getInt(kRate) ?? def;

  Future<void> saveRepeats(int v) async => (await SharedPreferences.getInstance()).setInt(kRepeats, v);
  Future<int> loadRepeats({int def = 2}) async => (await SharedPreferences.getInstance()).getInt(kRepeats) ?? def;

  Future<void> saveDelaySec(int v) async => (await SharedPreferences.getInstance()).setInt(kDelaySec, v);
  Future<int> loadDelaySec({int def = 2}) async => (await SharedPreferences.getInstance()).getInt(kDelaySec) ?? def;

  Future<void> saveFilter(String v) async => (await SharedPreferences.getInstance()).setString(kFilter, v);
  Future<String> loadFilter({String def = 'Both'}) async => (await SharedPreferences.getInstance()).getString(kFilter) ?? def;

  Future<void> saveContinuous(bool v) async => (await SharedPreferences.getInstance()).setBool(kContinuous, v);
  Future<bool> loadContinuous({bool def = false}) async => (await SharedPreferences.getInstance()).getBool(kContinuous) ?? def;
}
DART

# 10) Minimal main.dart (first letter + basic controls)
cat > lib/main.dart <<'DART'
import 'package:flutter/material.dart';
import 'features/letters/data/letters_repository.dart';
import 'features/letters/domain/hindi_letter.dart';
import 'services/tts_service.dart';
import 'services/prefs_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final repo = LettersRepository();
  final prefs = PrefsService();

  final letters = await repo.loadLetters();
  final rate = await prefs.loadRate(def: 160);
  final reps = await prefs.loadRepeats(def: 2);
  final delaySec = await prefs.loadDelaySec(def: 2);

  final tts = TtsService(rateWpm: rate, repeats: reps, gap: Duration(seconds: delaySec));
  await tts.init();

  runApp(MyApp(letters: letters, tts: tts, prefs: prefs));
}

class MyApp extends StatelessWidget {
  final List<HindiLetter> letters;
  final TtsService tts;
  final PrefsService prefs;
  const MyApp({super.key, required this.letters, required this.tts, required this.prefs});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hindi Alphabet',
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'NotoSansDevanagari',
      ),
      home: HomePage(letters: letters, tts: tts, prefs: prefs),
    );
  }
}

class HomePage extends StatefulWidget {
  final List<HindiLetter> letters;
  final TtsService tts;
  final PrefsService prefs;
  const HomePage({super.key, required this.letters, required this.tts, required this.prefs});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    final letter = widget.letters[index];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hindi Alphabet'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(letter.symbol, style: const TextStyle(fontSize: 96)),
              const SizedBox(height: 12),
              Text("'${letter.pronunciation}'", style: const TextStyle(fontSize: 24)),
              const SizedBox(height: 8),
              Text("Say: ${letter.englishApprox}", style: const TextStyle(fontSize: 18)),
              const SizedBox(height: 8),
              if (letter.hint != null) Text("Hint: ${letter.hint!}", textAlign: TextAlign.center),
              const SizedBox(height: 16),
              if (letter.imageFileName != null)
                Image.asset(
                  letter.imageFileName!,
                  width: 220, height: 220, fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                ),
              const SizedBox(height: 8),
              if (letter.example != null) Text(letter.example!, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            IconButton(icon: const Icon(Icons.chevron_left), onPressed: _prev),
            FilledButton.tonal(
              onPressed: _play,
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [Icon(Icons.hearing), SizedBox(width: 8), Text("Play")],
              ),
            ),
            IconButton(icon: const Icon(Icons.chevron_right), onPressed: _next),
          ],
        ),
      ),
    );
  }

  void _play() async {
    await widget.tts.speakRepeats(widget.letters[index].symbol);
  }

  void _prev() => setState(() => index = (index - 1) < 0 ? 0 : index - 1);
  void _next() => setState(() => index = (index + 1) >= widget.letters.length ? index : index + 1);

  void _openSettings() {
    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => const Padding(
        padding: EdgeInsets.all(24),
        child: Text("Settings (rate/repeats/delay) — to be implemented"),
      ),
    );
  }
}
DART

# 11) Get packages
flutter pub get

echo "✅ Flutter scaffold ready."
echo "Note: macOS deployment target set to 10.15 for flutter_tts compatibility."

# Next:
#   1) Add NotoSansDevanagari-Regular.ttf into assets/fonts/Noto_Sans_Devanagari/static/
#   2) Run: cd ${APP_DIR} && flutter run
