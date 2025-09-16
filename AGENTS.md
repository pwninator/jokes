## AGENTS.md: Instructions for AI Agents

This repository contains a Flutter app and a Python Cloud Functions codebase. Follow these rules to keep changes correct, testable, and consistent.

## 1. Project overview

- Flutter app (`snickerdoodle`)
  - Framework: Flutter (Dart)
  - State management: `flutter_riverpod`
  - Navigation: `go_router`
  - Backend: Firebase (Auth, Firestore, Cloud Functions, Messaging, Analytics)
  - Code generation: `build_runner`

- Python Cloud Functions (`py_quill`)
  - Firebase Functions (Python) for APIs and a Flask-based SEO web layer
  - Flask + Jinja templates for topic pages and search
  - Agents/tools for content workflows in `py_quill/agents/` and services under `py_quill/services/`

## 2. Core directives

- Make correct, verifiable, minimal changes.
- Tests are mandatory for changed behavior.
- Do not run the Flutter app (`flutter run`) for verification.

### 2.1 Testing as primary verification

- Always add/update tests for modified code.
- Target near 100% coverage for newly added code.
- Flutter: use `mocktail`; mock repositories/services rather than notifiers; assert rendered UI states.
- Python: use `pytest` and Flask test client; mock `services.search`/`services.firestore` where needed.

### 2.2 Code style/formatting

- Flutter: run `dart format .` and `flutter analyze` before submitting.
- Python: keep names clear, functions small, docstrings concise; match existing style in `py_quill`.

### 2.3 Analytics and error reporting

- Flutter: error-like analytics events must also log a Crashlytics non-fatal via `AnalyticsService`; tests should verify both.
- Python: use Cloud Logging (do not call Flutter Analytics/Crashlytics from Python).

## 3. Environment setup

### 3.1 Jules

Jules should run the jules_setup.sh script to initialize the development environment. This script will install the necessary dependencies such as flutter.

### 3.2 All other environments/agents

For all other agents, the environments is already set up for you. There is no need for any setup or dependency installation.

## 3. Commands (run from repo root)

Use Dart/Flutter commands only for the Flutter app. Do not use Flutter/Dart commands for the Python codebase. For Python, use the pytest commands specified below.

### 3.1 Flutter (Dart only)

1) Install deps
```bash
flutter pub get
```

2) Generate code (when provider files change)
```bash
dart run build_runner build --delete-conflicting-outputs
```

3) Run tests
```bash
flutter test
```

4) Analyze
```bash
flutter analyze
```

5) Format
```bash
dart format .
```

### 3.2 Python Cloud Functions (`py_quill`)

1) Install deps
```bash
pip install -r py_quill/requirements.txt
```

2) Run unit tests
```bash
python -m pytest py_quill
# or
pytest py_quill
```

3) Coverage (optional)
```bash
python -m pytest py_quill --cov=py_quill --cov-report=term-missing
# or
pytest py_quill --cov=py_quill --cov-report=term-missing
```

## 4. Architecture

### 4.1 Flutter

- Source: `lib/src/`
- Features: `lib/src/features/...`
- Common widgets: `lib/src/common_widgets/`
- Core services/providers: `lib/src/core/`, `lib/src/providers/`
- Routing: `lib/src/config/router/`
- Tests mirror `lib/` under `test/`

### 4.2 Python Cloud Functions (`py_quill`)

- Entry point: `py_quill/main.py` (exports HTTP and background functions)
- Web layer: `py_quill/functions/web_fns.py`
  - Flask app adapted to Firebase via `@https_fn.on_request` (`web_search_page`).
  - Blueprint routes:
    - `GET /jokes/<topic>`: SEO page with setup image/text visible; punchline revealed via `<details><summary>`.
    - `GET /sitemap.xml`: sitemap of topic pages from a hard-coded list in `web_fns.py`.
    - `GET /search`: simple search page retained for tests/compatibility.
  - Templates under `py_quill/web/templates/`:
    - `base.html`: canonical link, OpenGraph/Twitter meta, responsive layout.
    - `topic.html`: JSON-LD (`FAQPage`) with each joke as Question/Answer; accessible reveal; lazy images with width/height.
  - Caching headers on HTML: `Cache-Control`, `ETag`, `Last-Modified`.
  - Prefer static CSS/JS served from Firebase Hosting/CDN.
- Services: `py_quill/services/` (Firestore, Search, Storage, LLM/image clients)
- Data models: `py_quill/common/models.py`
- Agents: `py_quill/agents/` (content generation/evaluation leveraging Vertex/Anthropic)

### 4.3 Hosting rewrites and URLs

- Configure Firebase Hosting rewrites so:
  - `/jokes/**` and `/sitemap.xml` → Python HTTPS Function (Flask adapter).
  - Static assets served via Hosting/CDN.
- Canonical topic URLs avoid query params; use `?page=N` for pagination hints.

## 5. Testing guidelines

### 5.1 Flutter

- Mock repositories/services at the edges; let providers resolve naturally.
- Test realistic widget behavior (loading or content) rather than internal states.
- No test-only branches in production code.

### 5.2 Python (`py_quill`)

- Use Flask test client; verify:
  - Canonical and social tags (base template)
  - JSON-LD script of type `FAQPage`
  - `<details><summary>` punchline reveal markup
  - Image attributes and `loading="lazy"`
  - Caching headers on responses

## 6. Deployment notes

- Python functions exported in `py_quill/main.py`; Flask served via `web_search_page`.
- Keep timeouts/memory reasonable; batch Firestore reads in services where possible.

## 7. Conventions

- Naming: meaningful, non-abbreviated; functions as verbs, variables as nouns.
- Control flow: early returns; explicit error handling; avoid deep nesting.
- Comments: explain “why,” not “how.”
- No TODO comments in production; implement or remove.

## 8. Quick checklists

- Flutter change:
  - [ ] Tests under `test/`
  - [ ] `dart format .`
  - [ ] `flutter analyze`
  - [ ] `flutter test`

- Python change:
  - [ ] Tests under `py_quill/**/_test.py`
  - [ ] `pip install -r py_quill/requirements.txt`
  - [ ] `pytest -q`
  - [ ] Verify headers/SEO where relevant
