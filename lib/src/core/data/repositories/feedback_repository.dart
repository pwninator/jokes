import 'package:cloud_firestore/cloud_firestore.dart';

/// Repository for handling feedback-related Firestore operations
abstract class FeedbackRepository {
  /// Submit user feedback to Firestore
  Future<void> submitFeedback(String feedbackText, String userId);
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
    });
  }
}
