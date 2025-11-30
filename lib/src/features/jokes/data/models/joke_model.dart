import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

@immutable
class Joke {
  final String id;
  final String setupText;
  final String punchlineText;
  final String? setupImageUrl;
  final String? punchlineImageUrl;
  final String? setupImageUrlUpscaled;
  final String? punchlineImageUrlUpscaled;
  final String? setupImageDescription;
  final String? punchlineImageDescription;
  final String? setupSceneIdea;
  final String? punchlineSceneIdea;
  final List<String> allSetupImageUrls;
  final List<String> allPunchlineImageUrls;
  final Map<String, dynamic>? generationMetadata;
  final int numViews;
  final int numSaves;
  final int numShares;
  final double numSavedUsersFraction;
  final double popularityScore;
  final JokeAdminRating? adminRating;
  final JokeState? state;
  final DateTime? publicTimestamp;
  final List<String> tags;
  final String? seasonal;

  const Joke({
    required this.id,
    required this.setupText,
    required this.punchlineText,
    this.setupImageUrl,
    this.punchlineImageUrl,
    this.setupImageUrlUpscaled,
    this.punchlineImageUrlUpscaled,
    this.setupImageDescription,
    this.punchlineImageDescription,
    this.setupSceneIdea,
    this.punchlineSceneIdea,
    this.allSetupImageUrls = const [],
    this.allPunchlineImageUrls = const [],
    this.generationMetadata,
    this.numSaves = 0,
    this.numShares = 0,
    this.numViews = 0,
    this.numSavedUsersFraction = 0.0,
    this.popularityScore = 0.0,
    this.adminRating,
    this.state,
    this.publicTimestamp,
    this.tags = const [],
    this.seasonal,
  });

  Joke copyWith({
    String? id,
    String? setupText,
    String? punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
    String? setupImageUrlUpscaled,
    String? punchlineImageUrlUpscaled,
    String? setupImageDescription,
    String? punchlineImageDescription,
    String? setupSceneIdea,
    String? punchlineSceneIdea,
    List<String>? allSetupImageUrls,
    List<String>? allPunchlineImageUrls,
    Map<String, dynamic>? generationMetadata,
    int? numViews,
    int? numSaves,
    int? numShares,
    double? numSavedUsersFraction,
    double? popularityScore,
    JokeAdminRating? adminRating,
    JokeState? state,
    DateTime? publicTimestamp,
    List<String>? tags,
    String? seasonal,
  }) {
    return Joke(
      id: id ?? this.id,
      setupText: setupText ?? this.setupText,
      punchlineText: punchlineText ?? this.punchlineText,
      setupImageUrl: setupImageUrl ?? this.setupImageUrl,
      punchlineImageUrl: punchlineImageUrl ?? this.punchlineImageUrl,
      setupImageUrlUpscaled:
          setupImageUrlUpscaled ?? this.setupImageUrlUpscaled,
      punchlineImageUrlUpscaled:
          punchlineImageUrlUpscaled ?? this.punchlineImageUrlUpscaled,
      setupImageDescription:
          setupImageDescription ?? this.setupImageDescription,
      punchlineImageDescription:
          punchlineImageDescription ?? this.punchlineImageDescription,
      setupSceneIdea: setupSceneIdea ?? this.setupSceneIdea,
      punchlineSceneIdea: punchlineSceneIdea ?? this.punchlineSceneIdea,
      allSetupImageUrls: allSetupImageUrls ?? this.allSetupImageUrls,
      allPunchlineImageUrls:
          allPunchlineImageUrls ?? this.allPunchlineImageUrls,
      generationMetadata: generationMetadata ?? this.generationMetadata,
      numViews: numViews ?? this.numViews,
      numSaves: numSaves ?? this.numSaves,
      numShares: numShares ?? this.numShares,
      numSavedUsersFraction:
          numSavedUsersFraction ?? this.numSavedUsersFraction,
      popularityScore: popularityScore ?? this.popularityScore,
      adminRating: adminRating ?? this.adminRating,
      state: state ?? this.state,
      publicTimestamp: publicTimestamp ?? this.publicTimestamp,
      tags: tags ?? this.tags,
      seasonal: seasonal ?? this.seasonal,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'setup_text': setupText,
      'punchline_text': punchlineText,
      'setup_image_url': setupImageUrl,
      'punchline_image_url': punchlineImageUrl,
      'setup_image_url_upscaled': setupImageUrlUpscaled,
      'punchline_image_url_upscaled': punchlineImageUrlUpscaled,
      'setup_image_description': setupImageDescription,
      'punchline_image_description': punchlineImageDescription,
      'setup_scene_idea': setupSceneIdea,
      'punchline_scene_idea': punchlineSceneIdea,
      'all_setup_image_urls': allSetupImageUrls,
      'all_punchline_image_urls': allPunchlineImageUrls,
      'generation_metadata': generationMetadata,
      'num_viewed_users': numViews,
      'num_saved_users': numSaves,
      'num_shared_users': numShares,
      'num_saved_users_fraction': numSavedUsersFraction,
      'popularity_score': popularityScore,
      'admin_rating': adminRating?.value,
      'state': state?.value,
      'public_timestamp': publicTimestamp != null
          ? Timestamp.fromDate(publicTimestamp!)
          : null,
      'tags': tags,
      'seasonal': seasonal,
    };
  }

