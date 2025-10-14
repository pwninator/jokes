import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';

import '../../../test_helpers/core_mocks.dart';

class _ThrowingInteractionsRepository extends JokeInteractionsRepository {
  _ThrowingInteractionsRepository({required super.db})
      : super(performanceService: MockPerformanceService());

  @override
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    return Stream<JokeInteraction?>.error(Exception('DB stream failure'));
  }
}

void main() {
  group('Stream providers (isJokeSavedProvider, isJokeSharedProvider)', () {
    late AppDatabase db;
    late ProviderContainer container;

    setUp(() {
      CoreMocks.reset();
      db = AppDatabase.inMemory();
      container = ProviderContainer(
        overrides: CoreMocks.getCoreProviderOverrides(
          additionalOverrides: [
            appDatabaseProvider.overrideWithValue(db),
          ],
        ),
      );
    });

    tearDown(() async {
      container.dispose();
    });

    test('isJokeSaved emits false initially when no interaction exists', () async {
      const id = 'j1';
      final values = <AsyncValue<bool>>[];
      final sub = container.listen(
        isJokeSavedProvider(id),
        (prev, next) => values.add(next),
        fireImmediately: true,
      );

      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(values.isNotEmpty, true);
      expect(values.last.hasValue, true);
      expect(values.last.value, false);

      sub.close();
    });

    test('isJokeSaved reacts to setSaved and setUnsaved', () async {
      const id = 'j2';
      final repo = container.read(jokeInteractionsRepositoryProvider);
      final events = <bool>[];
      final sub = container.listen(
        isJokeSavedProvider(id),
        (prev, next) {
          if (next.hasValue) events.add(next.requireValue);
        },
        fireImmediately: true,
      );

      // Initially false
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(events.last, false);

      // Save → true
      await repo.setSaved(id);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(events.last, true);

      // Unsaved → false
      await repo.setUnsaved(id);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(events.last, false);

      sub.close();
    });

    test('isJokeShared reacts to setShared', () async {
      const id = 'j3';
      final repo = container.read(jokeInteractionsRepositoryProvider);
      final events = <bool>[];

      final sub = container.listen(
        isJokeSharedProvider(id),
        (prev, next) {
          if (next.hasValue) events.add(next.requireValue);
        },
        fireImmediately: true,
      );

      // Initially false
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(events.last, false);

      // Shared → true
      await repo.setShared(id);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(events.last, true);

      sub.close();
    });

    test('multiple subscribers receive the same updates', () async {
      const id = 'j4';
      final repo = container.read(jokeInteractionsRepositoryProvider);
      final s1 = <bool>[];
      final s2 = <bool>[];

      final sub1 = container.listen(
        isJokeSavedProvider(id),
        (prev, next) {
          if (next.hasValue) s1.add(next.requireValue);
        },
        fireImmediately: true,
      );
      final sub2 = container.listen(
        isJokeSavedProvider(id),
        (prev, next) {
          if (next.hasValue) s2.add(next.requireValue);
        },
        fireImmediately: true,
      );

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await repo.setSaved(id);
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(s1.isNotEmpty && s2.isNotEmpty, true);
      expect(s1.last, true);
      expect(s2.last, true);

      sub1.close();
      sub2.close();
    });

    test('provider surfaces stream errors', () async {
      const id = 'err';
      final errorContainer = ProviderContainer(
        overrides: CoreMocks.getCoreProviderOverrides(
          additionalOverrides: [
            appDatabaseProvider.overrideWithValue(db),
            jokeInteractionsRepositoryProvider.overrideWith((ref) {
              return _ThrowingInteractionsRepository(db: db);
            }),
          ],
        ),
      );

      final values = <AsyncValue<bool>>[];
      final sub = errorContainer.listen(
        isJokeSavedProvider(id),
        (prev, next) => values.add(next),
        fireImmediately: true,
      );

      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(values.any((v) => v.hasError), true);

      sub.close();
      errorContainer.dispose();
    });

    test('independent streams for different joke IDs', () async {
      const a = 'a', b = 'b';
      final repo = container.read(jokeInteractionsRepositoryProvider);
      final va = <bool>[];
      final vb = <bool>[];

      final subA = container.listen(
        isJokeSavedProvider(a),
        (prev, next) {
          if (next.hasValue) va.add(next.requireValue);
        },
        fireImmediately: true,
      );
      final subB = container.listen(
        isJokeSavedProvider(b),
        (prev, next) {
          if (next.hasValue) vb.add(next.requireValue);
        },
        fireImmediately: true,
      );

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await repo.setSaved(a);
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(va.last, true);
      expect(vb.last, false);

      subA.close();
      subB.close();
    });
  });
}
