// Platform-specific database executors for Drift via conditional exports

export 'app_database_platform_native.dart'
    if (dart.library.html) 'app_database_platform_web.dart';
