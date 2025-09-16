import 'package:cloud_firestore/cloud_firestore.dart';

/// Repository for handling feedback-related Firestore operations
abstract class FeedbackRepository {
  /// Submit user feedback to Firestore
  Future<void> submitFeedback(String feedbackText, String userId);

  /// Stream all feedback ordered by creation_time descending
  Stream<List<FeedbackEntry>> watchAllFeedback();

  /// Stream the count of unread (NEW) feedback items
  Stream<int> watchUnreadCount();

  /// Mark a feedback document READ
  Future<void> markFeedbackRead(String docId);
}

class FirestoreFeedbackRepository implements FeedbackRepository {
  final FirebaseFirestore _firestore;

  static const String _collectionName = 'joke_feedback';

  FirestoreFeedbackRepository({FirebaseFirestore? firestore})
    : _firestore = firestore ?? FirebaseFirestore.instance;

  @override
  Future<void> submitFeedback(String feedbackText, String userId) async {
    final text = feedbackText.trim();
    if (text.isEmpty) {
      return;
    }

    // Generate custom document ID: YYYYMMDD_HHMMSS_[userId]
    final now = DateTime.now();
    final dateStr =
        now.year.toString().padLeft(4, '0') +
        now.month.toString().padLeft(2, '0') +
        now.day.toString().padLeft(2, '0');
    final timeStr =
        now.hour.toString().padLeft(2, '0') +
        now.minute.toString().padLeft(2, '0') +
        now.second.toString().padLeft(2, '0');
    final docId = '${dateStr}_${timeStr}_$userId';

    await _firestore.collection(_collectionName).doc(docId).set({
      'creation_time': FieldValue.serverTimestamp(),
      'feedback_text': text,
      'user_id': userId,
      'state': FeedbackState.NEW.name,
    });
  }

  @override
  Stream<List<FeedbackEntry>> watchAllFeedback() {
    return _firestore
        .collection(_collectionName)
        .orderBy('creation_time', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map((doc) => FeedbackEntry.fromFirestore(doc))
              .toList(),
        );
  }

  @override
  Stream<int> watchUnreadCount() {
    return _firestore
        .collection(_collectionName)
        .where('state', isEqualTo: FeedbackState.NEW.name)
        .snapshots()
        .map((s) => s.size);
  }

  @override
  Future<void> markFeedbackRead(String docId) async {
    await _firestore.collection(_collectionName).doc(docId).update({
      'state': FeedbackState.READ.name,
    });
  }
}

/// Enum representing feedback state stored in Firestore
enum FeedbackState { NEW, READ }

/// Feedback entry model used by admin UI
class FeedbackEntry {
  final String id;
  final DateTime? creationTime;
  final String feedbackText;
  final String userId;
  final FeedbackState state;

  FeedbackEntry({
    required this.id,
    required this.creationTime,
    required this.feedbackText,
    required this.userId,
    required this.state,
  });

  static FeedbackEntry fromFirestore(
    DocumentSnapshot<Map<String, dynamic>> doc,
  ) {
    final data = doc.data() ?? <String, dynamic>{};
    final ts = data['creation_time'];
    DateTime? created;
    if (ts is Timestamp) {
      created = ts.toDate();
    } else if (ts is DateTime) {
      created = ts;
    } else {
      created = null;
    }

    final stateStr = (data['state'] as String?) ?? FeedbackState.NEW.name;
    final state = stateStr == FeedbackState.READ.name
        ? FeedbackState.READ
        : FeedbackState.NEW;

    return FeedbackEntry(
      id: doc.id,
      creationTime: created,
      feedbackText: (data['feedback_text'] as String?) ?? '',
      userId: (data['user_id'] as String?) ?? 'anonymous',
      state: state,
    );
  }
}
