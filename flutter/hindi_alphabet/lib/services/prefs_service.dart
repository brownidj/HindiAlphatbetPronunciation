import 'package:flutter/foundation.dart';
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

  // Notes:
  //  - _kTtsRateWpm stores integer WPM (10..210)
  //  - _kTtsDelaySec actually stores milliseconds (historical name)

  /// Load saved mode ('vowels' | 'consonants' | 'both'); defaults to 'both'.
  Future<String> loadMode({String def = 'both'}) async {
    final sp = await SharedPreferences.getInstance();
    final val = sp.getString('mode');
    if (val == 'vowels' || val == 'consonants' || val == 'both') {
      return val!;
    }
    return def;
  }

  /// Persist current mode.
  Future<void> saveMode(String value) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setString('mode', value);
  }

  // ---- Rate (WPM) ----
  Future<int> loadRate({int def = kDefaultTtsRateWpm}) async {
    final p = await SharedPreferences.getInstance();
    final v = p.getInt(_kTtsRateWpm) ?? def;
    final clamped = v.clamp(10, 210).toInt();
    debugPrint('Loaded speech rate: $clamped WPM');
    return clamped;
  }

  Future<void> saveRate(int value) async {
    final p = await SharedPreferences.getInstance();
    final clamped = value.clamp(10, 210).toInt();
    await p.setInt(_kTtsRateWpm, clamped);
    debugPrint('Saved speech rate: $clamped WPM');
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

  // ---- Delay (milliseconds, integer) ----
  Future<int> loadDelayMs({int def = kDefaultTtsDelayMs}) async {
    final p = await SharedPreferences.getInstance();
    return p.getInt(_kTtsDelaySec) ?? def;
  }
  Future<void> saveDelayMs(int value) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kTtsDelaySec, value);
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