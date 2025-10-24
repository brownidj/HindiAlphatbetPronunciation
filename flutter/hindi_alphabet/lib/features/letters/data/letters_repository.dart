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
