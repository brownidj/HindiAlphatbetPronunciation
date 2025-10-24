import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:window_size/window_size.dart' as win;

import 'features/letters/data/letters_repository.dart';
import 'features/letters/domain/hindi_letter.dart';
import 'services/prefs_service.dart';
import 'services/tts_service.dart';
// import 'tts_stub.dart'
//   if (dart.library.io) 'tts_real.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  if (!Platform.isIOS && !Platform.isAndroid) {
    // desktop only (macOS, Windows, Linux)
    win.setWindowTitle('Hindi Alphabet');
    win.setWindowMinSize(const Size(800, 1280));
    win.setWindowMaxSize(const Size(4096, 4096)); // optional
    // Centered 1280x800
    final frame = await win.getWindowInfo().then((info) {
      final screen = info.screen!;
      const w = 1170.0, h = 2532.0;
      final left =
          screen.visibleFrame.left + (screen.visibleFrame.width - w) / 2;
      final top =
          screen.visibleFrame.top + (screen.visibleFrame.height - h) / 2;
      return Rect.fromLTWH(left, top, w, h);
    });
    win.setWindowFrame(frame);
  }

  final repo = LettersRepository();
  final prefs = PrefsService();

  final letters = await repo.loadLetters();
  final rate = await prefs.loadRate(def: 160);
  final reps = await prefs.loadRepeats(def: 2);
  final delaySec = await prefs.loadDelaySec(def: 2);
  final int delayMs = (delaySec * 1000).round();

  final tts = TtsService(
      rateWpm: rate,
      repeats: reps,
      gap: Duration(milliseconds: delayMs));
  await tts.init();

  runApp(MyApp(letters: letters, tts: tts, prefs: prefs));
}

class MyApp extends StatelessWidget {
  final List<HindiLetter> letters;
  final TtsService tts;
  final PrefsService prefs;

  const MyApp(
      {super.key,
      required this.letters,
      required this.tts,
      required this.prefs});

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

  const HomePage(
      {super.key,
      required this.letters,
      required this.tts,
      required this.prefs});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _isPlaying = false;

