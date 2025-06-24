import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeViewerScreen extends ConsumerStatefulWidget implements TitledScreen {
  const JokeViewerScreen({super.key});

  @override
  String get title => 'Jokes';

  @override
  ConsumerState<JokeViewerScreen> createState() => _JokeViewerScreenState();
}

class _JokeViewerScreenState extends ConsumerState<JokeViewerScreen> {
  int _currentPage = 0;
  late PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goToNextJoke(int totalJokes) {
    final nextPage = _currentPage + 1;
    if (nextPage < totalJokes) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final jokesAsyncValue = ref.watch(jokesWithImagesProvider);

    return Scaffold(
      appBar: const AppBarWidget(
        title: 'Jokes',
      ),
      body: jokesAsyncValue.when(
        data: (jokes) {
          if (jokes.isEmpty) {
            return const Center(
              child: Text('No jokes found! Try adding some.'),
            );
          }

          // Ensure current page is within bounds
          final safeCurrentPage = _currentPage.clamp(0, jokes.length - 1);
          if (_currentPage != safeCurrentPage) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                setState(() {
                  _currentPage = safeCurrentPage;
                });
              }
            });
          }

          return Stack(
            children: [
              PageView.builder(
                controller: _pageController,
                scrollDirection: Axis.vertical,
                itemCount: jokes.length,
                onPageChanged: (index) {
                  if (mounted) {
                    setState(() {
                      _currentPage = index;
                    });
                  }
                },
                itemBuilder: (context, index) {
                  final joke = jokes[index];
                  final List<Joke> jokesToPreload = [];
                  if (index + 1 < jokes.length) {
                    jokesToPreload.add(jokes[index + 1]);
                  }
                  if (index + 2 < jokes.length) {
                    jokesToPreload.add(jokes[index + 2]);
                  }

                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: JokeCard(
                        joke: joke,
                        index: index,
                        onPunchlineTap: () => _goToNextJoke(jokes.length),
                        isAdminMode: false,
                        jokesToPreload: jokesToPreload,
                      ),
                    ),
                  );
                },
              ),
              // Page indicator at the bottom
              if (jokes.length > 1)
                Positioned(
                  bottom: 20,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.6),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        '${safeCurrentPage + 1} of ${jokes.length}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) {
          debugPrint('Error loading jokes: $error');
          debugPrint('Stack trace: $stackTrace');
          return Center(child: Text('Error loading jokes: $error'));
        },
      ),
    );
  }
}