  factory Joke.fromMap(Map<String, dynamic> map, String documentId) {
    return Joke(
      id: documentId,
      setupText: map['setup_text'] ?? '',
      punchlineText: map['punchline_text'] ?? '',
      setupImageUrl: map['setup_image_url'],
      punchlineImageUrl: map['punchline_image_url'],
      setupImageUrlUpscaled: map['setup_image_url_upscaled'],
      punchlineImageUrlUpscaled: map['punchline_image_url_upscaled'],
      setupImageDescription: map['setup_image_description'],
      punchlineImageDescription: map['punchline_image_description'],
      setupSceneIdea: map['setup_scene_idea'],
      punchlineSceneIdea: map['punchline_scene_idea'],
      allSetupImageUrls: List<String>.from(map['all_setup_image_urls'] ?? []),
      allPunchlineImageUrls: List<String>.from(
        map['all_punchline_image_urls'] ?? [],
      ),
      generationMetadata: map['generation_metadata'] as Map<String, dynamic>?,
      numViews: (map['num_viewed_users'] as num?)?.toInt() ?? 0,
      numSaves: (map['num_saved_users'] as num?)?.toInt() ?? 0,
      numShares: (map['num_shared_users'] as num?)?.toInt() ?? 0,
      numSavedUsersFraction:
          (map['num_saved_users_fraction'] as num?)?.toDouble() ?? 0.0,
      popularityScore: (map['popularity_score'] as num?)?.toDouble() ?? 0.0,
      adminRating: JokeAdminRating.fromString(map['admin_rating'] as String?),
      state: JokeState.fromString(map['state'] as String?),
      publicTimestamp: _parsePublicTimestamp(map['public_timestamp']),
      tags: List<String>.from(map['tags'] ?? []),
      seasonal: map['seasonal'] as String?,
    );
  }

  static DateTime? _parsePublicTimestamp(dynamic value) {
    if (value == null) return null;
    try {
      if (value is Timestamp) {
        return value.toDate().toUtc();
      }
      if (value is String) {
        return DateTime.tryParse(value)?.toUtc();
      }
      if (value is int) {
        if (value > 1000000000000) {
          return DateTime.fromMillisecondsSinceEpoch(value, isUtc: true);
        }
        return DateTime.fromMillisecondsSinceEpoch(value * 1000, isUtc: true);
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  @override
  String toString() =>
      'Joke(id: $id, setupText: $setupText, punchlineText: $punchlineText, setupImageUrl: $setupImageUrl, punchlineImageUrl: $punchlineImageUrl, setupImageUrlUpscaled: $setupImageUrlUpscaled, punchlineImageUrlUpscaled: $punchlineImageUrlUpscaled, setupImageDescription: $setupImageDescription, punchlineImageDescription: $punchlineImageDescription, setupSceneIdea: $setupSceneIdea, punchlineSceneIdea: $punchlineSceneIdea, allSetupImageUrls: $allSetupImageUrls, allPunchlineImageUrls: $allPunchlineImageUrls, generationMetadata: $generationMetadata, numSaves: $numSaves, numShares: $numShares, numViews: $numViews, numSavedUsersFraction: $numSavedUsersFraction, popularityScore: $popularityScore, adminRating: $adminRating, state: $state, publicTimestamp: $publicTimestamp, tags: $tags, seasonal: $seasonal)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Joke &&
        other.id == id &&
        other.setupText == setupText &&
        other.punchlineText == punchlineText &&
        other.setupImageUrl == setupImageUrl &&
        other.punchlineImageUrl == punchlineImageUrl &&
        other.setupImageUrlUpscaled == setupImageUrlUpscaled &&
        other.punchlineImageUrlUpscaled == punchlineImageUrlUpscaled &&
        other.setupImageDescription == setupImageDescription &&
        other.punchlineImageDescription == punchlineImageDescription &&
        other.setupSceneIdea == setupSceneIdea &&
        other.punchlineSceneIdea == punchlineSceneIdea &&
        listEquals(other.allSetupImageUrls, allSetupImageUrls) &&
        listEquals(other.allPunchlineImageUrls, allPunchlineImageUrls) &&
        mapEquals(other.generationMetadata, generationMetadata) &&
        other.numViews == numViews &&
        other.numSaves == numSaves &&
        other.numShares == numShares &&
        other.numSavedUsersFraction == numSavedUsersFraction &&
        other.popularityScore == popularityScore &&
        other.adminRating == adminRating &&
        other.state == state &&
        other.publicTimestamp == publicTimestamp &&
        listEquals(other.tags, tags) &&
        other.seasonal == seasonal;
  }

  @override
  int get hashCode =>
      id.hashCode ^
      setupText.hashCode ^
      punchlineText.hashCode ^
      setupImageUrl.hashCode ^
      punchlineImageUrl.hashCode ^
      setupImageUrlUpscaled.hashCode ^
      punchlineImageUrlUpscaled.hashCode ^
      setupImageDescription.hashCode ^
      punchlineImageDescription.hashCode ^
      setupSceneIdea.hashCode ^
      punchlineSceneIdea.hashCode ^
      allSetupImageUrls.hashCode ^
      allPunchlineImageUrls.hashCode ^
      generationMetadata.hashCode ^
      numViews.hashCode ^
      numSaves.hashCode ^
      numShares.hashCode ^
      numSavedUsersFraction.hashCode ^
      popularityScore.hashCode ^
      adminRating.hashCode ^
      state.hashCode ^
      publicTimestamp.hashCode ^
      tags.hashCode ^
      seasonal.hashCode;
}
