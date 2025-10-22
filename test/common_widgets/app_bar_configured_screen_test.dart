import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  ProviderContainer createContainer() {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    return container;
  }

  Widget wrapWithScope(Widget child, ProviderContainer container) {
    return UncontrolledProviderScope(container: container, child: child);
  }

  Future<void> pumpAndSettleAll(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 10));
    await tester.pumpAndSettle();
  }

  testWidgets('applies provided configuration and floating action button', (
    tester,
  ) async {
    final container = createContainer();
    final leading = IconButton(
      key: const Key('custom-leading'),
      icon: const Icon(Icons.menu),
      onPressed: () {},
    );
    final action = IconButton(
      key: const Key('custom-action'),
      icon: const Icon(Icons.refresh),
      onPressed: () {},
    );

    await tester.pumpWidget(
      wrapWithScope(
        MaterialApp(
          home: AppBarConfiguredScreen(
            title: 'Configured',
            leading: leading,
            actions: [action],
            floatingActionButton: const FloatingActionButton(
              onPressed: null,
              child: Icon(Icons.add),
            ),
            body: const SizedBox.shrink(),
          ),
        ),
        container,
      ),
    );
    await pumpAndSettleAll(tester);

    final config = container.read(appBarConfigProvider);
    expect(config, isNotNull);
    expect(config!.title, 'Configured');
    expect(config.leading, same(leading));
    expect(config.actions, isNotEmpty);
    expect(config.actions!.single, same(action));
    expect(config.automaticallyImplyLeading, isTrue);

    final fab = container.read(floatingActionButtonProvider);
    expect(fab, isNotNull);
    expect(fab, isA<FloatingActionButton>());
  });

  testWidgets(
    'uses navigator fallback to provide back button and restores previous config after pop',
    (tester) async {
      final container = createContainer();
      final navKey = GlobalKey<NavigatorState>();

      await tester.pumpWidget(
        wrapWithScope(
          MaterialApp(
            navigatorKey: navKey,
            home: _RootNavigatorScreen(
              onNavigate: (context) => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => const _TestScreen(title: 'Second'),
                ),
              ),
            ),
          ),
          container,
        ),
      );
      await pumpAndSettleAll(tester);

      expect(container.read(appBarConfigProvider)!.title, 'Root');
      expect(container.read(appBarConfigProvider)!.leading, isNull);

      await tester.tap(find.byKey(const Key('push-button')));
      await pumpAndSettleAll(tester);

      final pushedConfig = container.read(appBarConfigProvider);
      expect(pushedConfig!.title, 'Second');
      expect(
        pushedConfig.leading,
        isA<IconButton>().having(
          (b) => b.key,
          'key',
          const Key('app_bar_configured_screen-back-button'),
        ),
      );

      navKey.currentState!.pop();
      await pumpAndSettleAll(tester);

      final restored = container.read(appBarConfigProvider);
      expect(restored!.title, 'Root');
      expect(restored.leading, isNull);
    },
  );

  testWidgets('respects explicit leading even when navigation stack can pop', (
    tester,
  ) async {
    final container = createContainer();
    final customLeading = IconButton(
      key: const Key('override-leading'),
      icon: const Icon(Icons.close),
      onPressed: () {},
    );

    await tester.pumpWidget(
      wrapWithScope(
        MaterialApp(
          home: _RootNavigatorScreen(
            onNavigate: (context) => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) =>
                    _TestScreen(title: 'Custom', leading: customLeading),
              ),
            ),
          ),
        ),
        container,
      ),
    );
    await pumpAndSettleAll(tester);

    await tester.tap(find.byKey(const Key('push-button')));
    await pumpAndSettleAll(tester);

    final config = container.read(appBarConfigProvider);
    expect(config!.title, 'Custom');
    expect(config.leading, same(customLeading));
  });

  testWidgets('does not add automatic leading when disabled', (tester) async {
    final container = createContainer();

    await tester.pumpWidget(
      wrapWithScope(
        MaterialApp(
          home: _RootNavigatorScreen(
            onNavigate: (context) => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => const _TestScreen(
                  title: 'NoBack',
                  automaticallyImplyLeading: false,
                ),
              ),
            ),
          ),
        ),
        container,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('push-button')));
    await pumpAndSettleAll(tester);

    final config = container.read(appBarConfigProvider);
    expect(config!.title, 'NoBack');
    expect(config.leading, isNull);
  });

  testWidgets(
    'uses GoRouter to provide automatic back button and updates after pop',
    (tester) async {
      final container = createContainer();

      late final GoRouter router;
      router = GoRouter(
        initialLocation: '/root',
        routes: [
          GoRoute(
            path: '/root',
            builder: (context, state) => _TestScreen(
              title: 'Discover',
              body: ElevatedButton(
                key: const Key('go-second'),
                onPressed: () => GoRouter.of(context).go('/root/second'),
                child: const Text('Next'),
              ),
            ),
            routes: [
              GoRoute(
                path: 'second',
                builder: (context, state) => const _TestScreen(title: 'Search'),
              ),
            ],
          ),
        ],
      );
      addTearDown(router.dispose);

      await tester.pumpWidget(
        wrapWithScope(MaterialApp.router(routerConfig: router), container),
      );
      await pumpAndSettleAll(tester);

      expect(container.read(appBarConfigProvider)!.title, 'Discover');

      await tester.tap(find.byKey(const Key('go-second')));
      await pumpAndSettleAll(tester);

      final secondConfig = container.read(appBarConfigProvider);
      expect(secondConfig!.title, 'Search');
      expect(
        secondConfig.leading,
        isA<IconButton>().having(
          (b) => b.key,
          'key',
          const Key('app_bar_configured_screen-back-button'),
        ),
      );

      router.go('/root');
      await pumpAndSettleAll(tester);

      final restored = container.read(appBarConfigProvider);
      expect(restored!.title, 'Discover');
      expect(restored.leading, isNull);
    },
  );

  testWidgets(
    'reapplies configuration when a previously hidden route becomes current again',
    (tester) async {
      final container = createContainer();
      final rootKey = GlobalKey<_DynamicTitleScreenState>();

      late final GoRouter router;
      router = GoRouter(
        initialLocation: '/root',
        routes: [
          GoRoute(
            path: '/root',
            builder: (context, state) => _DynamicTitleScreen(
              key: rootKey,
              onNavigate: () => GoRouter.of(context).go('/root/second'),
            ),
            routes: [
              GoRoute(
                path: 'second',
                builder: (context, state) => const _TestScreen(title: 'Second'),
              ),
            ],
          ),
        ],
      );
      addTearDown(router.dispose);

      await tester.pumpWidget(
        wrapWithScope(MaterialApp.router(routerConfig: router), container),
      );
      await pumpAndSettleAll(tester);

      expect(container.read(appBarConfigProvider)!.title, 'Root');

      rootKey.currentState!.setTitle('Root Updated');
      await pumpAndSettleAll(tester);
      expect(container.read(appBarConfigProvider)!.title, 'Root Updated');

      await tester.tap(find.byKey(const Key('dynamic-push-button')));
      await pumpAndSettleAll(tester);
      expect(container.read(appBarConfigProvider)!.title, 'Second');

      rootKey.currentState!.setTitle('Root After Pop');
      await pumpAndSettleAll(tester);
      expect(container.read(appBarConfigProvider)!.title, 'Second');

      router.go('/root');
      await pumpAndSettleAll(tester);
      expect(container.read(appBarConfigProvider)!.title, 'Root After Pop');
    },
  );

  testWidgets('updates floating action button when routes change', (
    tester,
  ) async {
    final container = createContainer();
    final navKey = GlobalKey<NavigatorState>();

    await tester.pumpWidget(
      wrapWithScope(
        MaterialApp(
          navigatorKey: navKey,
          home: _RootNavigatorScreen(
            onNavigate: (context) => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => const _TestScreen(
                  title: 'Second',
                  floatingActionButton: FloatingActionButton(
                    onPressed: null,
                    child: Icon(Icons.favorite),
                  ),
                ),
              ),
            ),
          ),
        ),
        container,
      ),
    );
    await pumpAndSettleAll(tester);

    expect(container.read(floatingActionButtonProvider), isNull);

    await tester.tap(find.byKey(const Key('push-button')));
    await pumpAndSettleAll(tester);

    final fab = container.read(floatingActionButtonProvider);
    expect(fab, isA<FloatingActionButton>());

    navKey.currentState!.pop();
    await pumpAndSettleAll(tester);

    expect(container.read(floatingActionButtonProvider), isNull);
  });
}

