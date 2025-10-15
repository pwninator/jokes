# Snickerdoodle Jokes App: SPECS.md

## 1. Overview

The Snickerdoodle Jokes app is a mobile application that delivers a curated feed of illustrated jokes to users. It leverages AI to generate and illustrate jokes, providing a unique and engaging user experience. The app also includes features for user feedback, sharing, and content moderation.

## 2. Tech Stack

- **Frontend**: Flutter/Dart
- **Backend**: Python, Firebase Cloud Functions
- **Database**: Firestore
- **Authentication**: Firebase Authentication
- **Hosting**: Firebase Hosting
- **Storage**: Firebase Cloud Storage
- **Analytics**: Firebase Analytics
- **Performance**: Firebase Performance Monitoring
- **Crash Reporting**: Firebase Crashlytics
- **External Services**:
  - Google AI (for LLM and image generation)
  - OpenAI (for LLM)
  - Anthropic (for LLM)
- **Local Storage**: Drift (on device)

## 3. System Architecture

The Snickerdoodle Jokes app is a client-server application with a Flutter frontend and a Python backend hosted on Firebase Cloud Functions.

- **Client (Flutter App)**: The mobile app is responsible for the user interface and user experience. It communicates with Firebase services for data, authentication, and other backend functionality.
- **Firebase**: Acts as the Backend-as-a-Service (BaaS) provider.
  - **Firestore**: The primary database for storing joke content, user data, and feedback.
  - **Firebase Authentication**: Manages user sign-up and sign-in.
  - **Cloud Storage**: Stores generated images for the jokes.
  - **Cloud Functions**: Hosts the Python backend logic.
- **Backend (Python Cloud Functions)**: A collection of serverless functions that perform various tasks, including:
  - Generating jokes using LLMs.
  - Generating images based on joke content.
  - Processing user feedback.
  - Performing administrative tasks.
- **External Services**: The backend communicates with external AI services (Google, OpenAI, Anthropic) to generate joke and image content.

The typical data flow is as follows:
1. The Flutter app requests a joke from Firestore.
2. If a new joke needs to be generated, a Cloud Function is triggered.
3. The Cloud Function calls an external LLM to generate a joke, then an image generation service to create an illustration.
4. The generated joke and image URL are saved to Firestore and Cloud Storage, respectively.
5. The Flutter app listens for real-time updates from Firestore and displays the new joke to the user.

## 4. Frontend (Flutter App)

### 4.1. Directory Structure

- `/lib`: The root directory for the Flutter app's Dart code.
  - `/src`: Contains the main source code, organized by feature and layer.
    - `/common_widgets`: Reusable widgets shared across multiple features.
    - `/config`: App-level configuration, such as themes and routing.
    - `/core`: Core application logic, including data models, repositories, and providers.
    - `/data`: Data access layer, responsible for interacting with data sources like Firestore and local storage.
    - `/features`: Contains the UI and business logic for each distinct feature of the app (e.g., joke feed, admin panel).
    - `/providers`: Riverpod providers for state management.
    - `/startup`: Logic for initializing the app on startup.
    - `/utils`: Utility functions and helper classes.

### 4.2. Major Components

- **Data Repositories**: A set of classes responsible for fetching and storing data from various sources (Firestore, local storage). They abstract the data layer from the rest of the app.
- **Settings**: Manages user-specific settings and preferences.
- **Notifications**: Handles local and push notifications.
- **Joke Data Sources**: Provides a unified interface for accessing joke data, whether it's from the network or a local cache.
- **Analytics**: A wrapper around Firebase Analytics to provide a consistent way of tracking events throughout the app.
- **Performance**: A wrapper around Firebase Performance Monitoring to provide a consistent way of tracking performance traces throughout the app.

### 4.3. Screens & Features

#### Admin

