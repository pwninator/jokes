# AGENTS.md: AI Agent Instructions for Snickerdoodle Jokes App

This document contains everything AI agents need to work effectively on this codebase. It combines project overview, architecture, testing patterns, and operational guidelines.

## 1. Project Overview

**Snickerdoodle** is a mobile jokes app that delivers AI-generated illustrated jokes to users.

### 1.1. Tech Stack

**Frontend (Flutter/Dart)**:
- Framework: Flutter with `flutter_riverpod` for state management
- Navigation: `go_router`
- Backend: Firebase (Auth, Firestore, Cloud Functions, Messaging, Analytics)
- Local Storage: Drift (on-device SQL)
- Code Generation: `build_runner`

**Backend (Python)**:
- Firebase Cloud Functions for APIs
- Flask + Jinja for SEO web layer
- Agents/tools in `py_quill/agents/` and services in `py_quill/services/`
- LLM Services: Google AI (Vertex), OpenAI, Anthropic

### 1.2. System Architecture

```
Client (Flutter App)
  ↓
Firebase (BaaS)
  ├─ Firestore (database)
  ├─ Authentication
  ├─ Cloud Storage (images)
  └─ Cloud Functions (Python backend)
      ↓
  External AI Services (LLMs, Image Generation)
```

**Data Flow**:
1. App requests joke from Firestore
2. If generation needed, Cloud Function triggers
3. Function calls LLM → generates joke → generates images
4. Saves to Firestore + Cloud Storage
5. App receives real-time updates

## 2. Directory Structure

### 2.1. Flutter (`lib/src/`)

```
lib/src/
├── common_widgets/      # Reusable UI components
├── config/              # App configuration (themes, routing)
├── core/                # Core logic (services, providers)
├── data/                # Data layer (repositories, local storage)
├── features/            # Feature modules
│   ├── admin/           # Admin panel screens
│   ├── auth/            # Authentication
│   ├── book_creator/    # Joke book creation
│   ├── feedback/        # User feedback
│   ├── jokes/           # Main joke features
│   ├── search/          # Search and discovery
│   └── settings/        # User settings
├── providers/           # Riverpod providers
├── startup/             # App initialization
└── utils/               # Utility functions
```

### 2.2. Python (`py_quill/`)

```
py_quill/
├── agents/              # ADK agents for content generation
├── common/              # Shared utilities and models
├── functions/           # Cloud Functions entry points
├── services/            # External service clients (LLM, Firestore, Storage)
└── web/                 # Flask app (templates, routes)
```

### 2.3. Tests

```
test/
├── common_widgets/      # Widget tests
├── core/                # Core service tests
├── data/                # Repository/data layer tests
├── features/            # Feature tests (mirror lib/src/features)
└── test_helpers/        # (deprecated - being removed)
```

## 3. Core Development Directives

### 3.1. Making Changes

- Make **correct, verifiable, minimal** changes
- Tests are **mandatory** for changed behavior
- Target **near 100% coverage** for new code
- Do **NOT** run `flutter run` for verification (use tests)

### 3.2. Code Style

**Flutter**:
- Run `dart format .` before committing
- Run `flutter analyze` and fix all issues
- Run `flutter test` to verify changes

**Python**:
- Keep names clear, functions small, docstrings concise
- Match existing style in `py_quill/`

### 3.3. Widget Keys (Flutter)

**All interactive widgets MUST have unique keys** for testing and automation.

**Naming Convention**: `Key('filename-widget-description')`

Examples:
- `Key('feedback_dialog-submit-button')`
- `Key('user_settings_screen-google-sign-in-button')`
- `Key('save_joke_button-$jokeId')` (with dynamic ID)

Interactive widgets include: buttons, text inputs, toggles, sliders, dropdowns, gesture detectors, list tiles.

### 3.4. Analytics & Error Reporting

**Flutter**:
- Error-like analytics events MUST also log Crashlytics non-fatal via `AnalyticsService`
- Tests should verify both are called

**Python**:
- Use Cloud Logging only (not Flutter Analytics/Crashlytics)

## 4. Testing Strategy

The app follows **Riverpod's official testing best practices** for test isolation and clarity.

### 4.1. Core Testing Principles

1. **No Shared State**: Each test creates its own fresh mocks
2. **Explicit Dependencies**: All provider overrides visible in test
3. **Mock at Repository Layer**: Widget/service tests mock repositories, not databases
4. **Real DB Only for Data Layer**: Only repository tests use `AppDatabase.inMemory()` with proper cleanup

### 4.2. Flutter Test Pattern

