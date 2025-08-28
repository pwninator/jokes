# AGENTS.md: Instructions for AI Agents

This document provides essential information and guidelines for AI agents working on the `snickerdoodle` codebase. Adhering to these instructions is crucial for maintaining code quality and consistency.

## 1. Project Overview

This is a Flutter application (`snickerdoodle`) for Android and iOS that displays jokes. It is built with the following technologies:

- **Framework**: Flutter (Dart)
- **State Management**: `flutter_riverpod`
- **Navigation**: `go_router`
- **Backend**: Firebase (Authentication, Firestore, Cloud Functions, Messaging, Analytics)
- **Code Generation**: `build_runner` is used, primarily for Riverpod providers.

## 2. Core Agent Directives

Your primary goal is to make correct and verifiable code changes.

### **Testing is Your Primary Verification Method**

- **You MUST NOT run the application using `flutter run`.** You cannot interact with the UI, so running the app is not a valid verification strategy.
- Your changes **must** be accompanied by new or updated tests.
- **Aim for near 100% test coverage** for any new or modified code. Use the existing tests in the `test/` directory as a reference for style and structure.
- Use mocks where appropriate. The project uses the `mocktail` package for mocking dependencies.

### **Code Style and Formatting**

- Before submitting, always ensure your code is formatted and passes all analysis checks.
- Run `dart format .` and `flutter analyze` to catch any issues.

## 3. Essential Commands

Here are the commands you will need to work on this project. Run them from the root directory.

1.  **Install/Update Dependencies:**
    ```bash
    flutter pub get
    ```

2.  **Run Code Generation:**
    *Run this command whenever you change files that require code generation (e.g., files with Riverpod providers).*
    ```bash
    dart run build_runner build --delete-conflicting-outputs
    ```

3.  **Run All Tests:**
    *This is the primary way you will verify your changes.*
    ```bash
    flutter test
    ```

4.  **Check for Code Style Issues:**
    ```bash
    flutter analyze
    ```

5.  **Format Code:**
    ```bash
    dart format .
    ```

## 4. Architecture Guide

The application follows a standard, feature-driven architecture.

- **Source Code**: All Dart code is located in `lib/src/`.
- **Features**: The `lib/src/features/` directory contains the code for distinct features of the app (e.g., `jokes`, `auth`, `settings`). When adding a new feature, create a new directory here.
- **Widgets**: Reusable widgets that are not specific to any single feature live in `lib/src/common_widgets/`.
- **Services/Providers**: Core services and providers are located in `lib/src/core/` and `lib/src/providers/`.
- **Data Models**: Data models are typically co-located with the features that use them.
- **Routing**: App navigation is managed by `go_router` and configured in `lib/src/config/router/`.
- **Tests**: The `test/` directory mirrors the `lib/` directory structure. Place your tests in the corresponding location.