- **User Analytics Screen**:
  - **Purpose**: To provide administrators with a visual representation of user activity over time.
  - **Behavior**:
    - The screen fetches and displays a histogram of user login data from the `usersLoginHistogramProvider`.
    - It shows a loading spinner while data is being fetched and an error message if the fetch fails.
    - The primary visualization is a bar chart titled "Daily Active Users (Last Login)".
    - Each bar represents a day, and the bar's total height indicates the number of active users on that day.
    - The bars are segmented into different colored stacks. Each color corresponds to a "bucket" of user engagement, explained in a legend on the screen.
    - The chart is horizontally scrollable to accommodate long date ranges.
    - Tapping on a bar reveals a detailed tooltip showing the specific user counts for each engagement bucket for that day.
    - Below the main chart, it also displays a `UserJokesChart`, which shows a histogram of jokes created by users.
  - *File*: `lib/src/features/admin/presentation/users_analytics_screen.dart`
- **Joke Management Screen**:
  - **Purpose**: To allow administrators to search, filter, and manage all jokes in the system.
  - **Behavior**:
    - The screen displays a list of jokes, fetched from the `adminJokesLiveProvider`. It supports infinite scrolling to load more jokes as the user scrolls down.
    - **Search**: A search bar allows admins to search for jokes by keyword. The search is triggered on submission.
    - **Filtering**: Admins can filter the joke list using several filter chips:
      - **State**: Opens a dialog to filter jokes by their status (e.g., `published`, `draft`).
      - **Popular**: Toggles a filter to show only popular jokes.
    - **Joke List**: The main content area is a list of `JokeCard` widgets in "admin mode." Each card displays the joke and additional admin-specific information and controls (e.g., rating buttons, stats).
    - **Add Joke**: A floating action button allows admins to navigate to the `JokeEditorScreen` to create a new joke.
    - **Empty State**: If no jokes are found that match the current filters, a message is displayed to the user, guiding them on what to do next.
    - **Loading/Error States**: The screen displays a loading indicator while fetching jokes and an error message if the fetch fails.
  - *File*: `lib/src/features/admin/presentation/joke_management_screen.dart`
- **Joke Editor Screen**:
  - **Purpose**: To allow administrators to create new jokes or edit existing ones.
  - **Behavior**:
    - The screen has two modes: "create" and "edit," determined by whether a `jokeId` is provided.
    - **Create Mode**:
      - Displays empty text fields for "Setup" and "Punchline."
      - A "Save Joke" button validates the form and calls a cloud function (`createJokeWithResponse`) to create a new joke.
      - On successful creation, it shows a success message and clears the form.
    - **Edit Mode**:
      - Fetches the joke data based on the `jokeId`.
      - Populates the "Setup" and "Punchline" fields with the existing joke's text.
      - Displays additional fields for "Setup Image Description" and "Punchline Image Description."
      - Shows carousels of available images for both the setup and punchline, allowing the admin to select the desired image.
      - A "Update Joke" button validates the form and updates the joke directly in Firestore.
      - On successful update, it shows a success message and navigates back to the previous screen.
    - **Validation**: Both the setup and punchline fields are required. Image descriptions have a minimum length if they are not empty.
    - **Loading/Error States**: The screen shows loading indicators while fetching joke data (in edit mode) or saving data. It also displays error messages if any of these operations fail.
  - *File*: `lib/src/features/admin/presentation/joke_editor_screen.dart`
- **Joke Creator Screen**:
  - **Purpose**: To provide a UI for administrators to generate jokes using AI based on a set of instructions.
  - **Behavior**:
    - The screen contains a large text field where an admin can input detailed instructions for joke generation and critique.
    - A "Generate" button validates the instructions (must be at least 10 characters) and triggers the `critiqueJokes` cloud function.
    - While the function is running, the button is disabled, and a loading indicator is shown.
    - When the generation is complete, the results are displayed in a card at the bottom of the screen.
    - The results card indicates success or failure and shows the raw data returned by the cloud function.
    - A snackbar (a temporary message) is displayed at the bottom of the screen to confirm whether the operation was successful or to show an error message.
  - *File*: `lib/src/features/admin/presentation/joke_creator_screen.dart`
