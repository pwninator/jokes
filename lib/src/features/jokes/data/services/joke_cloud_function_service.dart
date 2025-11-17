import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

part 'joke_cloud_function_service.g.dart';

/// How strictly to match the search query
enum MatchMode { tight, loose }

@Riverpod(keepAlive: true)
JokeCloudFunctionService jokeCloudFunctionService(Ref ref) {
  final functions = ref.watch(firebaseFunctionsProvider);
  final perf = ref.watch(performanceServiceProvider);
  return JokeCloudFunctionService(functions: functions, perf: perf);
}

class JokeCloudFunctionService {
  JokeCloudFunctionService({
    required FirebaseFunctions functions,
    required PerformanceService perf,
  }) : _functions = functions,
       _perf = perf;

  final FirebaseFunctions _functions;
  FirebaseFunctions get _fns => _functions;
  final PerformanceService _perf;

  Future<T> _traceCf<T>({
    required String functionName,
    required Future<T> Function() action,
    Map<String, String>? attributes,
  }) async {
    final key = functionName;
    _perf.startNamedTrace(
      name: TraceName.cfCall,
      key: key,
      attributes: {
        'function': functionName,
        if (attributes != null) ...attributes,
      },
    );
    try {
      AppLogger.debug('CLOUD_FUNCTIONS traceCf: Calling $functionName');
      return await action();
    } finally {
      _perf.stopNamedTrace(name: TraceName.cfCall, key: key);
    }
  }

  /// Track app usage in Cloud Functions (HTTP on_request endpoint).
  ///
  /// All fields are required and always sent to the backend.
  Future<void> trackUsage({
    required int numDaysUsed,
    required int numSaved,
    required int numViewed,
    required int numNavigated,
    required int numShared,
    required bool requestedReview,
    required String feedCursor,
    required int localFeedCount,
  }) async {
    try {
      await _traceCf(
        functionName: 'usage',
        action: () async {
          final callable = _fns.httpsCallable('usage');
          final payload = <String, dynamic>{
            'num_days_used': numDaysUsed.toString(),
            'num_saved': numSaved.toString(),
            'num_viewed': numViewed.toString(),
            'num_navigated': numNavigated.toString(),
            'num_shared': numShared.toString(),
            'requested_review': requestedReview,
            'feed_cursor': feedCursor,
            'local_feed_count': localFeedCount.toString(),
          };
          await callable.call(payload);
          return null;
        },
      );
    } catch (e) {
      AppLogger.warn('CLOUD FUNCTIONS trackUsage exception: $e');
    }
  }

