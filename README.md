# Snickerdoodle - A Jokes App

Snickerdoodle is a mobile application built with Flutter that allows users to browse, laugh at, and manage a collection of jokes. It features user authentication, joke submissions (admin-only), and personalized user settings.

## Getting Started

This project serves as a demonstration of building a Flutter application with a feature-first architecture and Riverpod for state management.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Tech Stack

- **Flutter**: For building the cross-platform mobile application.
- **Dart**: The programming language used for Flutter development.
- **Riverpod**: For state management, providing a robust and scalable way to manage application state.
- **Firebase**:
    - **Firebase Auth**: For user authentication (Google Sign-In).
    - **Cloud Firestore**: As the NoSQL database for storing joke data.
    - **Cloud Functions**: For backend logic, such as admin-privileged actions.
- **shared_preferences**: For storing simple key-value user settings locally on the device.
- **http**: For making HTTP requests (e.g., to Cloud Functions).
- **cached_network_image**: For displaying and caching network images.
- **flutter_cache_manager**: For more advanced cache management.

## Design Patterns & Architecture

- **Feature-First Architecture**: The project is organized by features, promoting modularity and separation of concerns. Each feature (e.g., `auth`, `jokes`, `settings`) resides in its own directory within `lib/src/features/`.
- **Riverpod for State Management**: Leverages Riverpod for dependency injection and state management. Providers are used to expose services, manage application state, and rebuild widgets efficiently.
- **Repository Pattern**: While not explicitly enforced in all areas yet, the intention is to use repositories for abstracting data sources (e.g., Firestore, local cache). This can be seen in the `jokes` feature.
- **Service Layer**: Application logic that isn't directly related to UI or data persistence is encapsulated in services (e.g., `SettingsService`, `ImageService`). These services are typically provided via Riverpod.

## Directory Structure

This project follows a feature-first directory structure, organized to work well with Riverpod state management.

- **`lib/src/`**: Contains all the core application code.
  - **`app.dart`**: The root widget of the application (`App`), which is a `ConsumerWidget` and includes the `MaterialApp`.
  - **`config/`**: Application-level configuration.
    - **`router/`**: Intended for navigation logic (e.g., GoRouter setup). *(Currently contains a .gitkeep file)*
  - **`common_widgets/`**: For widgets shared across multiple features. *(Currently contains a .gitkeep file)*
  - **`core/`**: Core utilities, constants, and base styles.
    - **`theme/`**: Application theme definitions.
  - **`data/`**: For data persistence and retrieval logic (e.g., repositories, API clients). *(Currently contains a .gitkeep file)*
  - **`features/`**: Contains individual feature modules. Each feature typically has:
    - **`application/`**: Business logic and state management (e.g., Riverpod providers).
    - **`domain/`**: Core business models and entities for the feature (optional, depending on complexity).
    - **`presentation/`**: UI layer for the feature (widgets, screens).
    - **`settings/`**: Manages user-specific settings, like preferences, using `shared_preferences`.
  - **`providers/`**: For application-wide Riverpod providers that are not tied to a specific feature. *(Currently contains a .gitkeep file)*
  - **`utils/`**: General utility functions or classes. *(Currently contains a .gitkeep file)*
- **`lib/main.dart`**: The main entry point of the application, responsible for initializing the app and setting up the `ProviderScope` for Riverpod.

This structure aims to improve modularity, scalability, and separation of concerns.