- **Joke Scheduler Screen**:
  - **Purpose**: To allow administrators to organize jokes into schedules and visualize their publication dates on a monthly basis.
  - **Behavior**:
    - The screen features a dropdown menu at the top to select an existing joke schedule. It also has an "Add" button to open a dialog for creating a new schedule.
    - When a schedule is selected from the dropdown, the screen displays a vertical list of monthly "batches" (`JokeScheduleBatchWidget`).
    - Each batch card represents a month and likely contains the jokes scheduled for that period.
    - Upon loading the batches for a schedule, the list automatically scrolls to the card corresponding to the current month, making it easy for admins to see the current schedule.
    - The screen handles various states:
      - A loading indicator is shown while fetching the list of schedules or the data for a selected schedule.
      - An empty state message is displayed if no schedule is selected.
      - An error message is shown if there's a problem loading the schedules.
  - *File*: `lib/src/features/admin/presentation/joke_scheduler_screen.dart`
- **Joke Categories Screen**:
  - **Purpose**: To display all joke categories to administrators in a responsive grid.
  - **Behavior**:
    - The screen fetches the list of all joke categories from the `jokeCategoriesProvider`.
    - It displays the categories in a `MasonryGridView`, which is a type of staggered grid.
    - The number of columns in the grid is dynamically calculated based on the available screen width, ensuring the layout is responsive and looks good on different screen sizes.
    - Each category is represented by a `JokeCategoryTile` widget.
    - Tapping on a category tile navigates the administrator to the `JokeCategoryEditorScreen` for that specific category, passing the `categoryId` as a parameter.
    - **Loading/Error States**: The screen shows a loading indicator while fetching categories and an error message if the fetch fails.
  - *File*: `lib/src/features/admin/presentation/joke_categories_screen.dart`
- **Joke Category Editor Screen**:
  - **Purpose**: To allow administrators to edit the details of a specific joke category, including its state, image, and description.
  - **Behavior**:
    - The screen fetches the data for a single category based on the `categoryId` passed to it.
    - It uses a `StateNotifierProvider` (`jokeCategoryEditorProvider`) to manage the state of the category being edited in the UI, allowing for local changes before saving.
    - **UI Components**:
      - Displays the category's `displayName` and `jokeDescriptionQuery` as non-editable text.
      - A dropdown menu allows the admin to change the category's `state` (e.g., `active`, `inactive`).
      - A multi-line text field allows editing the `imageDescription`.
      - An `ImageSelectorCarousel` displays available images for the category and allows the admin to select one.
    - **Actions**:
      - An "Update Category" button saves the changes made in the editor to Firestore via the `jokeCategoryRepositoryProvider`.
      - A `HoldableButton` (a button that must be held down to activate) allows the admin to delete the category.
    - After updating or deleting, the screen navigates back.
    - **Loading/Error States**: The screen shows a loading indicator while fetching the initial category data and an error message if it fails.
  - *File*: `lib/src/features/admin/presentation/joke_category_editor_screen.dart`
- **Joke Feedback Screen**:
  - **Purpose**: To provide administrators with a list of all user-submitted feedback threads.
  - **Behavior**:
    - The screen fetches and displays a list of all feedback entries from the `allFeedbackProvider`.
    - Each item in the list represents a feedback thread and displays:
      - An icon that indicates the status of the thread (e.g., read/unread, last message by user/admin).
        - A solid `Icons.feedback` icon indicates an unread message.
        - An outlined `Icons.feedback_outlined` icon indicates a read message.
        - The icon color indicates who sent the last message (yellow for user, green for admin).
      - The text of the latest user message in the conversation.
      - Detailed usage statistics for the user who submitted the feedback, including their first/last login dates, and the number of jokes they've viewed, saved, and shared.
    - Tapping on a feedback item navigates the admin to the `FeedbackConversationScreen` for that specific thread.
    - **Loading/Error States**: The screen shows a loading indicator while fetching the feedback list and an error message if the fetch fails.
  - *File*: `lib/src/features/admin/presentation/joke_feedback_screen.dart`
