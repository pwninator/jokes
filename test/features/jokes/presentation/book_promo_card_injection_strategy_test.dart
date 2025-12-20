import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_injection_strategies.dart';

class MockAppUsageService extends Mock implements AppUsageService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

final _refProvider = Provider<Ref>((ref) => ref);

void main() {
  late MockAppUsageService mockAppUsageService;
  late MockRemoteConfigValues mockRemoteValues;
  late ProviderContainer container;
  late Ref ref;
  final fixedNow = DateTime(2025, 1, 10);

  setUp(() {
    mockAppUsageService = MockAppUsageService();
    mockRemoteValues = MockRemoteConfigValues();
    container = ProviderContainer(
      overrides: [
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        remoteConfigValuesProvider.overrideWithValue(mockRemoteValues),
        clockProvider.overrideWithValue(() => fixedNow),
      ],
    );
    ref = container.read(_refProvider);
  });

  tearDown(() {
    container.dispose();
  });

  test('inserts promo card when thresholds are met', () async {
    _arrangeRemoteConfigDefaults(mockRemoteValues);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 42);
    when(
      () => mockAppUsageService.getBookPromoCardLastShown(),
    ).thenAnswer((_) async => null);

    final strategy = const BookPromoCardInjectionStrategy(
      jokeContext: 'joke_feed',
    );
    final existingEntries = _buildJokeEntries(count: 4);
    final newEntries = _buildJokeEntries(count: 2, startIndex: 4);

    final result = await strategy.apply(
      ref: ref,
      existingEntries: existingEntries,
      newEntries: newEntries,
      hasMore: true,
    );

    expect(result.length, newEntries.length + 1);
    expect(result[1], isA<BookPromoSlotEntry>());
  });

  test('does not insert when user has viewed too few jokes', () async {
    _arrangeRemoteConfigDefaults(mockRemoteValues);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 3);
    when(
      () => mockAppUsageService.getBookPromoCardLastShown(),
    ).thenAnswer((_) async => null);

    final strategy = const BookPromoCardInjectionStrategy(
      jokeContext: 'joke_feed',
    );
    final existingEntries = _buildJokeEntries(count: 5);
    final newEntries = _buildJokeEntries(count: 2, startIndex: 5);

    final result = await strategy.apply(
      ref: ref,
      existingEntries: existingEntries,
      newEntries: newEntries,
      hasMore: true,
    );

    expect(result, equals(newEntries));
  });

  test('does not insert when cooldown has not elapsed', () async {
    _arrangeRemoteConfigDefaults(mockRemoteValues);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 30);
    when(
      () => mockAppUsageService.getBookPromoCardLastShown(),
    ).thenAnswer((_) async => fixedNow.subtract(const Duration(days: 2)));

    final strategy = const BookPromoCardInjectionStrategy(
      jokeContext: 'joke_feed',
    );
    final existingEntries = _buildJokeEntries(count: 6);
    final newEntries = _buildJokeEntries(count: 1, startIndex: 6);

    final result = await strategy.apply(
      ref: ref,
      existingEntries: existingEntries,
      newEntries: newEntries,
      hasMore: true,
    );

    expect(result, equals(newEntries));
  });

  test('skips insertion when promo already exists', () async {
    _arrangeRemoteConfigDefaults(mockRemoteValues);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 25);
    when(
      () => mockAppUsageService.getBookPromoCardLastShown(),
    ).thenAnswer((_) async => null);

    final strategy = const BookPromoCardInjectionStrategy(
      jokeContext: 'joke_feed',
    );
    final existingEntries = [
      ..._buildJokeEntries(count: 5),
      const BookPromoSlotEntry(),
    ];
    final newEntries = _buildJokeEntries(count: 2, startIndex: 5);

    final result = await strategy.apply(
      ref: ref,
      existingEntries: existingEntries,
      newEntries: newEntries,
      hasMore: true,
    );

    expect(result, equals(newEntries));
  });
}

void _arrangeRemoteConfigDefaults(MockRemoteConfigValues remoteValues) {
  when(
    () => remoteValues.getInt(RemoteParam.bookPromoCardMinJokesViewed),
  ).thenReturn(20);
  when(
    () => remoteValues.getInt(RemoteParam.bookPromoCardInsertAfter),
  ).thenReturn(5);
  when(
    () => remoteValues.getInt(RemoteParam.bookPromoCardCooldownDays),
  ).thenReturn(5);
}

List<JokeSlotEntry> _buildJokeEntries({
  required int count,
  int startIndex = 0,
}) {
  return List<JokeSlotEntry>.generate(count, (index) {
    final jokeId = 'joke_${startIndex + index}';
    final joke = Joke(
      id: jokeId,
      setupText: 'Setup $jokeId',
      punchlineText: 'Punchline $jokeId',
      setupImageUrl: 'https://example.com/$jokeId-setup.png',
      punchlineImageUrl: 'https://example.com/$jokeId-punch.png',
    );
    return JokeSlotEntry(joke: JokeWithDate(joke: joke));
  });
}
