import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';

void main() {
  group('FeedbackConversationEntry', () {
    test('fromMap creates entry with SpeakerType enum', () {
      final testDateTime = DateTime(2025, 1, 1, 12, 0, 0);
      final map = {
        'speaker': 'USER',
        'text': 'Test message',
        'timestamp': Timestamp.fromDate(testDateTime),
      };

      final entry = FeedbackConversationEntry.fromMap(map);

      expect(entry.speaker, SpeakerType.user);
      expect(entry.text, 'Test message');
      expect(entry.timestamp, testDateTime);
    });

    test('fromMap handles ADMIN speaker', () {
      final testDateTime = DateTime(2025, 1, 1, 12, 0, 0);
      final map = {
        'speaker': 'ADMIN',
        'text': 'Admin response',
        'timestamp': Timestamp.fromDate(testDateTime),
      };

      final entry = FeedbackConversationEntry.fromMap(map);

      expect(entry.speaker, SpeakerType.admin);
      expect(entry.text, 'Admin response');
    });

    test('fromMap defaults to USER for unknown speaker', () {
      final testDateTime = DateTime(2025, 1, 1, 12, 0, 0);
      final map = {
        'speaker': 'UNKNOWN',
        'text': 'Test message',
        'timestamp': Timestamp.fromDate(testDateTime),
      };

      final entry = FeedbackConversationEntry.fromMap(map);

      expect(entry.speaker, SpeakerType.user);
    });

    test('fromMap handles missing speaker field', () {
      final testDateTime = DateTime(2025, 1, 1, 12, 0, 0);
      final map = {
        'text': 'Test message',
        'timestamp': Timestamp.fromDate(testDateTime),
      };

      final entry = FeedbackConversationEntry.fromMap(map);

      expect(entry.speaker, SpeakerType.user);
    });
  });

  group('SpeakerType', () {
    test('fromString handles valid values', () {
      expect(SpeakerType.fromString('USER'), SpeakerType.user);
      expect(SpeakerType.fromString('ADMIN'), SpeakerType.admin);
      expect(SpeakerType.fromString('user'), SpeakerType.user);
      expect(SpeakerType.fromString('admin'), SpeakerType.admin);
    });

    test('fromString defaults to user for unknown values', () {
      expect(SpeakerType.fromString('UNKNOWN'), SpeakerType.user);
      expect(SpeakerType.fromString(''), SpeakerType.user);
    });

    test('value property returns correct string', () {
      expect(SpeakerType.user.value, 'USER');
      expect(SpeakerType.admin.value, 'ADMIN');
    });
  });
}
