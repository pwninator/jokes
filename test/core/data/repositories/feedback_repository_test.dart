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
      final snapshot =
          await fakeFirestore.collection('feedback').get();
      expect(snapshot.docs.length, 1);
      final doc = snapshot.docs.first.data();
      expect(doc['user_id'], 'user1');
      expect(doc['messages'].length, 1);
      expect(doc['messages'][0]['text'], 'Test feedback');
      expect(doc['lastMessage']['text'], 'Test feedback');
    });

    test('addMessage adds a message and updates lastMessage', () async {
      final docRef = await fakeFirestore.collection('feedback').add({
        'user_id': 'user1',
        'messages': [],
      });

      final message = Message(
        text: 'New message',
        timestamp: DateTime.now(),
        isFromAdmin: true,
      );

      await repository.addMessage(docRef.id, message);

      final snapshot = await docRef.get();
      final doc = snapshot.data();
      expect(doc!['messages'].length, 1);
      expect(doc['messages'][0]['text'], 'New message');
      expect(doc['lastMessage']['text'], 'New message');
    });

    test('updateLastAdminViewTime updates the timestamp', () async {
      final docRef = await fakeFirestore.collection('feedback').add({
        'user_id': 'user1',
        'last_admin_view_time': null,
      });

      await repository.updateLastAdminViewTime(docRef.id);

      final snapshot = await docRef.get();
      expect(snapshot.data()!['last_admin_view_time'], isNotNull);
    });

    test('watchAllFeedback streams feedback entries', () async {
      await fakeFirestore.collection('feedback').add({
        'user_id': 'user1',
        'creation_time': DateTime.now(),
        'messages': [],
      });

      final stream = repository.watchAllFeedback();

      expect(
          stream,
          emits(isA<List<FeedbackEntry>>()..having(
              (list) => list.length, 'length', 1)));
    });
  });
}