- **Deep Research Screen**:
  - **Purpose**: To provide a powerful, multi-step workflow for administrators to generate a large number of high-quality, topic-specific jokes using an external LLM.
  - **Behavior**:
    - **Step 1: Prompt Generation**:
      - The admin enters a "joke topic" (e.g., "cats", "computers").
      - They click "Create prompt". The app then:
        - Searches for existing jokes related to the topic to use as examples.
        - Composes a detailed prompt for an LLM (like GPT or Gemini) using a predefined template. This prompt includes the topic, criteria for good jokes, and the examples found.
      - The generated prompt is displayed on the screen and can be copied to the clipboard.
    - **Step 2: LLM Interaction (Manual Step)**:
      - The admin manually pastes the generated prompt into an external LLM interface.
      - The admin then uses a separate, predefined "response prompt" (which can also be copied from the screen) to instruct the LLM to format the generated jokes correctly (e.g., `setup###punchline`).
    - **Step 3: Joke Submission**:
      - The admin pastes the formatted joke list from the LLM into a "Paste LLM response here" text field on the screen.
      - Clicking "Submit" opens a confirmation dialog that lists the parsed jokes.
      - Confirming the dialog triggers a batch process that calls the `createJokeWithResponse` cloud function for each joke, adding them to the database.
    - **State Management**: The screen manages loading and error states for both the prompt creation and joke submission steps.
  - *File*: `lib/src/features/admin/presentation/deep_research_screen.dart`
- **Joke Admin Screen**:
  - **Purpose**: To serve as the main dashboard and navigation hub for all administrative features.
  - **Behavior**:
    - The screen displays a list of cards, each representing a different admin tool or section.
    - Each card has a title, a subtitle describing its purpose, and an icon.
    - Tapping on a card navigates the user to the corresponding admin screen (e.g., tapping the "Feedback" card goes to the `JokeFeedbackScreen`).
    - **Dynamic Badge**: The "Feedback" list item displays a red badge with a count of unread feedback messages, providing an at-a-glance notification for admins. The count is derived from the `allFeedbackProvider`.
    - **Navigation Links To**:
      - Feedback
      - Book Creator
      - Users (Analytics)
      - Joke Categories
      - Joke Creator
      - Joke Management
      - Joke Scheduler
      - Deep Research
  - *File*: `lib/src/features/admin/presentation/joke_admin_screen.dart`

#### Auth

- **Authentication**: The app allows anonymous browsing for most features. User authentication is not required for viewing jokes.
- **Sign-in Flow**: There is no dedicated sign-in screen. The sign-in process is likely initiated through a button (e.g., in the settings screen) that uses a service like Google Sign-In to present a native sign-in UI.
- **Route Guarding**: The app uses a route guard (`AuthGuard`) to protect admin-only routes. If a non-admin user attempts to access an admin route, they are redirected to the main joke feed.
  - *File*: `lib/src/config/router/route_guards.dart`

#### Book Creator

- **Book Creator Screen**: This screen allows for the creation of "joke books," which are likely collections of jokes.
  - *File*: `lib/src/features/book_creator/book_creator_screen.dart`
- **Joke Selector Screen**: A UI for selecting which jokes to include in a joke book.
  - *File*: `lib/src/features/book_creator/joke_selector_screen.dart`

#### Feedback

- **User Feedback Screen**: This screen allows users to submit feedback about the app or specific jokes.
  - *File*: `lib/src/features/feedback/presentation/user_feedback_screen.dart`
- **Feedback Conversation Screen**: A screen for viewing and participating in a conversation thread related to a piece of feedback. This screen can be accessed by both users and admins.
  - *File*: `lib/src/features/feedback/presentation/feedback_conversation_screen.dart`

#### Jokes

- **Daily Jokes Screen**: This is the main screen of the app, displaying a feed of the latest jokes.
  - *File*: `lib/src/features/jokes/presentation/daily_jokes_screen.dart`
- **Saved Jokes Screen**: This screen displays a list of jokes that the user has saved for later viewing.
  - *File*: `lib/src/features/jokes/presentation/saved_jokes_screen.dart`

#### Search

- **Discover Screen**: A screen for browsing and discovering new content, likely through categories or trending jokes.
  - *File*: `lib/src/features/search/presentation/discover_screen.dart`
