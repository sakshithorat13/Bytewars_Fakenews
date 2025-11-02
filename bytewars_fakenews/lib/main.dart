import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'models/analysis_result.dart';
import 'screens/input_screen.dart';
import 'screens/loading_screen.dart';
import 'screens/results_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Veritas',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
        textTheme: GoogleFonts.latoTextTheme(),
      ),
      home: const VeritasApp(),
      debugShowCheckedModeBanner: false,
    );
  }
}

enum AppState { input, loading, results }

class VeritasApp extends StatefulWidget {
  const VeritasApp({Key? key}) : super(key: key);

  @override
  State<VeritasApp> createState() => _VeritasAppState();
}

class _VeritasAppState extends State<VeritasApp> {
  AppState _appState = AppState.input;

  final AnalysisResult _mockResult = AnalysisResult(
    score: 65,
    overallVerdict: 'Partially True',
    summary: 'The content contains some verifiable facts but also includes misleading statements that require context.',
    breakdown: [
      ClaimAnalysis(
        claim: 'The Earth revolves around the Sun',
        verdict: VerdictStatus.Supported,
        explanation: 'This is a well-established scientific fact supported by centuries of astronomical observations and research.',
      ),
      ClaimAnalysis(
        claim: 'Vaccines cause autism',
        verdict: VerdictStatus.Contradicted,
        explanation: 'This claim has been thoroughly debunked by numerous peer-reviewed studies. The original study that suggested this link was retracted due to fraudulent data.',
      ),
      ClaimAnalysis(
        claim: 'Climate change is accelerating',
        verdict: VerdictStatus.Supported,
        explanation: 'Scientific consensus and data from multiple sources confirm that global temperatures are rising at an unprecedented rate due to human activities.',
      ),
      ClaimAnalysis(
        claim: 'Ancient civilizations had smartphones',
        verdict: VerdictStatus.InsufficientInfo,
        explanation: 'There is no credible archaeological or historical evidence to support this claim. While ancient civilizations were advanced, there is no proof of modern technology.',
      ),
    ],
    context: 'Analysis based on cross-referencing with scientific journals, fact-checking databases, and verified news sources. Last updated: 2024.',
  );

  void _handleAnalyze() {
    setState(() {
      _appState = AppState.loading;
    });

    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) {
        setState(() {
          _appState = AppState.results;
        });
      }
    });
  }

  void _handleBackToInput() {
    setState(() {
      _appState = AppState.input;
    });
  }

  @override
  Widget build(BuildContext context) {
    switch (_appState) {
      case AppState.input:
        return InputScreen(onAnalyze: _handleAnalyze);
      case AppState.loading:
        return LoadingScreen(onBack: _handleBackToInput);
      case AppState.results:
        return ResultsScreen(result: _mockResult, onBack: _handleBackToInput);
    }
  }
}
