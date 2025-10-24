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
