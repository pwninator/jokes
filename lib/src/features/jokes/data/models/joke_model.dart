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
  final String? setupImageDescription;
  final String? punchlineImageDescription;
  final List<String> allSetupImageUrls;
  final List<String> allPunchlineImageUrls;
  final Map<String, dynamic>? generationMetadata;
  final int numThumbsUp;
  final int numThumbsDown;
  final int numSaves;
  final int numShares;
  final int popularityScore;
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
    this.setupImageDescription,
    this.punchlineImageDescription,
    this.allSetupImageUrls = const [],
    this.allPunchlineImageUrls = const [],
    this.generationMetadata,
    this.numThumbsUp = 0,
    this.numThumbsDown = 0,
    this.numSaves = 0,
    this.numShares = 0,
    this.popularityScore = 0,
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
    String? setupImageDescription,
    String? punchlineImageDescription,
    List<String>? allSetupImageUrls,
    List<String>? allPunchlineImageUrls,
    Map<String, dynamic>? generationMetadata,
    int? numThumbsUp,
    int? numThumbsDown,
    int? numSaves,
    int? numShares,
    int? popularityScore,
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
      numSaves: numSaves ?? this.numSaves,
      numShares: numShares ?? this.numShares,
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
      'setup_image_description': setupImageDescription,
      'punchline_image_description': punchlineImageDescription,
      'all_setup_image_urls': allSetupImageUrls,
      'all_punchline_image_urls': allPunchlineImageUrls,
      'generation_metadata': generationMetadata,
      'num_thumbs_up': numThumbsUp,
      'num_thumbs_down': numThumbsDown,
      'num_saves': numSaves,
      'num_shares': numShares,
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
      setupImageDescription: map['setup_image_description'],
      punchlineImageDescription: map['punchline_image_description'],
      allSetupImageUrls: List<String>.from(map['all_setup_image_urls'] ?? []),
      allPunchlineImageUrls: List<String>.from(
        map['all_punchline_image_urls'] ?? [],
      ),
      generationMetadata: map['generation_metadata'] as Map<String, dynamic>?,
      numThumbsUp: (map['num_thumbs_up'] as num?)?.toInt() ?? 0,
      numThumbsDown: (map['num_thumbs_down'] as num?)?.toInt() ?? 0,
      numSaves: (map['num_saves'] as num?)?.toInt() ?? 0,
      numShares: (map['num_shares'] as num?)?.toInt() ?? 0,
      popularityScore: (map['popularity_score'] as num?)?.toInt() ?? 0,
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
      'Joke(id: $id, setupText: $setupText, punchlineText: $punchlineText, setupImageUrl: $setupImageUrl, punchlineImageUrl: $punchlineImageUrl, setupImageDescription: $setupImageDescription, punchlineImageDescription: $punchlineImageDescription, allSetupImageUrls: $allSetupImageUrls, allPunchlineImageUrls: $allPunchlineImageUrls, generationMetadata: $generationMetadata, numThumbsUp: $numThumbsUp, numThumbsDown: $numThumbsDown, numSaves: $numSaves, numShares: $numShares, popularityScore: $popularityScore, adminRating: $adminRating, state: $state, publicTimestamp: $publicTimestamp, tags: $tags, seasonal: $seasonal)';

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
        other.numSaves == numSaves &&
        other.numShares == numShares &&
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
      setupImageDescription.hashCode ^
      punchlineImageDescription.hashCode ^
      allSetupImageUrls.hashCode ^
      allPunchlineImageUrls.hashCode ^
      generationMetadata.hashCode ^
      numThumbsUp.hashCode ^
      numThumbsDown.hashCode ^
      numSaves.hashCode ^
      numShares.hashCode ^
      popularityScore.hashCode ^
      adminRating.hashCode ^
      state.hashCode ^
      publicTimestamp.hashCode ^
      tags.hashCode ^
      seasonal.hashCode;
}
