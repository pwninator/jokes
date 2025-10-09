import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';

void main() {
  group('FirestoreFeedbackRepository', () {
    late FakeFirebaseFirestore fakeFirestore;
    late FirestoreFeedbackRepository repository;

    setUp(() {
      fakeFirestore = FakeFirebaseFirestore();
      repository = FirestoreFeedbackRepository(firestore: fakeFirestore);
    });

    test('submitFeedback creates a user-scoped feedback document', () async {
      await repository.submitFeedback('Test feedback', 'user1');

      final docSnapshot = await fakeFirestore
          .collection('joke_feedback')
          .doc('user1')
          .get();
      expect(docSnapshot.exists, isTrue);
      final data = docSnapshot.data();
      expect(data, isNotNull);
      expect(data!['user_id'], 'user1');
      final conversation = data['conversation'] as List<dynamic>;
      expect(conversation.length, 1);
      expect(conversation.first['text'], 'Test feedback');
      expect(conversation.first['speaker'], 'USER');
      expect(data['lastAdminViewTime'], isNull);
    });

    test(
      'submitFeedback (unauth) creates anonymous doc without user_id',
      () async {
        await repository.submitFeedback('Anon feedback', null);

        final querySnap = await fakeFirestore.collection('joke_feedback').get();
        expect(querySnap.docs.length, 1);
        final data = querySnap.docs.first.data();
        expect(data.containsKey('user_id'), isFalse);
        final conversation = data['conversation'] as List<dynamic>;
        expect(conversation.length, 1);
        expect(conversation.first['text'], 'Anon feedback');
        expect(conversation.first['speaker'], 'USER');
      },
    );

    test('submitFeedback appends additional messages for same user', () async {
      await repository.submitFeedback('First message', 'user1');
      await repository.submitFeedback('Second message', 'user1');

      final docSnapshot = await fakeFirestore
          .collection('joke_feedback')
          .doc('user1')
          .get();
      final data = docSnapshot.data()!;
      final conversation = data['conversation'] as List<dynamic>;
      expect(conversation.length, 2);
      expect(conversation[0]['text'], 'First message');
      expect(conversation[1]['text'], 'Second message');
    });

    test('addConversationMessage appends an admin message', () async {
      final docRef = fakeFirestore.collection('joke_feedback').doc('user1');
      await docRef.set({
        'user_id': 'user1',
        'conversation': [
          {
            'speaker': SpeakerType.user.value,
            'text': 'Hi there',
            'timestamp': Timestamp.fromDate(DateTime(2023, 1, 1).toUtc()),
          },
        ],
        'lastAdminViewTime': null,
        'lastUserViewTime': null,
      });

      await repository.addConversationMessage(
        'user1',
        'New message',
        SpeakerType.admin,
      );

      final snapshot = await docRef.get();
      final doc = snapshot.data()!;
      final conversation = doc['conversation'] as List<dynamic>;
      expect(conversation.length, 2);
      expect(conversation.last['text'], 'New message');
      expect(conversation.last['speaker'], 'ADMIN');
    });

    test(
      'addConversationMessage migrates legacy feedback_text to conversation',
      () async {
        final docRef = fakeFirestore.collection('joke_feedback').doc('user1');
        await docRef.set({
          'user_id': 'user1',
          'feedback_text': 'Legacy user message',
          'creation_time': Timestamp.fromDate(DateTime(2023, 1, 1)),
          'lastAdminViewTime': null,
        });

        await repository.addConversationMessage(
          'user1',
          'Admin reply',
          SpeakerType.admin,
        );

        final snapshot = await docRef.get();
        final doc = snapshot.data()!;
        final conversation = doc['conversation'] as List<dynamic>;
        expect(conversation.length, 2);
        expect(conversation[0]['text'], 'Legacy user message');
        expect(conversation[0]['speaker'], 'USER');
        expect(conversation[1]['text'], 'Admin reply');
        expect(conversation[1]['speaker'], 'ADMIN');
        expect(doc.containsKey('feedback_text'), isFalse);
      },
    );

    test('addConversationMessage creates document when missing', () async {
      await repository.addConversationMessage(
        'user1',
        'Hello from admin',
        SpeakerType.admin,
      );

      final snapshot = await fakeFirestore
          .collection('joke_feedback')
          .doc('user1')
          .get();
      expect(snapshot.exists, isTrue);
      final doc = snapshot.data()!;
      final conversation = doc['conversation'] as List<dynamic>;
      expect(conversation.length, 1);
      expect(conversation.first['text'], 'Hello from admin');
      expect(conversation.first['speaker'], 'ADMIN');
    });

    test('updateLastAdminViewTime writes server timestamp', () async {
      final docRef = fakeFirestore.collection('joke_feedback').doc('user1');
      await docRef.set({
        'user_id': 'user1',
        'conversation': [],
        'lastAdminViewTime': null,
      });

      await repository.updateLastAdminViewTime('user1');

      final snapshot = await docRef.get();
      expect(snapshot.data()!['lastAdminViewTime'], isNotNull);
    });

    test('watchAllFeedback streams feedback entries', () async {
      await fakeFirestore.collection('joke_feedback').doc('user1').set({
        'user_id': 'user1',
        'creation_time': Timestamp.fromDate(DateTime.now()),
        'conversation': [],
        'state': 'NEW',
      });

      final stream = repository.watchAllFeedback();

      expect(
        stream,
        emits(
          isA<List<FeedbackEntry>>().having((list) => list.length, 'length', 1),
        ),
      );
    });
  });
}
