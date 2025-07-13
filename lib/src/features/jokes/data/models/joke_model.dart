import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

@immutable
class Joke {
  final String id;
  final String setupText;
  final String punchlineText;
  final String? setupImageUrl;
  final String? punchlineImageUrl;
  final String? setupImageDescription;
  final String? punchlineImageDescription;
  final List<String> allSetupImageUrls;
  final List<String> allPunchlineImageUrls;
  final Map<String, dynamic>? generationMetadata;
  final int numThumbsUp;
  final int numThumbsDown;
  final JokeAdminRating? adminRating;

  const Joke({
    required this.id,
    required this.setupText,
    required this.punchlineText,
    this.setupImageUrl,
    this.punchlineImageUrl,
    this.setupImageDescription,
    this.punchlineImageDescription,
    this.allSetupImageUrls = const [],
    this.allPunchlineImageUrls = const [],
    this.generationMetadata,
    this.numThumbsUp = 0,
    this.numThumbsDown = 0,
    this.adminRating,
  });

  Joke copyWith({
    String? id,
    String? setupText,
    String? punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
    String? setupImageDescription,
    String? punchlineImageDescription,
    List<String>? allSetupImageUrls,
    List<String>? allPunchlineImageUrls,
    Map<String, dynamic>? generationMetadata,
    int? numThumbsUp,
    int? numThumbsDown,
    JokeAdminRating? adminRating,
  }) {
    return Joke(
      id: id ?? this.id,
      setupText: setupText ?? this.setupText,
      punchlineText: punchlineText ?? this.punchlineText,
      setupImageUrl: setupImageUrl ?? this.setupImageUrl,
      punchlineImageUrl: punchlineImageUrl ?? this.punchlineImageUrl,
      setupImageDescription:
          setupImageDescription ?? this.setupImageDescription,
      punchlineImageDescription:
          punchlineImageDescription ?? this.punchlineImageDescription,
      allSetupImageUrls: allSetupImageUrls ?? this.allSetupImageUrls,
      allPunchlineImageUrls:
          allPunchlineImageUrls ?? this.allPunchlineImageUrls,
      generationMetadata: generationMetadata ?? this.generationMetadata,
      numThumbsUp: numThumbsUp ?? this.numThumbsUp,
      numThumbsDown: numThumbsDown ?? this.numThumbsDown,
      adminRating: adminRating ?? this.adminRating,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'setup_text': setupText,
      'punchline_text': punchlineText,
      'setup_image_url': setupImageUrl,
      'punchline_image_url': punchlineImageUrl,
      'setup_image_description': setupImageDescription,
      'punchline_image_description': punchlineImageDescription,
      'all_setup_image_urls': allSetupImageUrls,
      'all_punchline_image_urls': allPunchlineImageUrls,
      'generation_metadata': generationMetadata,
      'num_thumbs_up': numThumbsUp,
      'num_thumbs_down': numThumbsDown,
      'admin_rating': adminRating?.value,
    };
  }

  factory Joke.fromMap(Map<String, dynamic> map, String documentId) {
    return Joke(
      id: documentId,
      setupText: map['setup_text'] ?? '',
      punchlineText: map['punchline_text'] ?? '',
      setupImageUrl: map['setup_image_url'],
      punchlineImageUrl: map['punchline_image_url'],
      setupImageDescription: map['setup_image_description'],
      punchlineImageDescription: map['punchline_image_description'],
      allSetupImageUrls: List<String>.from(map['all_setup_image_urls'] ?? []),
      allPunchlineImageUrls: List<String>.from(
        map['all_punchline_image_urls'] ?? [],
      ),
      generationMetadata: map['generation_metadata'] as Map<String, dynamic>?,
      numThumbsUp: (map['num_thumbs_up'] as num?)?.toInt() ?? 0,
      numThumbsDown: (map['num_thumbs_down'] as num?)?.toInt() ?? 0,
      adminRating: JokeAdminRating.fromString(map['admin_rating'] as String?),
    );
  }

  // Optional: Consider using toJson/fromJson if you prefer, especially for consistency
  // if other models use it, or if you have nested objects (though not the case here).
  // String toJson() => json.encode(toMap());
  // factory Joke.fromJson(String source) => Joke.fromMap(json.decode(source));

  @override
  String toString() =>
      'Joke(id: $id, setupText: $setupText, punchlineText: $punchlineText, setupImageUrl: $setupImageUrl, punchlineImageUrl: $punchlineImageUrl, setupImageDescription: $setupImageDescription, punchlineImageDescription: $punchlineImageDescription, allSetupImageUrls: $allSetupImageUrls, allPunchlineImageUrls: $allPunchlineImageUrls, generationMetadata: $generationMetadata, numThumbsUp: $numThumbsUp, numThumbsDown: $numThumbsDown, adminRating: $adminRating)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Joke &&
        other.id == id &&
        other.setupText == setupText &&
        other.punchlineText == punchlineText &&
        other.setupImageUrl == setupImageUrl &&
        other.punchlineImageUrl == punchlineImageUrl &&
        other.setupImageDescription == setupImageDescription &&
        other.punchlineImageDescription == punchlineImageDescription &&
        listEquals(other.allSetupImageUrls, allSetupImageUrls) &&
        listEquals(other.allPunchlineImageUrls, allPunchlineImageUrls) &&
        mapEquals(other.generationMetadata, generationMetadata) &&
        other.numThumbsUp == numThumbsUp &&
        other.numThumbsDown == numThumbsDown &&
        other.adminRating == adminRating;
  }

  @override
  int get hashCode =>
      id.hashCode ^
      setupText.hashCode ^
      punchlineText.hashCode ^
      setupImageUrl.hashCode ^
      punchlineImageUrl.hashCode ^
      setupImageDescription.hashCode ^
      punchlineImageDescription.hashCode ^
      allSetupImageUrls.hashCode ^
      allPunchlineImageUrls.hashCode ^
      generationMetadata.hashCode ^
      numThumbsUp.hashCode ^
      numThumbsDown.hashCode ^
      adminRating.hashCode;
}
