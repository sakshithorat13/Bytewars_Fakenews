import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'models/analysis_result.dart';
import 'screens/input_screen.dart';
import 'screens/loading_screen.dart';
import 'screens/results_screen.dart';
import 'services/api_service.dart';

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

enum AppState { input, loading, results, error }

class VeritasApp extends StatefulWidget {
  const VeritasApp({Key? key}) : super(key: key);

  @override
  State<VeritasApp> createState() => _VeritasAppState();
}

class _VeritasAppState extends State<VeritasApp> {
  AppState _appState = AppState.input;
  AnalysisResult? _analysisResult;
  String _errorMessage = '';

  void _handleAnalyze(String inputType, String data) async {
    setState(() {
      _appState = AppState.loading;
      _errorMessage = '';
    });

    try {
      print('🔍 Starting analysis for type: $inputType');
      final response = await ApiService.performAnalysis(
        inputType: inputType,
        data: data,
      );

      print('✅ Analysis response received: $response');

      // Validate response structure before parsing
      if (response is! Map<String, dynamic>) {
        throw Exception('Invalid response format from server');
      }

      // Check if it's an error response disguised as success
      if (response.containsKey('detail') &&
          response.containsKey('status_code')) {
        throw Exception(response['detail'] ?? 'Server error occurred');
      }

      final result = AnalysisResult.fromJson(response);

      setState(() {
        _analysisResult = result;
        _appState = AppState.results;
      });
    } catch (e) {
      print('❌ Analysis failed: $e');

      // Try to extract user-friendly error message
      String userFriendlyError = e.toString();

      // Check if the error contains JSON detail
      if (userFriendlyError.contains('"detail":')) {
        try {
          // Extract the detail from JSON error
          final RegExp detailRegex = RegExp(r'"detail":"([^"]*)"');
          final match = detailRegex.firstMatch(userFriendlyError);
          if (match != null) {
            userFriendlyError = match.group(1) ?? userFriendlyError;
            // Decode escaped characters
            userFriendlyError = userFriendlyError.replaceAll(r'\n', '\n');
            userFriendlyError = userFriendlyError.replaceAll(r'\"', '"');
          }
        } catch (parseError) {
          print('Could not parse error details: $parseError');
        }
      }

      // Make error more user-friendly
      if (userFriendlyError.contains('Resource exhausted')) {
        userFriendlyError =
            'The AI service is currently busy. Please try again in a few moments.';
      } else if (userFriendlyError.contains('403') ||
          userFriendlyError.contains('Forbidden')) {
        userFriendlyError =
            'Unable to access the webpage. The site may be blocking automated requests.';
      } else if (userFriendlyError.contains('timeout')) {
        userFriendlyError =
            'The request took too long. Please try again or check your internet connection.';
      } else if (userFriendlyError.contains('connection')) {
        userFriendlyError =
            'Cannot connect to the analysis server. Please ensure you\'re connected to the internet.';
      }

      setState(() {
        _errorMessage = userFriendlyError;
        _appState = AppState.error;
      });
    }
  }

  void _handleBackToInput() {
    setState(() {
      _appState = AppState.input;
      _analysisResult = null;
      _errorMessage = '';
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
        return ResultsScreen(
          result: _analysisResult!,
          onBack: _handleBackToInput,
        );
      case AppState.error:
        return _buildErrorScreen(context);
    }
  }

  Widget _buildErrorScreen(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Error'),
        backgroundColor: Colors.red.shade600,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red.shade600,
            ),
            const SizedBox(height: 20),
            Text(
              'Analysis Failed',
              style: GoogleFonts.lato(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.red.shade800,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              _errorMessage,
              style: GoogleFonts.lato(
                fontSize: 16,
                color: Colors.grey.shade700,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: _handleBackToInput,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue.shade600,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: 16,
                ),
              ),
              child: Text(
                'Try Again',
                style: GoogleFonts.lato(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