```dart
// Mock class declarations at top of file
class MockJokeRepository extends Mock implements JokeRepository {}
class MockAppUsageService extends Mock implements AppUsageService {}

void main() {
  setUpAll(() {
    // Only mocktail fallback registrations
    registerFallbackValue(FakeJoke());
  });

  late MockJokeRepository mockJokeRepository;
  late MockAppUsageService mockAppUsageService;

  setUp(() {
    // Create fresh mocks per test
    mockJokeRepository = MockJokeRepository();
    mockAppUsageService = MockAppUsageService();
    
    // Stub default behavior
    when(() => mockJokeRepository.getJokes()).thenAnswer((_) async => []);
    when(() => mockAppUsageService.logJokeViewed(any())).thenAnswer((_) async {});
  });

  testWidgets('description of behavior being tested', (tester) async {
    // Arrange: Test-specific stubs
    when(() => mockJokeRepository.getJokes()).thenAnswer((_) async => testJokes);
    
    // Act: Build widget with explicit overrides
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          // Only providers this widget actually needs
        ],
        child: MaterialApp(home: WidgetUnderTest()),
      ),
    );
    
    // Assert: Verify behavior
    expect(find.text('Expected Text'), findsOneWidget);
    verify(() => mockAppUsageService.logJokeViewed('joke-1')).called(1);
  });
}
```

### 4.3. Repository/Data Layer Test Pattern

```dart
void main() {
  late AppDatabase db;
  late JokeInteractionsRepository repository;

  setUp(() {
    db = AppDatabase.inMemory();
    repository = JokeInteractionsRepository(
      db: db,
      performanceService: NoopPerformanceService(),
    );
  });

  tearDown() async {
    await db.close(); // Always close to prevent leaks
  });

  test('setSaved stores joke interaction', () async {
    // Arrange, Act, Assert using real DB
    await repository.setSaved('joke-1');
    final saved = await repository.getSavedJokeInteractions();
    
    expect(saved.length, 1);
    expect(saved.first.jokeId, 'joke-1');
  });
}
```

### 4.4. Python Testing

- Use `pytest` and Flask test client
- Mock `services.search`, `services.firestore` where needed
- For web layer, verify:
  - Canonical and social meta tags
  - JSON-LD structured data
  - Caching headers
  - Image attributes (`loading="lazy"`, width, height)

### 4.5. Test Design Guidelines

- **One Behavior Per Test**: Each test verifies a single, well-defined behavior
- **Focused**: Not too broad (workflows) or too trivial (getters/setters)
- **Clear AAA**: Arrange-Act-Assert structure
- **Minimal Mocks**: Only mock what the test actually needs
- **No Test-Only Code**: Production code should not have test-specific branches

## 5. Commands

Run from repository root.

### 5.1. Flutter

```bash
# Install dependencies
flutter pub get

# Generate code (after provider changes)
dart run build_runner build --delete-conflicting-outputs

# Run tests
flutter test

# Run single test file
flutter test test/path/to/test_file.dart

# Analyze code
flutter analyze

# Format code
dart format .
```

### 5.2. Python

```bash
# Install dependencies
pip install -r py_quill/requirements.txt

# Run tests
pytest py_quill

# Run with coverage
pytest py_quill --cov=py_quill --cov-report=term-missing
```

**Important**: Python imports inside `py_quill/` must be relative to `py_quill` root:
```python
# ✅ Correct
from common import models

# ❌ Wrong
from py_quill.common import models
from ..common import models
```

## 6. Key Features & Screens

### 6.1. User-Facing Features

**Jokes**:
- `DailyJokesScreen`: Main feed of latest jokes
- `SavedJokesScreen`: User's saved jokes

**Search & Discovery**:
- `DiscoverScreen`: Browse by categories/trending
- `SearchScreen`: Active search for jokes

**User Features**:
- `UserFeedbackScreen`: Submit feedback
- `UserSettingsScreen`: Account settings, sign-in

**Book Creator**:
- `BookCreatorScreen`: Create joke book collections
- `JokeSelectorScreen`: Select jokes for books

### 6.2. Admin Features

**Admin Dashboard**:
- `JokeAdminScreen`: Main admin hub with navigation

**Joke Management**:
- `JokeManagementScreen`: Search, filter, manage all jokes
- `JokeEditorScreen`: Create/edit individual jokes
- `JokeCreatorScreen`: AI-assisted joke generation
- `JokeSchedulerScreen`: Schedule jokes for publication
- `DeepResearchScreen`: Bulk AI joke generation workflow

**Categories**:
- `JokeCategoriesScreen`: View all categories (responsive grid)
- `JokeCategoryEditorScreen`: Edit category details/images

**Analytics & Feedback**:
- `UsersAnalyticsScreen`: User activity histograms
- `JokeFeedbackScreen`: Review user feedback threads
- `FeedbackConversationScreen`: View/reply to feedback

**Auth**:
- Anonymous browsing allowed
- `AuthGuard` protects admin routes
- Google Sign-In via settings screen

## 7. Backend Cloud Functions

### 7.1. Admin Functions (`admin_fns.py`)

