/// Joke lifecycle/state values stored in Firestore as uppercase strings
enum JokeState {
  unknown('UNKNOWN'),
  draft('DRAFT'),
  unreviewed('UNREVIEWED'),
  approved('APPROVED'),
  rejected('REJECTED'),
  daily('DAILY'),
  published('PUBLISHED');

  const JokeState(this.value);

  final String value;

  static JokeState? fromString(String? value) {
    if (value == null) return null;
    for (final s in JokeState.values) {
      if (s.value == value) return s;
    }
    return null;
  }

  /// Whether admin rating is mutable in this state
  bool get canMutateAdminRating =>
      this == JokeState.approved ||
      this == JokeState.rejected ||
      this == JokeState.unreviewed;
}
