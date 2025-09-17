import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockAppUser extends Mock implements AppUser {}

void main() {
  group('FeedbackServiceImpl', () {
    late MockFeedbackRepository mockRepository;
    late MockAnalyticsService mockAnalyticsService;
    late FeedbackServiceImpl service;

    setUp(() {
      mockRepository = MockFeedbackRepository();
      mockAnalyticsService = MockAnalyticsService();
      service = FeedbackServiceImpl(
        feedbackRepository: mockRepository,
        analyticsService: mockAnalyticsService,
      );

      when(
        () => mockRepository.submitFeedback(any(), any()),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logFeedbackSubmitted(),
      ).thenAnswer((_) async {});
    });

    test(
      'submitFeedback calls repository and analytics service with user ID',
      () async {
        const feedbackText = 'Great app! Love the jokes.';
        final mockUser = MockAppUser();
        when(() => mockUser.id).thenReturn('user123');

        await service.submitFeedback(feedbackText, mockUser);

        verify(
          () => mockRepository.submitFeedback(feedbackText, 'user123'),
        ).called(1);
        verify(() => mockAnalyticsService.logFeedbackSubmitted()).called(1);
      },
    );

    test('submitFeedback handles null user with anonymous ID', () async {
      const feedbackText = 'Great app! Love the jokes.';

      await service.submitFeedback(feedbackText, null);

      verify(
        () => mockRepository.submitFeedback(feedbackText, 'anonymous'),
      ).called(1);
      verify(() => mockAnalyticsService.logFeedbackSubmitted()).called(1);
    });

    test('submitFeedback handles empty feedback', () async {
      const feedbackText = '';
      final mockUser = MockAppUser();
      when(() => mockUser.id).thenReturn('user123');

      await service.submitFeedback(feedbackText, mockUser);

      // Repository should handle empty text, analytics still called
      verify(
        () => mockRepository.submitFeedback(feedbackText, 'user123'),
      ).called(1);
      verify(() => mockAnalyticsService.logFeedbackSubmitted()).called(1);
    });

    test('submitFeedback handles whitespace-only feedback', () async {
      const feedbackText = '   ';
      final mockUser = MockAppUser();
      when(() => mockUser.id).thenReturn('user123');

      await service.submitFeedback(feedbackText, mockUser);

      verify(
        () => mockRepository.submitFeedback(feedbackText, 'user123'),
      ).called(1);
      verify(() => mockAnalyticsService.logFeedbackSubmitted()).called(1);
    });

    test('addConversationMessage calls repository', () async {
      const docId = 'doc123';
      const text = 'Thank you for your feedback!';
      const speaker = 'ADMIN';

      when(
        () => mockRepository.addConversationMessage(any(), any(), any()),
      ).thenAnswer((_) async {});

      await service.addConversationMessage(docId, text, speaker);

      verify(
        () => mockRepository.addConversationMessage(docId, text, speaker),
      ).called(1);
    });
  });
}
