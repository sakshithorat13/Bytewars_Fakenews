enum VerdictStatus { Contradicted, Supported, InsufficientInfo }

class ClaimAnalysis {
  final String claim;
  final VerdictStatus verdict;
  final String explanation;

  ClaimAnalysis({
    required this.claim,
    required this.verdict,
    required this.explanation,
  });
}

class AnalysisResult {
  final int score;
  final String overallVerdict;
  final String summary;
  final List<ClaimAnalysis> breakdown;
  final String? context;

  AnalysisResult({
    required this.score,
    required this.overallVerdict,
    required this.summary,
    required this.breakdown,
    this.context,
  });
}