- **Search Screen**: Provides a UI for users to actively search for specific jokes.
  - *File*: `lib/src/features/search/presentation/search_screen.dart`

#### Settings

- **User Settings Screen**: This screen allows users to manage their account settings and preferences. This is also where users can likely initiate the sign-in process.
  - *File*: `lib/src/features/settings/presentation/user_settings_screen.dart`

### 4.4. Analytics

The app uses Firebase Analytics to track user engagement and app usage. Key events to be tracked include:
- Screen views
- Joke views
- Joke shares
- Joke saves
- User sign-ups
- Searches performed

### 4.5. Performance

The app uses Firebase Performance Monitoring to track app performance. Key traces to be monitored include:
- App startup time
- Joke feed load time
- Image load time
- Search query response time

### 4.6. External Service Integrations

- **Firebase**: The frontend integrates with several Firebase services:
  - **Analytics**: For tracking user engagement.
  - **Performance Monitoring**: For monitoring app performance.
  - **Crashlytics**: For crash reporting.
  - **Authentication**: For user sign-in and sign-up, including Google Sign-In.
- **Drift**: For on-device local storage and caching.

## 5. Backend (Python)

### 5.1. Directory Structure

- `/py_quill`: The root directory for the Python backend.
  - `/agents`: Contains the ADK agents.
  - `/common`: Shared utilities and data models.
  - `/functions`: The source code for the Firebase Cloud Functions.
  - `/services`: Clients for interacting with external services (e.g., LLMs, Google APIs).
  - `/web`: Flask app for web-based search.

### 5.2. Major Components

- **LLM Clients**: A set of classes for interacting with different Large Language Models (Google, OpenAI, Anthropic).
- **Image Generation**: Logic for generating images based on joke content, using services like Google's Imagen.
- **Firestore Models**: Data models that represent the structure of documents in Firestore.
- **Cloud Function Triggers**: The entry points for the cloud functions, which can be HTTP requests, Firestore events, or other triggers.

### 5.3. Cloud Functions

- **Admin Functions**:
  - **`set_user_role(req)`**:
    - **Purpose**: To assign a custom role to a user, which is used for authorization (e.g., granting admin privileges).
    - **Trigger**: HTTPS Request (`on_request`).
    - **Inputs**:
      - `user_id`: The ID of the user to modify.
      - `role`: The role to assign (e.g., "admin").
    - **Behavior**:
      - It takes a `user_id` and a `role` as input from the request.
      - It uses the Firebase Admin SDK's `set_custom_user_claims` method to attach the specified role to the target user's authentication token.
      - **Note**: The code to verify if the *requesting* user is an admin is currently commented out, meaning this function is effectively open to be called by any user.
    - **Outputs**: Returns a success message with the user ID and the role that was set, or an error message if the operation fails.
  - *File*: `py_quill/functions/admin_fns.py`
- **Analytics Functions**:
  - **`usage(req)`**:
    - **Purpose**: To track user activity and update their usage statistics in Firestore. This function is called by the client app periodically to report metrics.
    - **Trigger**: HTTPS Request (`on_request`).
    - **Inputs (from authenticated user)**:
      - `num_days_used` (optional): The number of distinct days the client app has been used.
      - `num_saved` (optional): The total number of jokes the user has saved.
      - `num_viewed` (optional): The total number of jokes the user has viewed.
      - `num_shared` (optional): The total number of jokes the user has shared.
      - `requested_review` (optional): A boolean indicating if the user has been prompted for an app review.
    - **Behavior**:
      - It requires an authenticated user ID.
      - It calls `firestore_service.upsert_joke_user_usage` to update the user's usage document in Firestore.
      - This service function updates the `lastLoginAt` timestamp, increments a server-side daily usage counter, and stores the latest client-reported metrics (`num_saved`, `num_viewed`, etc.).
    - **Outputs**: Returns a success message with the user ID and the server-calculated number of distinct days used.
  - *File*: `py_quill/functions/analytics_fns.py`
- **Book Functions**: Functions for managing joke books.
  - *File*: `py_quill/functions/book_fns.py`
