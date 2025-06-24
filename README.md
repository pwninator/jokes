# jokes

A jokes app

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.


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
