# Image Infrastructure Usage

This directory contains the image infrastructure for the jokes app. Here's how to use the components:

## CachedJokeImage Widget

The main widget for displaying joke images with caching:

```dart
// Basic usage
CachedJokeImage(
  imageUrl: joke.imageUrl,
  width: 200,
  height: 150,
)

// With custom styling
CachedJokeImage(
  imageUrl: joke.imageUrl,
  width: 300,
  height: 200,
  fit: BoxFit.cover,
  borderRadius: BorderRadius.circular(12),
  showLoadingIndicator: true,
  showErrorIcon: true,
)
```

## CachedJokeThumbnail Widget

For small thumbnail images:

```dart
CachedJokeThumbnail(
  imageUrl: joke.imageUrl,
  size: 80, // Both width and height
)
```

## CachedJokeHeroImage Widget

For full-size images with hero animations:

```dart
CachedJokeHeroImage(
  imageUrl: joke.imageUrl,
  heroTag: 'joke-${joke.id}',
  width: double.infinity,
  height: 300,
  onTap: () {
    // Handle tap - maybe show full screen
  },
)
```

## Key Features

- **Automatic caching**: Images are cached automatically by URL
- **Consistent styling**: All image widgets use the app theme
- **Error handling**: Graceful fallbacks for failed image loads
- **Loading states**: Built-in loading indicators
- **Memory management**: Efficient memory and disk usage
- **Shared cache**: All widgets share the same cache automatically

## Architecture

- **CachedJokeImage**: Main widget (screens use this)
- **ImageService**: Business logic (internal use)
- **imageServiceProvider**: Riverpod provider (internal use)

Screens only need to import and use the image widgets. The service and provider are internal implementation details. 