import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter/foundation.dart';

class JokeCloudFunctionService {
  final FirebaseFunctions _functions = FirebaseFunctions.instance;

  Future<bool> createJoke({
    required String setupText,
    required String punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
  }) async {
    try {
      final callable = _functions.httpsCallable('create-joke');

      final result = await callable.call({
        'joke_data': {
          'setup_text': setupText, 
          'punchline_text': punchlineText,
          'setup_image_url': setupImageUrl,
          'punchline_image_url': punchlineImageUrl,
        },
      });

      debugPrint('Joke created successfully: ${result.data}');
      return true;
    } catch (e) {
      debugPrint('Error creating joke: $e');
      return false;
    }
  }

  Future<Map<String, dynamic>?> createJokeWithResponse({
    required String setupText,
    required String punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
  }) async {
    try {
      final callable = _functions.httpsCallable('create_joke');

      final result = await callable.call({
        'joke_data': {
          'setup_text': setupText, 
          'punchline_text': punchlineText,
          'setup_image_url': setupImageUrl,
          'punchline_image_url': punchlineImageUrl,
        },
      });

      debugPrint('Joke created successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      debugPrint('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      debugPrint('Error creating joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }
}