- **Character Functions**: Functions for managing characters that may be used in jokes or stories.
  - *File*: `py_quill/functions/character_fns.py`
- **Joke Book Functions**: Functions specifically for managing the contents and creation of joke books. This is referenced in `firebase.json` for the `/joke-book/**` route.
  - *File*: `py_quill/functions/joke_book_fns.py`
- **Joke Functions**:
  - **`create_joke(req)`**:
    - **Purpose**: To create a new joke document in Firestore.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `setup_text`, `punchline_text`, `admin_owned` (optional), `populate_joke` (optional).
    - **Behavior**:
      - Creates a `PunnyJoke` object from the provided text.
      - Assigns ownership to "ADMIN" if `admin_owned` is true, otherwise to the authenticated user's ID.
      - Sets the initial state to `DRAFT`.
      - If `populate_joke` is true, it asynchronously calls the `_populate_joke_internal` function to generate images and other metadata for the joke.
    - **Outputs**: The newly created joke data.
  - **`search_jokes(req)`**:
    - **Purpose**: To find jokes based on a text query using vector search.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `search_query`, `max_results`, `match_mode` ('TIGHT' or 'LOOSE'), `public_only` (boolean).
    - **Behavior**:
      - Calls the `search.search_jokes` service to perform a vector similarity search against the joke embeddings in the database.
      - Can filter for only public jokes based on the `public_only` flag.
    - **Outputs**: A list of joke IDs and their vector distance from the search query.
  - **`populate_joke(req)`**:
    - **Purpose**: To enrich a joke with AI-generated content, including images and metadata.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `joke_id`, `image_quality`, `images_only` (boolean), `overwrite` (boolean).
    - **Behavior**:
      - Fetches the specified joke from Firestore.
      - If `images_only` is true, it only generates new images for the existing descriptions.
      - Otherwise, it uses the "joke populator agent" to generate a full set of data, including pun analysis, image descriptions, and image URLs.
      - If the joke's state is `DRAFT`, it's updated to `UNREVIEWED`.
    - **Outputs**: The updated joke data.
  - **`modify_joke_image(req)`**:
    - **Purpose**: To modify a joke's existing images based on text instructions.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `joke_id`, `setup_instruction` (optional), `punchline_instruction` (optional).
    - **Behavior**: Calls the `image_generation.modify_image` service to alter the setup and/or punchline image and saves the updated image URL to the joke.
    - **Outputs**: The updated joke data.
  - **`critique_jokes(req)`**:
    - **Purpose**: To use an AI agent to critique jokes based on a set of instructions.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `instructions`, `jokes` (a list of joke texts).
    - **Behavior**: Runs the "joke critic agent" with the provided instructions and jokes.
    - **Outputs**: The critique data generated by the agent.
  - **`send_daily_joke_scheduler(event)` / `send_daily_joke_http(req)`**:
    - **Purpose**: To send daily joke notifications to users subscribed to FCM topics.
    - **Trigger**: Scheduled event (runs every hour) or HTTPS Request.
    - **Behavior**:
      - Iterates through all joke schedules in the database.
      - For each schedule, determines the correct joke for the current date (in UTC-12).
      - Sends a push notification containing the joke to the appropriate FCM topic (e.g., `daily_jokes_09c`). The topic is constructed based on the schedule name, the hour, and a suffix indicating if it's for the "current" or "next" date relative to UTC-12.
  - **`upscale_joke(req)`**:
    - **Purpose**: To upscale a joke's images to a higher resolution.
    - **Trigger**: HTTPS Request.
    - **Inputs**: `joke_id`, `mime_type` (optional), `compression_quality` (optional).
    - **Behavior**: Calls the `joke_operations.upscale_joke` operation to perform the upscaling.
    - **Outputs**: The updated joke data with the new upscaled image URLs.
  - **`on_joke_write(event)`**:
    - **Purpose**: To maintain data consistency when a joke document is written to Firestore.
    - **Trigger**: Firestore `on_document_written`.
    - **Behavior**:
      - **Embedding Update**: If the joke's text has changed or if it's a new joke, it calculates a new vector embedding for the joke and saves it.
      - **Popularity Score Update**: It recalculates the joke's `popularity_score` based on its saves and shares, and updates the field if it's incorrect.
      - **Search Subcollection Sync**: It syncs the latest embedding, state, public timestamp, and popularity score to a dedicated subcollection (`/search/search`) to optimize search queries.
  - **`on_joke_category_write(event)`**:
    - **Purpose**: To automatically generate a new representative image for a joke category when its description changes.
    - **Trigger**: Firestore `on_document_written`.
    - **Behavior**:
      - When a `joke_categories` document is created or its `image_description` field changes, this function triggers.
      - It calls the `image_generation.generate_pun_image` service to create a new image based on the new description.
      - It then updates the category document, setting the `image_url` to the new image's URL and appending the new URL to the `all_image_urls` list.
  - *File*: `py_quill/functions/joke_fns.py`
