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
