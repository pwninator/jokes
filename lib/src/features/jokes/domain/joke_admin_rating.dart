/// Admin rating values for jokes
enum JokeAdminRating {
  unreviewed('UNREVIEWED'),
  approved('APPROVED'),
  rejected('REJECTED');

  const JokeAdminRating(this.value);

  /// The string value stored in Firestore
  final String value;

  /// Parse a string value to JokeAdminRating
  static JokeAdminRating? fromString(String? value) {
    if (value == null) return null;

    for (final rating in JokeAdminRating.values) {
      if (rating.value == value) {
        return rating;
      }
    }
    return null;
  }

  /// Convert to thumbs up/down representation
  bool get isThumbsUp => this == JokeAdminRating.approved;
  bool get isThumbsDown => this == JokeAdminRating.rejected;
}