- **Story Prompt Functions**: Functions related to generating or managing story prompts.
  - *File*: `py_quill/functions/story_prompt_fns.py`
- **User Functions**: Functions for managing user data and accounts.
  - *File*: `py_quill/functions/user_fns.py`
- **Utility Functions**: General-purpose utility functions used by other cloud functions.
  - *File*: `py_quill/functions/util_fns.py`
- **Web Functions**: Functions that serve web content, such as the search page referenced in `firebase.json`.
  - *File*: `py_quill/functions/web_fns.py`

### 5.4. Agents (ADK)

The backend uses agents built with the ADK (Agent Development Kit) to perform complex, multi-step tasks.

- **Jokes Agent**: The primary agent for generating and managing jokes.
  - *File*: `py_quill/agents/jokes/jokes_agent.py`
- **Categorizer Agent**: An agent responsible for categorizing jokes.
  - *File*: `py_quill/agents/jokes/categorizer_agent.py`
- **Punny Joke Agents**: A specialized agent for creating puns.
  - *File*: `py_quill/agents/jokes/punny_joke_agents.py`
- **Updater Agent**: An agent that likely handles updates to joke data or content.
  - *File*: `py_quill/agents/jokes/updater_agent.py`

### 5.5. External Service Integrations

- **Firebase**: The backend relies on Firebase for core infrastructure:
  - **Firestore**: The primary database.
  - **Cloud Storage**: For storing generated images.
  - **Cloud Functions**: The serverless execution environment for the backend code.
- **Google AI (Vertex AI)**: Used for LLM (e.g., Gemini) and image generation (Imagen) models.
- **OpenAI**: Used for LLM access (e.g., GPT models).
- **Anthropic**: Used for LLM access (e.g., Claude models).

## 6. User Journeys

### New User Journey

1.  **Launch App**: The user opens the app for the first time.
2.  **View Daily Jokes**: The user is presented with the main joke feed (`DailyJokesScreen`) and can scroll through the latest jokes.
3.  **Save a Joke**: The user finds a joke they like and saves it to their favorites (`SavedJokesScreen`).
4.  **Discover Jokes**: The user navigates to the discover tab (`DiscoverScreen`) to browse jokes by category.
5.  **Search for a Joke**: The user uses the search functionality (`SearchScreen`) to find a specific joke.
6.  **Sign Up**: The user decides to create an account through the settings screen (`UserSettingsScreen`) to sync their saved jokes and preferences.

### Admin Journey

1.  **Log In**: An admin user logs in with their credentials.
2.  **Access Admin Panel**: The admin navigates to the admin section of the app (`JokeAdminScreen`).
3.  **Review User Analytics**: The admin checks the user analytics dashboard (`UsersAnalyticsScreen`) to see user engagement metrics.
4.  **Manage Jokes**: The admin uses the joke management screen (`JokeManagementScreen`) to review, edit (`JokeEditorScreen`), or create (`JokeCreatorScreen`) new jokes.
5.  **Schedule Jokes**: The admin schedules jokes to be published at a future date (`JokeSchedulerScreen`).
6.  **Review Feedback**: The admin reviews user-submitted feedback (`JokeFeedbackScreen`).
