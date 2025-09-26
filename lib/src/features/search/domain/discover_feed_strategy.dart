import 'package:flutter/foundation.dart' show immutable;

enum DiscoverFeedType { all, popular }

@immutable
abstract class DiscoverFeedStrategy {
  const DiscoverFeedStrategy();

  const factory DiscoverFeedStrategy.all({required int limit}) =
      DiscoverAllStrategy;

  const factory DiscoverFeedStrategy.popular({required int limit}) =
      DiscoverPopularStrategy;

  DiscoverFeedType get type;

  /// Stable identifier for caching/analytics. Includes parameters.
  String get id;

  R when<R>({
    required R Function(DiscoverAllStrategy) all,
    required R Function(DiscoverPopularStrategy) popular,
  });
}

@immutable
class DiscoverAllStrategy extends DiscoverFeedStrategy {
  const DiscoverAllStrategy({required this.limit});

  final int limit;

  @override
  DiscoverFeedType get type => DiscoverFeedType.all;

  @override
  String get id => 'all:$limit';

  @override
  R when<R>({
    required R Function(DiscoverAllStrategy) all,
    required R Function(DiscoverPopularStrategy) popular,
  }) => all(this);

  @override
  bool operator ==(Object other) =>
      other is DiscoverAllStrategy && other.limit == limit;

  @override
  int get hashCode => Object.hashAll([limit]);
}

@immutable
class DiscoverPopularStrategy extends DiscoverFeedStrategy {
  const DiscoverPopularStrategy({required this.limit});

  final int limit;

  @override
  DiscoverFeedType get type => DiscoverFeedType.popular;

  @override
  String get id => 'popular:$limit';

  @override
  R when<R>({
    required R Function(DiscoverAllStrategy) all,
    required R Function(DiscoverPopularStrategy) popular,
  }) => popular(this);

  @override
  bool operator ==(Object other) =>
      other is DiscoverPopularStrategy && other.limit == limit;

  @override
  int get hashCode => Object.hashAll([limit]);
}