  @override
  void initState() {
    super.initState();
    // Initialize after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        await widget.tts.init();
      } catch (e, st) {
        debugPrint('TTS init failed: $e\n$st');
      }
    });
  }
  int index = 0;

  String? _formatHint(String? hint) {
    if (hint == null) return null;
    final s = hint.trim();
    if (s.isEmpty) return null;
    final dot = s.indexOf('.');
    if (dot >= 0 && dot < s.length - 1) {
      final first = s.substring(0, dot + 1).trim();
      final second = s.substring(dot + 1).trim();
      return '$first\n$second';
    }
    return s;
  }

  @override
  Widget build(BuildContext context) {
    final letter = widget.letters[index];
    final formattedHint = _formatHint(letter.hint);
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 48,
        title: const Text('Hindi Alphabet'),
      ),
      drawer: Drawer(
        child: SafeArea(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              const DrawerHeader(
                decoration: BoxDecoration(color: Colors.blueGrey),
                child: Text(
                  'Menu',
                  style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w600),
                ),
              ),
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('About'),
                onTap: () {
                  Navigator.of(context).pop();
                  showAboutDialog(
                    context: context,
                    applicationName: 'Hindi Alphabet',
                    applicationVersion: '0.1.0',
                    children: const [Text('Learn to pronounce Hindi vowels and consonants, with audio.')],
                  );
                },
              ),
            ],
          ),
        ),
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: const EdgeInsets.only(left: 8, right: 8),
              // padding: const EdgeInsets.only(left: 8, right: 8, bottom: 8),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: SizedBox(
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Big symbol, responsive font size
                      Container(
                        // decoration: BoxDecoration(
                        //     border: Border.all(
                        //         color: Colors.purpleAccent, width: 1)),
                        child: Text(
                          letter.symbol,
                          textAlign: TextAlign.center,
                          textHeightBehavior: const TextHeightBehavior(
                            applyHeightToFirstAscent: false,
                            applyHeightToLastDescent: true,
                          ),
                          style: TextStyle(
                            // Larger Hindi symbol — target around 256 px max, scaled to 60% of screen width
                            fontSize: math.min(180.0,
                                MediaQuery.of(context).size.width * 0.50),
                            height: 0.9,
                          ),
                        ),
                      ),
                      const SizedBox(height: 6),

                      // Pronunciation + approx
                      Container(
                          // decoration: BoxDecoration(
                          //     border: Border.all(
                          //         color: Colors.orangeAccent, width: 1)),
                          // padding: const EdgeInsets.all(4),
                          child: Text(
                            "English: ${letter.pronunciation}",
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                          )),

                      // const SizedBox(height: 8),
                      Container(
                        // decoration: BoxDecoration(
                        //     border: Border.all(
                        //         color: Colors.orangeAccent, width: 1)),
                        // padding: const EdgeInsets.all(4),
                        child: Text(
                          "Say: ${letter.englishApprox}",
                          style: const TextStyle(fontSize: 18),
                          textAlign: TextAlign.center,
                        ),
                      ),

                      if (formattedHint != null)
                        Container(
                          // decoration: BoxDecoration(
                          //     border: Border.all(
                          //         color: Colors.orangeAccent, width: 1)),
                          padding: const EdgeInsets.all(4),
                          child: Text(
                            'Hint: $formattedHint',
                            textAlign: TextAlign.center,
                          ),
                        ),

                      if (letter.imageFileName != null)
                        Container(
                          // decoration: BoxDecoration(
                          //     border:
                          //         Border.all(color: Colors.green, width: 1)),
                          child: SizedBox(
                            height: math.min(220.0,
                                MediaQuery.of(context).size.height * 0.35),
                            child: Image.asset(
                              letter.imageFileName!,
                              fit: BoxFit.contain,
                              errorBuilder: (_, __, ___) =>
                                  const SizedBox.shrink(),
                            ),
                          ),
                        ),

                      if (letter.example != null)
                        Text(
                          letter.example!,
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                          textAlign: TextAlign.center,
                        ),

                      const SizedBox(height: 4),

                      // Dependent form info (matra) — show when available
                      if (letter.dependentForm != null && letter.dependentForm!.trim().isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Text(
                            'Dependent form: ${letter.dependentForm}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                          ),
                        ),

                      if (letter.dependentFormExample != null &&
                          letter.dependentFormExample!.trim().isNotEmpty &&
                          letter.dependentFormExample!.toLowerCase() != 'none' &&
                          letter.dependentFormExample! != 'None.')
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Text(
                            'Example: ${letter.dependentFormExample}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                          ),
                        ),

                      // Add a bit of bottom padding so content doesn't collide with bottom bar
                      const SizedBox(height: 16),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 20), // bottom +8
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextButton(
              style: TextButton.styleFrom(
                foregroundColor: Colors.indigo,
                disabledForegroundColor: Colors.grey,
              ),
              onPressed: index > 0 && !_isPlaying ? _prevLetter : null,
              child: const Text('Previous', style: TextStyle(fontSize: 16)),
            ),
            const SizedBox(width: 12),
      ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.indigo,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        ),
        onPressed: _isPlaying ? null : _playSound,
        child: const Text(
          'Play',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ),
            const SizedBox(width: 12),
            TextButton(
              style: TextButton.styleFrom(
                foregroundColor: Colors.indigo,
                disabledForegroundColor: Colors.grey,
              ),
              onPressed: index < widget.letters.length - 1 && !_isPlaying ? _nextLetter : null,
              child: const Text('Next', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  void _play() async {
    if (_isPlaying) {
      debugPrint('TTS already playing; ignoring Play tap');
      return;
    }
    setState(() => _isPlaying = true);
    try {
      await widget.tts.speakRepeats(widget.letters[index].symbol);
    } catch (e, stack) {
      debugPrint('Error during TTS playback: $e');
      debugPrint('$stack');
    } finally {
      if (mounted) setState(() => _isPlaying = false);
    }
  }

  void _prev() {
    if (_isPlaying) return; // block nav during TTS
    setState(() => index = (index - 1) < 0 ? 0 : index - 1);
  }

  void _next() {
    if (_isPlaying) return; // block nav during TTS
    setState(() => index = (index + 1) >= widget.letters.length ? index : index + 1);
  }

  // Wrappers to match UI callback names used in IconButtons
  void _prevLetter() => _prev();

  void _nextLetter() => _next();

  void _playSound() => _play();

  // Settings functionality removed
}

// [!] Automatically assigning platform `iOS` with version `13.0` on target `Runner` because no platform was specified. Please specify a platform for this target in your Podfile. See `https://guides.cocoapods.org/syntax/podfile.html#platform`.
//
// [!] CocoaPods did not set the base configuration of your project because your project already has a custom config set. In order for CocoaPods integration to work at all, please either set the base configurations of the target `Runner` to `Target Support Files/Pods-Runner/Pods-Runner.profile.xcconfig` or include the `Target Support Files/Pods-Runner/Pods-Runner.profile.xcconfig` in your build configuration (`Flutter/Release.xcconfig`).

//   00008110-001064683601801E</file>