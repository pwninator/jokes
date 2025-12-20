import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';

import 'slot_entries.dart';

/// Base contract for slot-injection strategies.
///
/// Implementations receive both the committed entries (what the viewer already
/// renders) and the new entries that are about to be appended. Strategies may
/// examine either list, inject additional [SlotEntry] instances, or leave the
/// list unchanged. Implementations **must** ensure that every element of
/// [newEntries] is still present in the returned list to avoid dropping jokes.
abstract class SlotInjectionStrategy {
  const SlotInjectionStrategy();

  FutureOr<List<SlotEntry>> apply({
    required Ref ref,
    required List<SlotEntry> existingEntries,
    required List<SlotEntry> newEntries,
    required bool hasMore,
  });
}

/// Inserts a single end-of-feed entry when pagination reports no more items.
class EndOfFeedSlotInjectionStrategy extends SlotInjectionStrategy {
  const EndOfFeedSlotInjectionStrategy({required this.jokeContext});

  final String jokeContext;

  @override
  List<SlotEntry> apply({
    required Ref ref,
    required List<SlotEntry> existingEntries,
    required List<SlotEntry> newEntries,
    required bool hasMore,
  }) {
    if (hasMore) {
      return newEntries;
    }

    // Only inject EndOfFeed if there are already existing entries.
    if (existingEntries.isEmpty) return newEntries;

    // Avoid duplicating EndOfFeed if it was already injected previously.
    final SlotEntry? lastExisting = existingEntries.isNotEmpty
        ? existingEntries.last
        : null;
    if (newEntries.isEmpty && _isEndOfFeedEntry(lastExisting)) {
      return newEntries;
    }

    final totalJokes =
        existingEntries.whereType<JokeSlotEntry>().length +
        newEntries.whereType<JokeSlotEntry>().length;

    return [
      ...newEntries,
      EndOfFeedSlotEntry(jokeContext: jokeContext, totalJokes: totalJokes),
    ];
  }

  bool _isEndOfFeedEntry(SlotEntry? entry) =>
      entry is EndOfFeedSlotEntry && entry.jokeContext == jokeContext;
}

/// Injection strategy that inserts a promotional card after a configured
/// number of jokes when engagement criteria are met.
class BookPromoCardInjectionStrategy extends SlotInjectionStrategy {
  const BookPromoCardInjectionStrategy({required this.jokeContext});

  final String jokeContext;

  @override
  Future<List<SlotEntry>> apply({
    required Ref ref,
    required List<SlotEntry> existingEntries,
    required List<SlotEntry> newEntries,
    required bool hasMore,
  }) async {
    if (_hasExistingPromo(existingEntries) ||
        _hasExistingPromo(newEntries) ||
        newEntries.isEmpty) {
      return newEntries;
    }

    final remoteValues = ref.read(remoteConfigValuesProvider);
    final insertAfter = remoteValues.getInt(
      RemoteParam.bookPromoCardInsertAfter,
    );
    if (insertAfter < 0) {
      return newEntries;
    }

    final existingJokeCount = _countJokeEntries(existingEntries);
    final totalJokeCount = existingJokeCount + _countJokeEntries(newEntries);

    if (totalJokeCount < insertAfter) {
      return newEntries;
    }

    final minJokesViewed = remoteValues.getInt(
      RemoteParam.bookPromoCardMinJokesViewed,
    );
    final cooldownDays = remoteValues.getInt(
      RemoteParam.bookPromoCardCooldownDays,
    );

    final appUsage = ref.read(appUsageServiceProvider);
    final jokesViewed = await appUsage.getNumJokesViewed();
    if (jokesViewed < minJokesViewed) {
      return newEntries;
    }

    final lastShown = await appUsage.getBookPromoCardLastShown();
    final now = ref.read(clockProvider)();
    if (lastShown != null) {
      final daysSince = now.difference(lastShown).inDays;
      if (daysSince < cooldownDays) {
        return newEntries;
      }
    }

    // Insert promo card before the joke that exceeds the threshold.
    return _injectPromoCard(
      newEntries: newEntries,
      existingJokeCount: existingJokeCount,
      insertAfter: insertAfter,
    );
  }

  List<SlotEntry> _injectPromoCard({
    required List<SlotEntry> newEntries,
    required int existingJokeCount,
    required int insertAfter,
  }) {
    if (insertAfter == 0 && existingJokeCount == 0) {
      return [const BookPromoSlotEntry(), ...newEntries];
    }

    final List<SlotEntry> injected = [];
    int jokeCount = existingJokeCount;
    bool promoInserted = false;

    for (final entry in newEntries) {
      if (!promoInserted && jokeCount >= insertAfter) {
        injected.add(const BookPromoSlotEntry());
        promoInserted = true;
      }

      injected.add(entry);

      if (entry is JokeSlotEntry) {
        jokeCount++;
      }
    }

    if (!promoInserted && jokeCount >= insertAfter) {
      injected.add(const BookPromoSlotEntry());
    }

    return injected;
  }

  bool _hasExistingPromo(List<SlotEntry> entries) =>
      entries.any((entry) => entry is BookPromoSlotEntry);

  int _countJokeEntries(List<SlotEntry> entries) =>
      entries.whereType<JokeSlotEntry>().length;
}
