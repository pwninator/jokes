import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

@immutable
class JokeScheduleBatch {
  final String id; // format: scheduleId_YYYY_MM
  final String scheduleId;
  final int year;
  final int month;
  final Map<String, Joke> jokes; // day (01-31) -> joke

  const JokeScheduleBatch({
    required this.id,
    required this.scheduleId,
    required this.year,
    required this.month,
    required this.jokes,
  });

  /// Creates a batch ID from schedule ID, year, and month
  static String createBatchId(String scheduleId, int year, int month) {
    final monthStr = month.toString().padLeft(2, '0');
    return '${scheduleId}_${year}_$monthStr';
  }

  /// Parses a batch ID to extract schedule ID, year, and month
  static Map<String, dynamic>? parseBatchId(String batchId) {
    final parts = batchId.split('_');
    if (parts.length < 3) return null;

    try {
      final year = int.parse(parts[parts.length - 2]);
      final month = int.parse(parts[parts.length - 1]);
      final scheduleId = parts.sublist(0, parts.length - 2).join('_');
      return {
        'scheduleId': scheduleId,
        'year': year,
        'month': month,
      };
    } catch (e) {
      return null;
    }
  }

  JokeScheduleBatch copyWith({
    String? id,
    String? scheduleId,
    int? year,
    int? month,
    Map<String, Joke>? jokes,
  }) {
    return JokeScheduleBatch(
      id: id ?? this.id,
      scheduleId: scheduleId ?? this.scheduleId,
      year: year ?? this.year,
      month: month ?? this.month,
      jokes: jokes ?? this.jokes,
    );
  }

  Map<String, dynamic> toMap() {
    // Convert jokes map to Firestore format
    final jokesMap = <String, dynamic>{};
    jokes.forEach((day, joke) {
      jokesMap[day] = {
        'joke_id': joke.id,
        'setup': joke.setupText,
        'punchline': joke.punchlineText,
        'setup_image_url': joke.setupImageUrl,
        'punchline_image_url': joke.punchlineImageUrl,
      };
    });

    return {
      'jokes': jokesMap,
    };
  }

  factory JokeScheduleBatch.fromMap(Map<String, dynamic> map, String documentId) {
    final parsedId = parseBatchId(documentId);
    if (parsedId == null) {
      throw ArgumentError('Invalid batch ID format: $documentId');
    }

    // Convert Firestore jokes map to Joke objects
    final jokes = <String, Joke>{};
    final jokesMap = map['jokes'] as Map<String, dynamic>? ?? {};
    
    jokesMap.forEach((day, jokeData) {
      if (jokeData is Map<String, dynamic>) {
        jokes[day] = Joke(
          id: jokeData['joke_id'] ?? '',
          setupText: jokeData['setup'] ?? '',
          punchlineText: jokeData['punchline'] ?? '',
          setupImageUrl: jokeData['setup_image_url'],
          punchlineImageUrl: jokeData['punchline_image_url'],
        );
      }
    });

    return JokeScheduleBatch(
      id: documentId,
      scheduleId: parsedId['scheduleId'],
      year: parsedId['year'],
      month: parsedId['month'],
      jokes: jokes,
    );
  }

  @override
  String toString() => 'JokeScheduleBatch(id: $id, scheduleId: $scheduleId, year: $year, month: $month, jokes: ${jokes.length})';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is JokeScheduleBatch &&
        other.id == id &&
        other.scheduleId == scheduleId &&
        other.year == year &&
        other.month == month &&
        mapEquals(other.jokes, jokes);
  }

  @override
  int get hashCode => id.hashCode ^ scheduleId.hashCode ^ year.hashCode ^ month.hashCode ^ jokes.hashCode;
} 