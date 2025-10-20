import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

part 'url_launcher_service.g.dart';

/// Shared provider for the app-wide URL launcher service.
@Riverpod(keepAlive: true)
UrlLauncherService urlLauncherService(Ref ref) {
  return const UrlLauncherService();
}

/// Thin wrapper around the `url_launcher` plugin so that widgets and view
/// models can depend on an easily-mockable abstraction in tests.
class UrlLauncherService {
  const UrlLauncherService();

  /// Launch [url] using the provided [mode].
  Future<bool> launchUrl(Uri url) {
    return url_launcher.launchUrl(
      url,
      mode: url_launcher.LaunchMode.externalApplication,
    );
  }
}
