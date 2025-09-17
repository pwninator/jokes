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

    test('submitFeedback creates a new feedback document', () async {
      await repository.submitFeedback('Test feedback', 'user1');
      final snapshot = await fakeFirestore.collection('joke_feedback').get();
      expect(snapshot.docs.length, 1);
      final doc = snapshot.docs.first.data();
      expect(doc['user_id'], 'user1');
      expect(doc['conversation'].length, 1);
      expect(doc['conversation'][0]['text'], 'Test feedback');
      expect(doc['lastAdminViewTime'], isNull);
    });

    test('addConversationMessage appends an admin message', () async {
      final docRef = await fakeFirestore.collection('joke_feedback').add({
        'user_id': 'user1',
        'conversation': [],
        'lastAdminViewTime': null,
      });

      await repository.addConversationMessage(
        docRef.id,
        'New message',
        SpeakerType.admin,
      );

      final snapshot = await docRef.get();
      final doc = snapshot.data();
      expect(doc!['conversation'].length, 1);
      expect(doc['conversation'][0]['text'], 'New message');
      expect(doc['conversation'][0]['speaker'], 'ADMIN');
    });

    test(
      'addConversationMessage migrates legacy feedback_text to conversation',
      () async {
        final docRef = await fakeFirestore.collection('joke_feedback').add({
          'user_id': 'user1',
          'feedback_text': 'Legacy user message',
          'creation_time': Timestamp.fromDate(DateTime(2023, 1, 1)),
          'lastAdminViewTime': null,
        });

        await repository.addConversationMessage(
          docRef.id,
          'Admin reply',
          SpeakerType.admin,
        );

        final snapshot = await docRef.get();
        final doc = snapshot.data();
        expect(doc!['conversation'].length, 2);
        expect(doc['conversation'][0]['text'], 'Legacy user message');
        expect(doc['conversation'][0]['speaker'], 'USER');
        expect(doc['conversation'][1]['text'], 'Admin reply');
        expect(doc['conversation'][1]['speaker'], 'ADMIN');
        expect(doc['feedback_text'], isNull); // Should be removed
      },
    );

    test('updateLastAdminViewTime writes server timestamp', () async {
      final docRef = await fakeFirestore.collection('joke_feedback').add({
        'user_id': 'user1',
        'conversation': [],
        'lastAdminViewTime': null,
      });

      await repository.updateLastAdminViewTime(docRef.id);

      final snapshot = await docRef.get();
      expect(snapshot.data()!['lastAdminViewTime'], isNotNull);
    });

    test('watchAllFeedback streams feedback entries', () async {
      await fakeFirestore.collection('joke_feedback').add({
        'user_id': 'user1',
        'creation_time': DateTime.now(),
        'conversation': [],
        'state': 'NEW',
      });

      final stream = repository.watchAllFeedback();

      expect(
        stream,
        emits(
          isA<List<FeedbackEntry>>()
            ..having((list) => list.length, 'length', 1),
        ),
      );
    });
  });
}
