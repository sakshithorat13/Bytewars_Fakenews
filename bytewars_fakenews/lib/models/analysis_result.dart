enum VerdictStatus { Contradicted, Supported, InsufficientInfo, Mixed }

class ClaimAnalysis {
  final String claim;
  final VerdictStatus verdict;
  final String explanation;

  ClaimAnalysis({
    required this.claim,
    required this.verdict,
    required this.explanation,
  });

  factory ClaimAnalysis.fromJson(Map<String, dynamic> json) {
    VerdictStatus parseVerdict(String verdict) {
      switch (verdict.toLowerCase()) {
        case 'contradicted':
          return VerdictStatus.Contradicted;
        case 'supported':
          return VerdictStatus.Supported;
        case 'mixed':
          return VerdictStatus.Mixed;
        case 'insufficientinfo':
        case 'insufficient info':
        default:
          return VerdictStatus.InsufficientInfo;
      }
    }

    try {
      return ClaimAnalysis(
        claim: json['claim'] is String && json['claim'].isNotEmpty
            ? json['claim']
            : 'No specific claim identified',
        verdict:
            parseVerdict(json['verdict']?.toString() ?? 'InsufficientInfo'),
        explanation:
            json['explanation'] is String && json['explanation'].isNotEmpty
                ? json['explanation']
                : 'Unable to provide detailed analysis.',
      );
    } catch (e) {
      print('Error parsing ClaimAnalysis: $e');
      return ClaimAnalysis(
        claim: 'Error processing claim',
        verdict: VerdictStatus.InsufficientInfo,
        explanation: 'There was an issue analyzing this claim.',
      );
    }
  }

  String get verdictText {
    switch (verdict) {
      case VerdictStatus.Supported:
        return 'Supported';
      case VerdictStatus.Contradicted:
        return 'Contradicted';
      case VerdictStatus.Mixed:
        return 'Mixed Evidence';
      case VerdictStatus.InsufficientInfo:
        return 'Needs More Info';
    }
  }

  String get friendlyExplanation {
    if (explanation.isEmpty ||
        explanation == 'Unable to provide detailed analysis.') {
      switch (verdict) {
        case VerdictStatus.Supported:
          return 'This claim appears to be backed by available evidence.';
        case VerdictStatus.Contradicted:
          return 'This claim appears to contradict established facts.';
        case VerdictStatus.Mixed:
          return 'This claim contains both accurate and questionable elements.';
        case VerdictStatus.InsufficientInfo:
          return 'We need more reliable sources to verify this claim properly.';
      }
    }
    return explanation;
  }
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

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    try {
      // Provide safe defaults for all fields
      int score = 50;
      String overallVerdict = 'Needs Review';
      String summary =
          'Analysis completed but needs more information for detailed verification.';
      List<ClaimAnalysis> breakdown = [];
      String? context;

      // Safely extract score
      if (json.containsKey('score')) {
        final scoreValue = json['score'];
        if (scoreValue is int) {
          score = scoreValue;
        } else if (scoreValue is double) {
          score = scoreValue.round();
        } else if (scoreValue is String) {
          score = int.tryParse(scoreValue) ?? 50;
        }
      }

      // Safely extract verdict
      if (json.containsKey('overallVerdict') &&
          json['overallVerdict'] is String) {
        overallVerdict = json['overallVerdict'];
      }

      // Safely extract summary
      if (json.containsKey('summary') &&
          json['summary'] is String &&
          json['summary'].isNotEmpty) {
        summary = json['summary'];
      }

      // Safely extract breakdown
      if (json.containsKey('breakdown') && json['breakdown'] is List) {
        final breakdownList = json['breakdown'] as List;
        breakdown = breakdownList
            .where((item) => item is Map<String, dynamic>)
            .map((item) => ClaimAnalysis.fromJson(item as Map<String, dynamic>))
            .toList();
      }

      // If no breakdown items, create a default one
      if (breakdown.isEmpty) {
        breakdown = [
          ClaimAnalysis(
            claim: 'General content analysis',
            verdict: VerdictStatus.InsufficientInfo,
            explanation:
                'Unable to identify specific factual claims for detailed verification.',
          )
        ];
      }

      // Safely extract context
      if (json.containsKey('context') && json['context'] is String) {
        context = json['context'];
      }

      return AnalysisResult(
        score: score,
        overallVerdict: overallVerdict,
        summary: summary,
        breakdown: breakdown,
        context: context,
      );
    } catch (e) {
      print('Error parsing AnalysisResult: $e');
      // Return a safe fallback result
      return AnalysisResult(
        score: 50,
        overallVerdict: 'Analysis Error',
        summary:
            'There was an issue processing the analysis. Please try again.',
        breakdown: [
          ClaimAnalysis(
            claim: 'Unable to process content',
            verdict: VerdictStatus.InsufficientInfo,
            explanation:
                'An error occurred during analysis. Please try again with different content.',
          )
        ],
        context: null,
      );
    }
  }

  String get friendlySummary {
    if (summary.isEmpty) {
      return getDefaultSummary();
    }
    return summary;
  }

  String getDefaultSummary() {
    if (score >= 80) {
      return "The information appears to be largely accurate based on available evidence.";
    } else if (score >= 60) {
      return "Most of the information seems reliable, but some claims need verification.";
    } else if (score >= 40) {
      return "The information contains a mix of accurate and questionable content.";
    } else if (score >= 20) {
      return "Several claims in this content appear to be problematic or misleading.";
    } else {
      return "This content contains significant factual issues that contradict established evidence.";
    }
  }

  String get scoreDescription {
    if (score >= 80) {
      return "Highly Reliable";
    } else if (score >= 60) {
      return "Mostly Reliable";
    } else if (score >= 40) {
      return "Mixed Reliability";
    } else if (score >= 20) {
      return "Low Reliability";
    } else {
      return "Unreliable";
    }
  }
}
