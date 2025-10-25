import 'dart:async';
import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  final FlutterTts _tts = FlutterTts();

  int _rateWpm;
  int repeats;
  Duration gap;

  TtsService({
    int rateWpm = 160,
    this.repeats = 2,
    Duration? gap,
  })  : _rateWpm = rateWpm,
        gap = gap ?? const Duration(milliseconds: 2000);

  int get rateWpm => _rateWpm;
  set rateWpm(int v) {
    _rateWpm = v;
    // Apply immediately in background (no await needed)
    unawaited(_applyRate());
  }

  Future<void> init() async {
    // Recommended defaults
    await _tts.setSharedInstance(true);          // iOS/macOS: reuse engine
    await _tts.setLanguage('hi-IN');             // Hindi
    await _tts.awaitSpeakCompletion(true);       // await finish
    // Optional: keep audio in playback category on iOS
    try {
      await _tts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playback,
        [
          IosTextToSpeechAudioCategoryOptions.defaultToSpeaker,
          IosTextToSpeechAudioCategoryOptions.duckOthers,
        ],
        IosTextToSpeechAudioMode.defaultMode,
      );
    } catch (_) {}

    // Apply initial rate
    await _applyRate();
  }

  /// Map user WPM (40–240) to engine rate (~0.2–0.8).
  double _mapWpmToEngineRate(int wpm) {
    final clamped = wpm.clamp(10, 200);
    const inMin = 10, inMax = 200;
    const outMin = 0.20, outMax = 0.80;
    return outMin + (clamped - inMin) * (outMax - outMin) / (inMax - inMin);
  }

  Future<void> _applyRate() async {
    final engineRate = _mapWpmToEngineRate(_rateWpm);
    await _tts.setSpeechRate(engineRate);
  }

  Future<void> speakRepeats(String text) async {
    // Ensure the latest rate & gap are applied before playing
    await _applyRate();

    for (var i = 0; i < repeats; i++) {
      await _tts.stop();        // clear any queued speech
      await _tts.speak(text);   // will await due to awaitSpeakCompletion(true)
      if (i < repeats - 1) {
        await Future.delayed(gap);
      }
    }
  }

  /// Set the underlying engine speech rate directly (0.0–1.0).
  /// Useful for extra-slow turtle mode beyond normal WPM mapping.
  Future<void> setRawEngineRate(double rate) async {
    final r = rate.clamp(0.01, 1.0);
    try {
      await _tts.setSpeechRate(r);
    } catch (_) {}
  }

  Future<void> stop() => _tts.stop();
}