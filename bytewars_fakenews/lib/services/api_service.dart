import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Try different localhost variations for Flutter web
  static const List<String> baseUrls = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
  ];

  static Future<Map<String, dynamic>> performAnalysis({
    required String inputType,
    required String data,
  }) async {
    
    for (String baseUrl in baseUrls) {
      try {
        final url = Uri.parse('$baseUrl/analyze');
        
        print('🔗 Attempting to connect to: $url');
        
        final response = await http.post(
          url,
          headers: {
            'Content-Type': 'application/json; charset=UTF-8',
            'Access-Control-Allow-Origin': '*',
          },
          body: jsonEncode({'type': inputType, 'data': data}),
        ).timeout(Duration(seconds: 30));

        print('📡 Response status: ${response.statusCode}');
        print('📡 Response body: ${response.body}');

        if (response.statusCode == 200) {
          return jsonDecode(response.body);
        } else {
          print('❌ Server error: ${response.statusCode} - ${response.body}');
          throw Exception('Server returned ${response.statusCode}: ${response.body}');
        }
      } catch (e) {
        print('❌ Connection failed to $baseUrl: $e');
        if (baseUrl == baseUrls.last) {
          // If this is the last URL, throw the error
          throw Exception('Unable to connect to backend server. Please ensure the Python backend is running on port 8000. Error: $e');
        }
        // Otherwise, continue to the next URL
        continue;
      }
    }
    
    throw Exception('All connection attempts failed');
  }

  static Future<Map<String, dynamic>> healthCheck() async {
    for (String baseUrl in baseUrls) {
      try {
        final url = Uri.parse('$baseUrl/health');
        final response = await http.get(url).timeout(Duration(seconds: 10));
        
        if (response.statusCode == 200) {
          return jsonDecode(response.body);
        }
      } catch (e) {
        print('Health check failed for $baseUrl: $e');
        continue;
      }
    }
    throw Exception('Backend server is not responding');
  }
}
