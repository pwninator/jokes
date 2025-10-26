import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_feed_screen.dart';

void main() {
  test('JokeFeedScreen exposes expected title', () {
    const screen = JokeFeedScreen();
    expect(screen, isA<TitledScreen>());
    expect(screen.title, 'Joke Feed');
  });
}
