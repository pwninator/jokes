enum JokeThumbsReaction {
  none,
  up,
  down;

  static JokeThumbsReaction fromString(String? value) {
    switch (value) {
      case 'up':
        return JokeThumbsReaction.up;
      case 'down':
        return JokeThumbsReaction.down;
      case 'none':
      case null:
        return JokeThumbsReaction.none;
      default:
        return JokeThumbsReaction.none;
    }
  }

  String get storageValue {
    switch (this) {
      case JokeThumbsReaction.none:
        return 'none';
      case JokeThumbsReaction.up:
        return 'up';
      case JokeThumbsReaction.down:
        return 'down';
    }
  }
}
