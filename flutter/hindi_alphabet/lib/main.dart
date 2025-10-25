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
      const w = 1170.0,
          h = 2532.0;
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
  final delayMs = await prefs.loadDelayMs(def: 2000);

  final tts = TtsService(
      rateWpm: rate, repeats: reps, gap: Duration(milliseconds: delayMs));
  await tts.init();

  runApp(MyApp(letters: letters, tts: tts, prefs: prefs));
}

class MyApp extends StatelessWidget {
  final List<HindiLetter> letters;
  final TtsService tts;
  final PrefsService prefs;

  const MyApp({super.key,
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

  const HomePage({super.key,
    required this.letters,
    required this.tts,
    required this.prefs});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _isPlaying = false;
  bool _slowMode = false;
  bool _autoMode = false;

  // Track visible indices and counts for vowels/consonants.
  List<int> _visible = [];
  int _vowelCount = 0;
  int _consonantCount = 0;
  int _rateWpm = 160; // persisted speech rate (WPM), clamped to 10..190

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        // Load saved mode first (default to 'both')
        final savedMode = await widget.prefs.loadMode(def: 'both');
        if (mounted) setState(() => _mode = savedMode);

        // Initialize TTS
        await widget.tts.init();

        // Load preferences for repeats, delay, and rate
        final r = await widget.prefs.loadRepeats(def: 2);
        final dMs = await widget.prefs.loadDelayMs(def: 2000);
        final rWpm = await widget.prefs.loadRate(def: 160);

        if (mounted) {
          setState(() {
            _repeats = r.clamp(1, 10);
            _delayMs = dMs.clamp(500, 5000);
            _rateWpm = rWpm.clamp(10, 210);
          });
        }

        // Apply loaded preferences to TTS
        widget.tts.rateWpm = _rateWpm;
        widget.tts.repeats = _repeats;
        widget.tts.gap = Duration(milliseconds: _delayMs);

        debugPrint(
            'Loaded TTS prefs -> rate=$_rateWpm WPM, repeats=$_repeats, delay=$_delayMs ms, mode=$_mode');
      } catch (e, st) {
        debugPrint('Init error: $e\n$st');
      }
    });
  }

  int index = 0;

  // Mode: 'vowels', 'consonants', or 'both'
  String _mode = 'both';

  // Rebuild _visible and update counts.
  void _rebuildVisible() {
    _vowelCount = widget.letters
        .where((e) => (e.type ?? '').toLowerCase() == 'vowel')
        .length;
    _consonantCount = widget.letters
        .where((e) => (e.type ?? '').toLowerCase() == 'consonant')
        .length;
    final wantVowel = _mode == 'vowels';
    final wantCons = _mode == 'consonants';
    _visible = [];
    for (var i = 0; i < widget.letters.length; i++) {
      final t = (widget.letters[i].type ?? '').toLowerCase();
      final isVowel = t == 'vowel';
      if (_mode == 'both' || (wantVowel && isVowel) || (wantCons && !isVowel)) {
        _visible.add(i);
      }
    }
    if (_visible.isEmpty) {
      _visible = List<int>.generate(widget.letters.length, (i) => i);
    }
    if (index >= _visible.length) index = 0;
    setState(() {});
  }

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
    if (_visible.isEmpty) {
      _rebuildVisible();
    }
    final int effectiveIndex = (_visible.isNotEmpty)
        ? (_visible.contains(index) ? index : _visible.first)
        : index;
    final letter = widget.letters[effectiveIndex];
    final formattedHint = _formatHint(letter.hint);
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 48,
        title: const Text('Hindi Alphabet'),
      ),
      // Drawer with compact Playback Timing layout (use OPTION_COMPACT_LAYOUT markers to toggle standard vs compact)
      drawer: Drawer(
        child: SafeArea(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              const DrawerHeader(
                decoration: BoxDecoration(color: Colors.blueGrey),
                child: Text(
                  'Menu',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w600),
                ),
              ),

              // ===== Mode selection group with counts (compact horizontal layout) -- moved to top =====
              const Padding(
                //  this.left, this.top, this.right, this.bottom
                padding: EdgeInsets.fromLTRB(8, 8, 8, 2),
                child: Text(
                  'Mode',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
                ),
              ),
              Padding(
                padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    Tooltip(
                      message: 'Vowels ($_vowelCount)',
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Radio<String>(
                            materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                            visualDensity: VisualDensity.compact,
                            value: 'vowels',
                            groupValue: _mode,
                            onChanged: (v) {
                              setState(() {
                                _mode = v!;
                              });
                              _rebuildVisible();
                              // persist mode selection
                              widget.prefs.saveMode(_mode);
                              // jump to first item of new filter set
                              if (_visible.isNotEmpty) {
                                setState(() {
                                  index = _visible.first;
                                });
                              }
                              Navigator.of(context).maybePop();
                            },
                          ),
                          const Text('स्वर', style: TextStyle(fontSize: 13)),
                        ],
                      ),
                    ),
                    Tooltip(
                      message: 'Consonants ($_consonantCount)',
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Radio<String>(
                            materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                            visualDensity: VisualDensity.compact,
                            value: 'consonants',
                            groupValue: _mode,
                            onChanged: (v) {
                              setState(() {
                                _mode = v!;
                              });
                              _rebuildVisible();
                              // persist mode selection
                              widget.prefs.saveMode(_mode);
                              // jump to first item of new filter set
                              if (_visible.isNotEmpty) {
                                setState(() {
                                  index = _visible.first;
                                });
                              }
                              Navigator.of(context).maybePop();
                            },
                          ),
                          const Text('व्यंजन', style: TextStyle(
                              fontSize: 13)),
                        ],
                      ),
                    ),
                    Tooltip(
                      message: 'Both vowels and consonants',
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Radio<String>(
                            materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                            visualDensity: VisualDensity.compact,
                            value: 'both',
                            groupValue: _mode,
                            onChanged: (v) {
                              setState(() {
                                _mode = v!;
                              });
                              _rebuildVisible();
                              // persist mode selection
                              widget.prefs.saveMode(_mode);
                              // jump to first item of new filter set
                              if (_visible.isNotEmpty) {
                                setState(() {
                                  index = _visible.first;
                                });
                              }
                              Navigator.of(context).maybePop();
                            },
                          ),
                          const Text('दोनों', style: TextStyle(fontSize: 13)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 8.0),
                child: Divider(height: 2, thickness: 0.6),
              ),

              // ===== WPM SLIDER START =====
              const Padding(
                padding: EdgeInsets.fromLTRB(8, 8, 8, 2),
                child: Text(
                  'Speech Rate (WPM)',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
                ),
              ),
              Padding(
                padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Icon(Icons.speed, size: 20),
                    Expanded(
                      child: Slider(
                        min: 10,
                        max: 210,
                        // 20-WPM increments across 10..190 → (190-10)/20 = 9 divisions
                        divisions: 5,
                        value: _rateWpm.clamp(10, 210).toDouble(),
                        label: '$_rateWpm WPM',
                        onChanged: _isPlaying
                            ? null
                            : (v) {
                          setState(
                                  () => _rateWpm = v.round().clamp(10, 210));
                          // Apply live so the user hears the change immediately
                          widget.tts.rateWpm = _rateWpm;
                        },
                        onChangeEnd: (v) async {
                          final next = v.round().clamp(10, 210);
                          await widget.prefs.saveRate(next); // ← persist
                          widget.tts.rateWpm =
                              next; // ensure engine is in sync
                          if (mounted) setState(() => _rateWpm = next);
                          debugPrint(
                              'Speech rate set to $next WPM (persisted)');
                        },
                      ),
                    ),
                    Text(
                      '$_rateWpm',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 8.0),
                child: Divider(height: 2, thickness: 0.6),
              ),
              // ===== WPM SLIDER END =====

              // ===== OPTION_COMPACT_LAYOUT_START =====
              // Compact Playback Timing section (smaller icons, tighter padding)
              const Padding(
                padding: EdgeInsets.fromLTRB(8, 8, 8, 2),
                child: Text(
                  'Playback Timing',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
                ),
              ),

              // Repeats control row
              Padding(
                padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Repeats (1-10)'),
                    Row(
                      children: [
                        IconButton(
                          icon: const Icon(Icons.remove, size: 18),
                          tooltip: 'Decrease repeats',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                              width: 28, height: 28),
                          visualDensity:
                          const VisualDensity(horizontal: -4, vertical: -4),
                          onPressed: _isPlaying
                              ? null
                              : () =>
                              _changeRepeats((_repeats - 1).clamp(1, 10)),
                        ),
                        const SizedBox(width: 6),
                        Text('$_repeats',
                            style:
                            const TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(width: 6),
                        IconButton(
                          icon: const Icon(Icons.add, size: 18),
                          tooltip: 'Increase repeats',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                              width: 28, height: 28),
                          visualDensity:
                          const VisualDensity(horizontal: -4, vertical: -4),
                          onPressed: _isPlaying
                              ? null
                              : () =>
                              _changeRepeats((_repeats + 1).clamp(1, 10)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Delay control row (500ms steps)
              Padding(
                padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Play Delay (1 - 5 sec)'),
                    Row(
                      children: [
                        IconButton(
                          icon: const Icon(Icons.remove, size: 18),
                          tooltip: 'Decrease delay',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                              width: 28, height: 28),
                          visualDensity:
                          const VisualDensity(horizontal: -4, vertical: -4),
                          onPressed: _isPlaying
                              ? null
                              : () =>
                              _changeDelayMs(
                                  (_delayMs - 500).clamp(1000, 5000)),
                        ),
                        const SizedBox(width: 6),
                        Text('${(_delayMs / 1000).toStringAsFixed(1)} sec',
                            style:
                            const TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(width: 6),
                        IconButton(
                          icon: const Icon(Icons.add, size: 18),
                          tooltip: 'Increase delay',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                              width: 28, height: 28),
                          visualDensity:
                          const VisualDensity(horizontal: -4, vertical: -4),
                          onPressed: _isPlaying
                              ? null
                              : () =>
                              _changeDelayMs(
                                  (_delayMs + 500).clamp(500, 5000)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(top: 8.0),
                child: Divider(height: 2, thickness: 0.6),
              ),
              // ===== OPTION_COMPACT_LAYOUT_END =====

              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('About'),
                onTap: () {
                  Navigator.of(context).pop();
                  showAboutDialog(
                    context: context,
                    applicationName: 'Hindi Alphabet',
                    applicationVersion: '0.1.0',
                    children: const [
                      Text(
                          'Learn to pronounce Hindi vowels and consonants, with audio.')
                    ],
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
                      // Mode indicator with tooltip
                      Padding(
                        padding: const EdgeInsets.only(top: 4.0, bottom: 4.0),
                        child: Tooltip(
                          message: _mode == 'vowels'
                              ? 'Vowels'
                              : _mode == 'consonants'
                              ? 'Consonants'
                              : 'Both vowels and consonants',
                          child: Text(
                            _mode == 'vowels'
                                ? 'स्वर'
                                : _mode == 'consonants'
                                ? 'व्यंजन'
                                : 'दोनों',
                            style: const TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w500),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      ),
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
                                MediaQuery
                                    .of(context)
                                    .size
                                    .width * 0.50),
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
                            style: const TextStyle(
                                fontSize: 18, fontWeight: FontWeight.w600),
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
                          alignment: Alignment.center,
                          child: SizedBox(
                            height: 220,
                            child: Center(
                              child: Image.asset(
                                letter.imageFileName!,
                                fit: BoxFit.contain,
                                errorBuilder: (_, __, ___) =>
                                const SizedBox.shrink(),
                              ),
                            ),
                          ),
                        ),

                      if (letter.example != null)
                        Text(
                          letter.example!,
                          style: const TextStyle(
                              fontSize: 18, fontWeight: FontWeight.w600),
                          textAlign: TextAlign.center,
                        ),

                      const SizedBox(height: 4),

                      // Dependent form info (matra) — show when available
                      if (letter.dependentForm != null &&
                          letter.dependentForm!.trim().isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: RichText(
                            textAlign: TextAlign.center,
                            text: TextSpan(
                              children: [
                                TextSpan(
                                  text: 'Dependent form: ',
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                    color: Colors.black,
                                  ),
                                ),
                                TextSpan(
                                  text: letter.dependentForm ?? '',
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.black,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                      if (letter.dependentFormExample != null &&
                          letter.dependentFormExample!.trim().isNotEmpty &&
                          letter.dependentFormExample!.toLowerCase() !=
                              'none' &&
                          letter.dependentFormExample! != 'None.')
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Text(
                            'Example: ${letter.dependentFormExample}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 14, fontWeight: FontWeight.w600),
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
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Tooltip(
                message: 'Previous',
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF6270BB),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 10),
                  ),
                  onPressed: !_isPlaying ? _prevLetter : null,
                  child: const Icon(Icons.chevron_left, size: 30),
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.indigo, // 6270BBFF
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 20, vertical: 10),
                ),
                onPressed: _isPlaying ? null : _playSound,
                child: const Text(
                  'Play',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 12),
              Tooltip(
                message: 'Next',
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF6270BB),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 10),
                  ),
                  onPressed: !_isPlaying ? _nextLetter : null,
                  child: const Icon(Icons.chevron_right, size: 30),
                ),
              ),
              // 🐢 Slow TTS button
              const SizedBox(width: 12),
              Tooltip(
                message: 'Slower playback - click on/off',
                child: TextButton(
                  style: ButtonStyle(
                    backgroundColor: MaterialStateProperty.resolveWith<
                        Color?>(
                          (states) {
                        if (states.contains(MaterialState.disabled)) {
                          return Colors.grey.shade200;
                        }
                        return _slowMode ? Colors.indigo.shade100 : null;
                      },
                    ),
                    foregroundColor: MaterialStateProperty.resolveWith<
                        Color?>(
                          (states) {
                        if (states.contains(MaterialState.disabled)) {
                          return Colors.grey;
                        }
                        return _slowMode ? Colors.indigo.shade900 : Colors
                            .indigo;
                      },
                    ),
                  ),
                  onPressed: !_isPlaying ? _toggleSlowTts : null,
                  child: const Text('🐢', style: TextStyle(fontSize: 30)),
                ),
              ),
              const SizedBox(width: 12),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Auto',
                    style: TextStyle(
                        fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                  Padding(
                    padding: EdgeInsets.only(top: 0),
                    child: Radio<bool>(
                      value: true,
                      groupValue: _autoMode,
                      visualDensity: VisualDensity(horizontal: 0, vertical: -4),
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      onChanged: (v) {
                        setState(() {
                          _autoMode = !_autoMode;
                        });
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
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
      // Push latest timing to TTS
      widget.tts.rateWpm = _rateWpm.clamp(10, 210);
      widget.tts.repeats = _repeats;
      widget.tts.gap = Duration(milliseconds: _delayMs);
    } catch (_) {}
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
    if (_isPlaying) return;
    if (_visible.isEmpty) return;
    int cur = index;
    if (!_visible.contains(cur)) {
      cur = _visible.first;
      setState(() => index = cur);
    }
    final currentPos = _visible.indexOf(cur);
    final prevPos = (currentPos - 1 + _visible.length) % _visible.length;
    setState(() => index = _visible[prevPos]);
  }

  void _next() {
    if (_isPlaying) return;
    if (_visible.isEmpty) return;
    int cur = index;
    if (!_visible.contains(cur)) {
      cur = _visible.first;
      setState(() => index = cur);
    }
    final currentPos = _visible.indexOf(cur);
    final nextPos = (currentPos + 1) % _visible.length;
    setState(() => index = _visible[nextPos]);
  }

  // Wrappers to match UI callback names used in IconButtons
  void _prevLetter() => _prev();

  void _nextLetter() => _next();

  void _playSound() => _play();

  // Toggle slow TTS mode with segmented playback when ON
  void _toggleSlowTts() async {
    setState(() {
      _slowMode = !_slowMode;
    });
    if (_slowMode) {
      debugPrint('🐢 Slow TTS toggled ON → segmented phoneme mode');
      // Break the symbol into phonemes or syllables for clarity.
      final symbol = widget.letters[index].symbol;
      final segments = _segmentPhonemes(symbol);
      debugPrint('🐢 Segmented into ${segments.length} parts: $segments');
      for (final s in segments) {
        await widget.tts.speakRepeats(s);
        await Future.delayed(const Duration(milliseconds: 500));
      }
    } else {
      debugPrint('🐢 Slow TTS toggled OFF → normal mode');
      final wpm = _rateWpm.clamp(10, 210);
      widget.tts.rateWpm = wpm;
    }
  }

  /// Helper to roughly segment a Hindi symbol into phoneme or syllable parts.
  List<String> _segmentPhonemes(String text) {
    // For simple Hindi letters, treat each combining character as a segment.
    final buffer = <String>[];
    final runes = text.runes.toList();
    for (int i = 0; i < runes.length; i++) {
      final ch = String.fromCharCode(runes[i]);
      // Basic heuristic: if it's a vowel sign (matra), attach it to the previous character.
      if (RegExp(r'[\u093e-\u094c\u0962\u0963]').hasMatch(ch) &&
          buffer.isNotEmpty) {
        buffer[buffer.length - 1] += ch;
      } else {
        buffer.add(ch);
      }
    }
    return buffer;
  }

  // Example settings state
  int _repeats = 2;
  int _delayMs = 2000;

  /// Change the number of repeats, min 1, max 10.
  Future<void> _changeRepeats(int next) async {
    if (next != _repeats) {
      setState(() => _repeats = next);
      try {
        await widget.prefs.saveRepeats(_repeats);
      } catch (_) {}
      // keep TTS up-to-date if idle
      if (!_isPlaying) {
        try {
          widget.tts.repeats = _repeats;
        } catch (_) {}
      }
    }
  }

  /// Change delay in ms, min 500, max 5000.
  Future<void> _changeDelayMs(int next) async {
    if (next != _delayMs) {
      setState(() => _delayMs = next);
      try {
        await widget.prefs.saveDelayMs(_delayMs);
      } catch (_) {}
      // keep TTS up-to-date if idle
      if (!_isPlaying) {
        try {
          widget.tts.gap = Duration(milliseconds: _delayMs);
        } catch (_) {}
      }
    }
  }
}

// [!] Automatically assigning platform `iOS` with version `13.0` on target `Runner` because no platform was specified. Please specify a platform for this target in your Podfile. See `https://guides.cocoapods.org/syntax/podfile.html#platform`.
//
// [!] CocoaPods did not set the base configuration of your project because your project already has a custom config set. In order for CocoaPods integration to work at all, please either set the base configurations of the target `Runner` to `Target Support Files/Pods-Runner/Pods-Runner.profile.xcconfig` or include the `Target Support Files/Pods-Runner/Pods-Runner.profile.xcconfig` in your build configuration (`Flutter/Release.xcconfig`).

//   00008110-001064683601801E</file>
