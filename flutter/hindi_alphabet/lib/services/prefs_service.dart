import 'package:shared_preferences/shared_preferences.dart';
import '../config/constants.dart';

/// Simple key–value settings store using shared_preferences.
/// Replace your existing PrefsService with this version (names match your code).
class PrefsService {
  // Keys
  static const _kTtsRateWpm   = 'tts_rate_wpm';
  static const _kTtsRepeats   = 'tts_repeats';
  static const _kTtsDelaySec  = 'tts_delay_sec';
  static const _kContinuous   = 'continuous_mode';

  // ---- Rate (WPM) ----
  Future<int> loadRate({int def = kDefaultTtsRateWpm}) async {
    final p = await SharedPreferences.getInstance();
    return p.getInt(_kTtsRateWpm) ?? def;
  }
  Future<void> saveRate(int value) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kTtsRateWpm, value);
  }

  // ---- Repeats ----
  Future<int> loadRepeats({int def = kDefaultTtsRepeats}) async {
    final p = await SharedPreferences.getInstance();
    return p.getInt(_kTtsRepeats) ?? def;
  }
  Future<void> saveRepeats(int value) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kTtsRepeats, value);
  }

  // ---- Delay (seconds, double to allow 0.5 steps if needed) ----
  Future<int> loadDelaySec({int def = kDefaultTtsDelaySec}) async {
    final p = await SharedPreferences.getInstance();
    return p.getInt(_kTtsDelaySec) ?? def;
  }
  Future<void> saveDelaySec(double value) async {
    final p = await SharedPreferences.getInstance();
    await p.setDouble(_kTtsDelaySec, value);
  }

  // ---- Continuous auto-play ----
  Future<bool> loadContinuous({bool def = kDefaultContinuous}) async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kContinuous) ?? def;
  }
  Future<void> saveContinuous(bool value) async {
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kContinuous, value);
  }
}