class _RootNavigatorScreen extends StatelessWidget {
  const _RootNavigatorScreen({required this.onNavigate});

  final void Function(BuildContext) onNavigate;

  @override
  Widget build(BuildContext context) {
    return _TestScreen(
      title: 'Root',
      body: ElevatedButton(
        key: const Key('push-button'),
        onPressed: () => onNavigate(context),
        child: const Text('Push'),
      ),
    );
  }
}

class _TestScreen extends StatelessWidget {
  const _TestScreen({
    required this.title,
    this.leading,
    this.automaticallyImplyLeading = true,
    this.floatingActionButton,
    this.body,
  });

  final String title;
  final Widget? leading;
  final bool automaticallyImplyLeading;
  final Widget? floatingActionButton;
  final Widget? body;

  @override
  Widget build(BuildContext context) {
    return AppBarConfiguredScreen(
      title: title,
      leading: leading,
      automaticallyImplyLeading: automaticallyImplyLeading,
      floatingActionButton: floatingActionButton,
      body: body ?? const SizedBox.shrink(),
    );
  }
}

class _DynamicTitleScreen extends StatefulWidget {
  const _DynamicTitleScreen({super.key, required this.onNavigate});

  final VoidCallback onNavigate;

  @override
  State<_DynamicTitleScreen> createState() => _DynamicTitleScreenState();
}

class _DynamicTitleScreenState extends State<_DynamicTitleScreen> {
  String _title = 'Root';

  void setTitle(String value) {
    setState(() {
      _title = value;
    });
  }

  @override
  Widget build(BuildContext context) {
    return _TestScreen(
      title: _title,
      body: ElevatedButton(
        key: const Key('dynamic-push-button'),
        onPressed: widget.onNavigate,
        child: const Text('To Second'),
      ),
    );
  }
}
