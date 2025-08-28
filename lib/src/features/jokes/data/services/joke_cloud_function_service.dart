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

      final requestData = <String, dynamic>{
        'joke_id': jokeId,
        'overwrite': true,
      };
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

  /// Search jokes via Cloud Function and return a list of joke IDs
  ///
  /// Request params: { search_query, max_results }
  /// Response: List of objects: [{ joke_id, vector_distance }, ...]
  Future<List<String>> searchJokes({
    required String searchQuery,
    int? maxResults,
  }) async {
    try {
      final callable = _functions.httpsCallable('search_jokes');
      final payload = <String, dynamic>{'search_query': searchQuery};
      if (maxResults != null) {
        payload['max_results'] = maxResults;
      }

      final result = await callable.call(payload);

      final data = result.data;
      // Accept either: { jokes: [...] } or [...] directly
      final List<dynamic>? resultsList = (data is Map && data['jokes'] is List)
          ? (data['jokes'] as List)
          : (data is List)
          ? data
          : null;

      if (resultsList != null) {
        final ids = <String>[];
        for (final item in resultsList) {
          if (item is Map && item['joke_id'] != null) {
            ids.add(item['joke_id'].toString());
          }
        }
        return ids;
      }

      debugPrint('Unexpected search_jokes response: $data');
      return <String>[];
    } on FirebaseFunctionsException catch (e) {
      debugPrint(
        'Firebase Functions error (search_jokes): ${e.code} - ${e.message}',
      );
      return <String>[];
    } catch (e) {
      debugPrint('Error calling search_jokes: $e');
      return <String>[];
    }
  }
}
