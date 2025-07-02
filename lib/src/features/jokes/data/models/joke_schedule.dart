import 'package:flutter/foundation.dart';

@immutable
class JokeSchedule {
  final String id;
  final String name;

  const JokeSchedule({
    required this.id,
    required this.name,
  });

  /// Sanitizes a name to create a valid Firestore document ID
  /// 1. Replace all non-alphanumeric chars with underscores
  /// 2. Remove leading/trailing underscores
  /// 3. Dedupe consecutive underscores to single underscore
  /// 4. Convert to lowercase
  static String sanitizeId(String name) {
    return name
        .replaceAll(RegExp(r'[^a-zA-Z0-9]'), '_')
        .replaceAll(RegExp(r'_+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '')
        .toLowerCase();
  }

  JokeSchedule copyWith({
    String? id,
    String? name,
  }) {
    return JokeSchedule(
      id: id ?? this.id,
      name: name ?? this.name,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'name': name,
    };
  }

  factory JokeSchedule.fromMap(Map<String, dynamic> map, String documentId) {
    return JokeSchedule(
      id: documentId,
      name: map['name'] ?? '',
    );
  }

  @override
  String toString() => 'JokeSchedule(id: $id, name: $name)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is JokeSchedule && other.id == id && other.name == name;
  }

  @override
  int get hashCode => id.hashCode ^ name.hashCode;
} 