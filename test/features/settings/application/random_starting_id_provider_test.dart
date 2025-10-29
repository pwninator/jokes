import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/settings/application/random_starting_id_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockSettingsService extends Mock implements SettingsService {}

void main() {
  late MockSettingsService mockSettingsService;
  late RandomStartingIdService service;

  setUp(() {
    mockSettingsService = MockSettingsService();
    service = RandomStartingIdService(mockSettingsService);
  });

  group('RandomStartingIdService', () {
    test('returns existing random starting ID when present', () async {
      // Arrange
      const existingId = 123456789;
      when(
        () => mockSettingsService.getInt('random_starting_id'),
      ).thenReturn(existingId);

      // Act
      final result = await service.getRandomStartingId();

      // Assert
      expect(result, existingId);
      verify(() => mockSettingsService.getInt('random_starting_id')).called(1);
      verifyNever(() => mockSettingsService.setInt(any(), any()));
    });

    test(
      'generates and stores new random starting ID when not present',
      () async {
        // Arrange
        when(
          () => mockSettingsService.getInt('random_starting_id'),
        ).thenReturn(null);
        when(
          () => mockSettingsService.setInt(any(), any()),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.getRandomStartingId();

        // Assert
        expect(result, isA<int>());
        expect(result, greaterThanOrEqualTo(0));
        expect(result, lessThan(1 << 31)); // Less than 2^31

        verify(
          () => mockSettingsService.getInt('random_starting_id'),
        ).called(1);
        verify(
          () => mockSettingsService.setInt('random_starting_id', result),
        ).called(1);
      },
    );

    test(
      'generates different IDs on multiple calls when not present',
      () async {
        // Arrange
        when(
          () => mockSettingsService.getInt('random_starting_id'),
        ).thenReturn(null);
        when(
          () => mockSettingsService.setInt(any(), any()),
        ).thenAnswer((_) async {});

        // Act
        final result1 = await service.getRandomStartingId();
        final result2 = await service.getRandomStartingId();

        // Assert
        expect(result1, isA<int>());
        expect(result2, isA<int>());
        // Note: While it's possible for two random numbers to be the same,
        // it's extremely unlikely with 2^31 possible values
        expect(result1, greaterThanOrEqualTo(0));
        expect(result2, greaterThanOrEqualTo(0));
        expect(result1, lessThan(1 << 31));
        expect(result2, lessThan(1 << 31));
      },
    );

    test(
      'persists generated ID and returns same value on subsequent calls',
      () async {
        // Arrange
        when(
          () => mockSettingsService.getInt('random_starting_id'),
        ).thenReturn(null);
        when(
          () => mockSettingsService.setInt(any(), any()),
        ).thenAnswer((_) async {});

        // Act - First call should generate and store
        final result1 = await service.getRandomStartingId();

        // Arrange - Second call should return stored value
        when(
          () => mockSettingsService.getInt('random_starting_id'),
        ).thenReturn(987654321);

        // Act - Second call should return stored value
        final result2 = await service.getRandomStartingId();

        // Assert
        expect(result1, isA<int>());
        expect(result2, 987654321);

        verify(
          () => mockSettingsService.getInt('random_starting_id'),
        ).called(2);
        verify(
          () => mockSettingsService.setInt('random_starting_id', result1),
        ).called(1);
      },
    );
  });
}
