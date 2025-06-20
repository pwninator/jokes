import 'package:flutter/foundation.dart';

@immutable
class Joke {
  final String id;
  final String setupText;
  final String punchlineText;
  final String? imageUrl;

  const Joke({
    required this.id,
    required this.setupText,
    required this.punchlineText,
    this.imageUrl,
  });

  Joke copyWith({
    String? id,
    String? setupText,
    String? punchlineText,
    String? imageUrl,
  }) {
    return Joke(
      id: id ?? this.id,
      setupText: setupText ?? this.setupText,
      punchlineText: punchlineText ?? this.punchlineText,
      imageUrl: imageUrl ?? this.imageUrl,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'setup_text': setupText,
      'punchline_text': punchlineText,
      'image_url': imageUrl,
    };
  }

  factory Joke.fromMap(Map<String, dynamic> map, String documentId) {
    return Joke(
      id: documentId,
      setupText: map['setup_text'] ?? '',
      punchlineText: map['punchline_text'] ?? '',
      imageUrl: map['image_url'],
    );
  }

  // Optional: Consider using toJson/fromJson if you prefer, especially for consistency
  // if other models use it, or if you have nested objects (though not the case here).
  // String toJson() => json.encode(toMap());
  // factory Joke.fromJson(String source) => Joke.fromMap(json.decode(source));

  @override
  String toString() =>
      'Joke(id: $id, setupText: $setupText, punchlineText: $punchlineText, imageUrl: $imageUrl)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Joke &&
        other.id == id &&
        other.setupText == setupText &&
        other.punchlineText == punchlineText &&
        other.imageUrl == imageUrl;
  }

  @override
  int get hashCode =>
      id.hashCode ^ setupText.hashCode ^ punchlineText.hashCode ^ imageUrl.hashCode;
}
