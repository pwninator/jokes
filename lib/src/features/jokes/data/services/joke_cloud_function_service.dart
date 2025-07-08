import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter/foundation.dart';

class JokeCloudFunctionService {
  JokeCloudFunctionService({FirebaseFunctions? functions})
    : _functions = functions ?? FirebaseFunctions.instance;

  final FirebaseFunctions _functions;

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

  Future<Map<String, dynamic>?> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async {
    try {
      final callable = _functions.httpsCallable(
        'populate_joke',
        options: HttpsCallableOptions(timeout: const Duration(seconds: 300)),
      );

      final requestData = <String, dynamic>{'joke_id': jokeId};
      if (imagesOnly) {
        requestData['images_only'] = true;
      }
      if (additionalParams != null) {
        requestData.addAll(additionalParams);
      }

      final result = await callable.call(requestData);

      debugPrint('Joke populated successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      debugPrint('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      debugPrint('Error populating joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> updateJoke({
    required String jokeId,
    required String setupText,
    required String punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
  }) async {
    try {
      final callable = _functions.httpsCallable('update_joke');

      final result = await callable.call({
        'joke_id': jokeId,
        'joke_data': {
          'setup_text': setupText,
          'punchline_text': punchlineText,
          'setup_image_url': setupImageUrl,
          'punchline_image_url': punchlineImageUrl,
        },
      });

      debugPrint('Joke updated successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      debugPrint('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      debugPrint('Error updating joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> critiqueJokes({
    required String instructions,
    Map<String, dynamic>? additionalParameters,
  }) async {
    try {
      final callable = _functions.httpsCallable(
        'critique_jokes',
        options: HttpsCallableOptions(timeout: const Duration(seconds: 300)),
      );

      final requestData = {
        'instructions': instructions,
        if (additionalParameters != null) ...additionalParameters,
      };

      final result = await callable.call(requestData);

      debugPrint('Jokes critiqued successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      debugPrint('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      debugPrint('Error critiquing jokes: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }
}
