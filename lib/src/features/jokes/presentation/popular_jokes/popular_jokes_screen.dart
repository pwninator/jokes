import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/popular_jokes_paginator_provider.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class PopularJokesScreen extends ConsumerWidget {
  const PopularJokesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AdaptiveAppBarScreen(
      title: 'Popular Jokes',
      body: JokeListViewer(
        jokesAsyncProvider: popularJokesProvider,
        paginatorNotifierProvider: popularJokesPaginatorProvider,
        jokeContext: AnalyticsJokeContext.popularJokes,
        viewerId: 'popular_jokes',
      ),
    );
  }
}
