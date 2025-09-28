import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_providers.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_screen.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

// --- Mocks ---
class MockBookRepository extends Mock implements BookRepository {}

class MockHttpClient extends Mock implements HttpClient {}

class MockHttpClientRequest extends Mock implements HttpClientRequest {}

class MockHttpHeaders extends Mock implements HttpHeaders {}

class FakeUri extends Fake implements Uri {}

class MockHttpClientResponse extends Mock implements HttpClientResponse {
  @override
  final int statusCode = HttpStatus.ok;
  @override
  final int contentLength = transparentImage.length;
  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;
  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int> event)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) {
    return Stream.value(transparentImage).listen(
      onData,
      onError: onError,
      onDone: onDone,
      cancelOnError: cancelOnError,
    );
  }
}

// A fake controller that can be manually controlled in tests.
class TestBookCreatorController extends BookCreatorController {
  @override
  Future<void> build() async {}

  void setTestState(AsyncValue<void> newState) {
    state = newState;
  }

  @override
  Future<bool> createBook() async {
    setTestState(const AsyncLoading());
    setTestState(const AsyncData(null));
    return true;
  }
}

final transparentImage = [
  0x89,
  0x50,
  0x4E,
  0x47,
  0x0D,
  0x0A,
  0x1A,
  0x0A,
  0x00,
  0x00,
  0x00,
  0x0D,
  0x49,
  0x48,
  0x44,
  0x52,
  0x00,
  0x00,
  0x00,
  0x01,
  0x00,
  0x00,
  0x00,
  0x01,
  0x08,
  0x06,
  0x00,
  0x00,
  0x00,
  0x1F,
  0x15,
  0xC4,
  0x89,
  0x00,
  0x00,
  0x00,
  0x0A,
  0x49,
  0x44,
  0x41,
  0x54,
  0x78,
  0x9C,
  0x63,
  0x00,
  0x01,
  0x00,
  0x00,
  0x05,
  0x00,
  0x01,
  0x0D,
  0x0A,
  0x2D,
  0xB4,
  0x00,
  0x00,
  0x00,
  0x00,
  0x49,
  0x45,
  0x4E,
  0x44,
  0xAE,
  0x42,
  0x60,
  0x82,
];

// Helper to pump the widget with a given container.
Future<void> pumpBookCreatorScreen(
  WidgetTester tester,
  ProviderContainer container,
) {
  return tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: BookCreatorScreen()),
    ),
  );
}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeUri());
  });

  final mockJokes = List.generate(
    2,
    (index) => Joke(
      id: 'joke-$index',
      setupText: 'Setup $index',
      punchlineText: 'Punchline $index',
      setupImageUrl: 'https://example.com/image-$index.png',
    ),
  );

  group('BookCreatorScreen', () {
    testWidgets('renders initial UI elements when no jokes are selected', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          bookRepositoryProvider.overrideWithValue(MockBookRepository()),
          bookCreatorControllerProvider.overrideWith(
            () => TestBookCreatorController(),
          ),
        ],
      );
      addTearDown(container.dispose);

      await pumpBookCreatorScreen(tester, container);

      expect(
        find.byKey(const Key('book_creator_screen-title-field')),
        findsOneWidget,
      );
      expect(find.text('No jokes selected.'), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('displays selected jokes in a grid', (tester) async {
      await HttpOverrides.runZoned(
        () async {
          final container = ProviderContainer(
            overrides: [
              bookRepositoryProvider.overrideWithValue(MockBookRepository()),
              bookCreatorControllerProvider.overrideWith(
                () => TestBookCreatorController(),
              ),
            ],
          );
          addTearDown(container.dispose);

          await pumpBookCreatorScreen(tester, container);

          container.read(selectedJokesProvider.notifier).setJokes(mockJokes);
          await tester.pumpAndSettle();

          expect(
            find.byKey(const Key('book_creator_screen-jokes-grid')),
            findsOneWidget,
          );
          expect(find.byType(Card), findsNWidgets(mockJokes.length));
        },
        createHttpClient: (_) {
          final client = MockHttpClient();
          final request = MockHttpClientRequest();
          final response = MockHttpClientResponse();
          when(() => client.getUrl(any())).thenAnswer((_) async => request);
          when(() => request.close()).thenAnswer((_) async => response);
          when(() => request.headers).thenReturn(MockHttpHeaders());
          return client;
        },
      );
    });

    testWidgets('updates book title when text is entered', (tester) async {
      final container = ProviderContainer(
        overrides: [
          bookRepositoryProvider.overrideWithValue(MockBookRepository()),
          bookCreatorControllerProvider.overrideWith(
            () => TestBookCreatorController(),
          ),
        ],
      );
      addTearDown(container.dispose);

      await pumpBookCreatorScreen(tester, container);

      const newTitle = 'My Awesome Book';
      await tester.enterText(
        find.byKey(const Key('book_creator_screen-title-field')),
        newTitle,
      );
      await tester.pumpAndSettle();

      expect(container.read(bookTitleProvider), newTitle);
    });

    testWidgets('shows loading indicator and is disabled when saving', (
      tester,
    ) async {
      final container = ProviderContainer(
        overrides: [
          bookRepositoryProvider.overrideWithValue(MockBookRepository()),
          bookCreatorControllerProvider.overrideWith(
            () => TestBookCreatorController(),
          ),
        ],
      );
      addTearDown(container.dispose);

      final testController =
          container.read(bookCreatorControllerProvider.notifier)
              as TestBookCreatorController;

      container.read(bookTitleProvider.notifier).setTitle('My Book');
      container.read(selectedJokesProvider.notifier).setJokes(mockJokes);
      await pumpBookCreatorScreen(tester, container);

      testController.setTestState(const AsyncLoading());
      await tester.pump();

      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button.onPressed, isNull);
      expect(
        find.descendant(
          of: find.byType(FilledButton),
          matching: find.byType(CircularProgressIndicator),
        ),
        findsOneWidget,
      );

      testController.setTestState(const AsyncData(null));
      await tester.pump();

      final enabledButton = tester.widget<FilledButton>(
        find.byType(FilledButton),
      );
      expect(enabledButton.onPressed, isNotNull);
      expect(
        find.descendant(
          of: find.byType(FilledButton),
          matching: find.byType(CircularProgressIndicator),
        ),
        findsNothing,
      );
      await tester.pumpAndSettle();
    });
  });
}
