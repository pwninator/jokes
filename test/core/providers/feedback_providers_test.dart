import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  group('allFeedbackProvider', () {
    test(
      'should emit sorted feedback entries by last user message time',
      () async {
        // Arrange
        final mockRepository = MockFeedbackRepository();
        final unsortedEntries = [
          FeedbackEntry(
            id: '1',
            creationTime: DateTime(2023, 1, 1),
            conversation: [
              FeedbackConversationEntry(
                speaker: SpeakerType.user,
                text: 'Hello',
                timestamp: DateTime(2023, 1, 1, 10, 0),
              ),
            ],
            userId: 'user1',
            lastAdminViewTime: null,
            lastUserViewTime: null,
          ),
          FeedbackEntry(
            id: '2',
            creationTime: DateTime(2023, 1, 2),
            conversation: [
              FeedbackConversationEntry(
                speaker: SpeakerType.user,
                text: 'Question',
                timestamp: DateTime(2023, 1, 2, 11, 0),
              ),
            ],
            userId: 'user2',
            lastAdminViewTime: null,
            lastUserViewTime: null,
          ),
          FeedbackEntry(
            id: '3',
            creationTime: DateTime(2023, 1, 3),
            conversation: [
              FeedbackConversationEntry(
                speaker: SpeakerType.user,
                text: 'Issue',
                timestamp: DateTime(2023, 1, 1, 9, 0),
              ),
            ],
            userId: 'user3',
            lastAdminViewTime: null,
            lastUserViewTime: null,
          ),
        ];

        when(
          () => mockRepository.watchAllFeedback(),
        ).thenAnswer((_) => Stream.value(unsortedEntries));

        final container = ProviderContainer(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
          ],
        );

        // Act
        final result = await container.read(allFeedbackProvider.future);

        // Assert
        expect(result.map((e) => e.id).toList(), ['2', '1', '3']);
      },
    );
  });
}
