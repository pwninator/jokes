import 'package:flutter/foundation.dart';

@immutable
class Book {
  final String title;
  final List<String> jokeIds;

  const Book({required this.title, required this.jokeIds});

  Book copyWith({String? title, List<String>? jokeIds}) {
    return Book(title: title ?? this.title, jokeIds: jokeIds ?? this.jokeIds);
  }

  Map<String, dynamic> toMap() {
    return {'title': title, 'joke_ids': jokeIds};
  }

  @override
  String toString() => 'Book(title: $title, jokeIds: $jokeIds)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Book &&
        other.title == title &&
        listEquals(other.jokeIds, jokeIds);
  }

  @override
  int get hashCode => title.hashCode ^ jokeIds.hashCode;
}