  Future<Map<String, dynamic>?> createJokeWithResponse({
    required String setupText,
    required String punchlineText,
    required bool adminOwned,
    String? setupImageUrl,
    String? punchlineImageUrl,
  }) async {
    try {
      final result = await _traceCf(
        functionName: 'create_joke',
        action: () async {
          final callable = _fns.httpsCallable('create_joke');
          return await callable.call({
            'admin_owned': adminOwned,
            'joke_data': {
              'setup_text': setupText,
              'punchline_text': punchlineText,
              'setup_image_url': setupImageUrl,
              'punchline_image_url': punchlineImageUrl,
            },
          });
        },
      );

      AppLogger.debug('Joke created successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error creating joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async {
    try {
      final result = await _traceCf(
        functionName: 'populate_joke',
        attributes: {'images_only': imagesOnly.toString()},
        action: () async {
          final callable = _fns.httpsCallable(
            'populate_joke',
            options: HttpsCallableOptions(
              timeout: const Duration(seconds: 300),
            ),
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

          return await callable.call(requestData);
        },
      );

      AppLogger.debug('Joke populated successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error populating joke: $e');
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
      final result = await _traceCf(
        functionName: 'update_joke',
        action: () async {
          final callable = _fns.httpsCallable('update_joke');
          return await callable.call({
            'joke_id': jokeId,
            'joke_data': {
              'setup_text': setupText,
              'punchline_text': punchlineText,
              'setup_image_url': setupImageUrl,
              'punchline_image_url': punchlineImageUrl,
            },
          });
        },
      );

      AppLogger.debug('Joke updated successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error updating joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> critiqueJokes({
    required String instructions,
    Map<String, dynamic>? additionalParameters,
  }) async {
    try {
      final result = await _traceCf(
        functionName: 'critique_jokes',
        action: () async {
          final callable = _fns.httpsCallable(
            'critique_jokes',
            options: HttpsCallableOptions(
              timeout: const Duration(seconds: 300),
            ),
          );

          final requestData = {
            'instructions': instructions,
            if (additionalParameters != null) ...additionalParameters,
          };

          return await callable.call(requestData);
        },
      );

      AppLogger.debug('Jokes critiqued successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error critiquing jokes: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> modifyJoke({
    required String jokeId,
    String? setupInstructions,
    String? punchlineInstructions,
  }) async {
    try {
      final result = await _traceCf(
        functionName: 'modify_joke_image',
        action: () async {
          final callable = _fns.httpsCallable(
            'modify_joke_image',
            options: HttpsCallableOptions(
              timeout: const Duration(seconds: 300),
            ),
          );

          final requestData = <String, dynamic>{'joke_id': jokeId};

          if (setupInstructions != null && setupInstructions.isNotEmpty) {
            requestData['setup_instruction'] = setupInstructions;
          }

          if (punchlineInstructions != null &&
              punchlineInstructions.isNotEmpty) {
            requestData['punchline_instruction'] = punchlineInstructions;
          }

          return await callable.call(requestData);
        },
      );

      AppLogger.debug('Joke modified successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Firebase Functions error: ${e.code} - ${e.message}');
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error modifying joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  /// Search jokes via Cloud Function and return typed results
  ///
  /// Request params: { search_query, max_results, label }
  /// Response: List of objects: [{ joke_id, vector_distance }, ...]
  Future<List<JokeSearchResult>> searchJokes({
    required String searchQuery,
    required int maxResults,
    required bool publicOnly,
    required MatchMode matchMode,
    required SearchScope scope,
    List<String> excludeJokeIds = const <String>[],
    required SearchLabel label,
  }) async {
    try {
      // Build label: if SearchLabel is none, use scope.name; otherwise use "scope.name:label.name"
      final String labelValue = label == SearchLabel.none
          ? scope.name
          : '${scope.name}:${label.name}';

      final payload = <String, dynamic>{
        'search_query': searchQuery,
        // Workaround: send as string to avoid protobuf Int64 wrapper on the server
        'max_results': maxResults.toString(),
        'public_only': publicOnly,
        'match_mode': matchMode == MatchMode.tight ? 'TIGHT' : 'LOOSE',
        'label': labelValue,
        if (excludeJokeIds.isNotEmpty) 'exclude_joke_ids': excludeJokeIds,
      };

      final result = await _traceCf(
        functionName: 'search_jokes',
        attributes: {
          'scope': scope.name,
          'label': labelValue,
          'match_mode': matchMode == MatchMode.tight ? 'TIGHT' : 'LOOSE',
          'query_len': searchQuery.length.toString(),
          'exclude_count': excludeJokeIds.length.toString(),
        },
        action: () async {
          final callable = _fns.httpsCallable('search_jokes');
          return await callable.call(payload);
        },
      );

      final data = result.data;
      // Accept either: { jokes: [...] } or [...] directly
      final List<dynamic>? resultsList = (data is Map && data['jokes'] is List)
          ? (data['jokes'] as List)
          : (data is List)
          ? data
          : null;

      if (resultsList != null) {
        var parsed = resultsList
            .whereType<Map>()
            .map((e) => JokeSearchResult.fromMap(e))
            .where((r) => r.id.isNotEmpty)
            .toList();
        if (excludeJokeIds.isNotEmpty) {
          final exclude = excludeJokeIds.toSet();
          parsed = parsed.where((r) => !exclude.contains(r.id)).toList();
        }

        return parsed;
      }

      AppLogger.warn('Unexpected search_jokes response: $data');
      return <JokeSearchResult>[];
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn(
        'Firebase Functions error (search_jokes): ${e.code} - ${e.message}',
      );
      return <JokeSearchResult>[];
    } catch (e) {
      AppLogger.warn('Error calling search_jokes: $e');
      return <JokeSearchResult>[];
    }
  }

  Future<Map<String, dynamic>?> upscaleJoke(String jokeId) async {
    try {
      final result = await _traceCf(
        functionName: 'upscale_joke',
        action: () async {
          final callable = _fns.httpsCallable(
            'upscale_joke',
            options: HttpsCallableOptions(
              timeout: const Duration(seconds: 600),
            ),
          );
          return await callable.call({'joke_id': jokeId});
        },
      );

      AppLogger.debug('Joke upscaled successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn(
        'Firebase Functions error (upscale_joke): ${e.code} - ${e.message}',
      );
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error upscaling joke: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }

  Future<Map<String, dynamic>?> createBook({
    required String title,
    required List<String> jokeIds,
  }) async {
    try {
      final result = await _traceCf(
        functionName: 'create_joke_book',
        action: () async {
          final callable = _fns.httpsCallable('create_joke_book');
          final payload = <String, dynamic>{'book_name': title};
          if (jokeIds.isNotEmpty) {
            payload['joke_ids'] = jokeIds;
          }
          return await callable.call(payload);
        },
      );

      AppLogger.debug('Book created successfully: ${result.data}');
      return {'success': true, 'data': result.data};
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn(
        'Firebase Functions error (create_joke_book): ${e.code} - ${e.message}',
      );
      return {
        'success': false,
        'error': 'Function error: ${e.message}',
        'code': e.code,
      };
    } catch (e) {
      AppLogger.warn('Error creating book: $e');
      return {'success': false, 'error': 'Unexpected error: $e'};
    }
  }
}