- `set_user_role`: Assign user roles (e.g., admin)

### 7.2. Analytics Functions (`analytics_fns.py`)

- `usage`: Track and update user activity stats

### 7.3. Joke Functions (`joke_fns.py`)

**HTTP Endpoints**:
- `create_joke`: Create new joke document
- `search_jokes`: Vector similarity search
- `populate_joke`: Generate AI images/metadata for joke
- `modify_joke_image`: Edit joke images via text instructions
- `critique_jokes`: AI critique of jokes
- `upscale_joke`: Upscale joke images
- `send_daily_joke_scheduler/http`: Send FCM notifications

**Firestore Triggers**:
- `on_joke_write`: Update embeddings, popularity, search index
- `on_joke_category_write`: Generate category images on description change

### 7.4. Other Functions

- `book_fns.py`: Joke book management
- `character_fns.py`: Character management
- `joke_book_fns.py`: Book contents/creation
- `story_prompt_fns.py`: Story prompt generation
- `user_fns.py`: User data management
- `util_fns.py`: Utility functions
- `web_fns.py`: Flask web layer (SEO pages, search)

### 7.5. ADK Agents

Located in `py_quill/agents/`:
- `jokes_agent.py`: Primary joke generation
- `categorizer_agent.py`: Joke categorization
- `punny_joke_agents.py`: Pun creation
- `updater_agent.py`: Content updates

## 8. Flask Web Layer

**Entry Point**: `py_quill/functions/web_fns.py` (exports `web_search_page`)

**Routes**:
- `GET /jokes/<topic>`: SEO-optimized topic page
- `GET /sitemap.xml`: Sitemap for topic pages
- `GET /search`: Simple search interface

**Templates** (`py_quill/web/templates/`):
- `base.html`: Canonical link, OpenGraph/Twitter meta, responsive layout
- `topic.html`: JSON-LD FAQPage, accessible reveal, lazy images

**SEO Requirements**:
- Setup image/text visible; punchline in `<details><summary>`
- Caching headers: `Cache-Control`, `ETag`, `Last-Modified`
- Images: `loading="lazy"`, width, height attributes
- Structured data: JSON-LD with `FAQPage` schema

## 9. Conventions

### 9.1. Naming

- Functions: verbs (e.g., `fetchJokes`, `updateUser`)
- Variables: nouns (e.g., `jokeList`, `userName`)
- Clear, meaningful names (no abbreviations)

### 9.2. Control Flow

- Use early returns
- Explicit error handling
- Avoid deep nesting

### 9.3. Comments

- Explain "why," not "how"
- No TODO comments (implement or remove)

## 10. Environment Setup

### 10.1. Jules Agent

Sync to latest:
```bash
git fetch origin
git rebase origin/master
```

### 10.2. All Other Agents

Environment is pre-configured. No setup needed.

## 11. Deployment

- Python functions exported in `py_quill/main.py`
- Flask served via `web_search_page` function
- Firebase Hosting rewrites:
  - `/jokes/**`, `/sitemap.xml` → Python HTTPS Function
  - Static assets → Hosting/CDN
- Keep timeouts/memory reasonable
- Batch Firestore reads where possible

## 12. Quick Checklists

### Flutter Change
- [ ] Tests under `test/` (mirror `lib/` structure)
- [ ] All interactive widgets have unique keys (`Key('filename-widget-description')`)
- [ ] `dart format .`
- [ ] `flutter analyze` (fix all issues)
- [ ] `flutter test` (all pass)

### Python Change
- [ ] Tests under `py_quill/**/*_test.py`
- [ ] `pip install -r py_quill/requirements.txt`
- [ ] `pytest py_quill` (all pass)
- [ ] Verify headers/SEO (web layer changes)

## 13. Common Patterns

### 13.1. Riverpod Provider Override

```dart
// In tests, override providers explicitly
final container = ProviderContainer(
  overrides: [
    someProvider.overrideWithValue(mockImplementation),
  ],
);
```

### 13.2. Repository Test with DB

```dart
setUp(() => db = AppDatabase.inMemory());
tearDown() async => await db.close();
```

### 13.3. Firebase Analytics Event

```dart
await analyticsService.logEvent(
  'joke_viewed',
  parameters: {'joke_id': jokeId},
);
```

### 13.4. Python Import Pattern

```python
# Correct for py_quill/ files
from common import models
from services import firestore
```

## 14. Critical Reminders

1. **Never** run `flutter run` for verification—use tests
2. **Always** create tests for new/changed behavior
3. **Never** use shared mock singletons in tests
4. **Always** close `AppDatabase` in repository test tearDown
5. **Always** add keys to interactive widgets
6. **Never** commit TODO comments
7. **Always** format/analyze before committing

---

**For detailed API specs, see Cloud Function docstrings in `py_quill/functions/`**
**For UI flows, see widget implementations in `lib/src/features/`**
