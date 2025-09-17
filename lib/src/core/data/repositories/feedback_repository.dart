import 'package:cloud_firestore/cloud_firestore.dart';

class Message {
  final String text;
  final DateTime timestamp;
  final bool isFromAdmin;

  Message({
    required this.text,
    required this.timestamp,
    required this.isFromAdmin,
  });

  factory Message.fromFirestore(Map<String, dynamic> data) {
    return Message(
      text: data['text'] ?? '',
      timestamp: (data['timestamp'] as Timestamp).toDate(),
      isFromAdmin: data['isFromAdmin'] ?? false,
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'text': text,
      'timestamp': Timestamp.fromDate(timestamp),
      'isFromAdmin': isFromAdmin,
    };
  }
}

/// Repository for handling feedback-related Firestore operations
abstract class FeedbackRepository {
  /// Submit user feedback to Firestore
  Future<void> submitFeedback(String feedbackText, String userId);

  /// Stream all feedback ordered by creation_time descending
  Stream<List<FeedbackEntry>> watchAllFeedback();

  /// Adds a message to a feedback document
  Future<void> addMessage(String docId, Message message);

  /// Updates the last admin view time for a feedback document
  Future<void> updateLastAdminViewTime(String docId);
}

class FirestoreFeedbackRepository implements FeedbackRepository {
  final FirebaseFirestore _firestore;

  static const String _collectionName = 'feedback';

  FirestoreFeedbackRepository({FirebaseFirestore? firestore})
      : _firestore = firestore ?? FirebaseFirestore.instance;

  @override
  Future<void> submitFeedback(String feedbackText, String userId) async {
    final text = feedbackText.trim();
    if (text.isEmpty) {
      return;
    }

    final now = DateTime.now();
    final initialMessage = Message(
      text: text,
      timestamp: now,
      isFromAdmin: false,
    );

    await _firestore.collection(_collectionName).add({
      'creation_time': FieldValue.serverTimestamp(),
      'user_id': userId,
      'last_admin_view_time': null,
      'messages': [initialMessage.toFirestore()],
      'lastMessage': initialMessage.toFirestore(),
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
  Future<void> addMessage(String docId, Message message) async {
    await _firestore.collection(_collectionName).doc(docId).update({
      'messages': FieldValue.arrayUnion([message.toFirestore()]),
      'lastMessage': message.toFirestore(),
    });
  }

  @override
  Future<void> updateLastAdminViewTime(String docId) async {
    await _firestore.collection(_collectionName).doc(docId).update({
      'last_admin_view_time': FieldValue.serverTimestamp(),
    });
  }
}

/// Feedback entry model used by admin UI
class FeedbackEntry {
  final String id;
  final DateTime? creationTime;
  final String userId;
  final DateTime? lastAdminViewTime;
  final List<Message> messages;
  final Message? lastMessage;

  FeedbackEntry({
    required this.id,
    required this.creationTime,
    required this.userId,
    required this.lastAdminViewTime,
    required this.messages,
    this.lastMessage,
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

    final lastAdminViewTimeTs = data['last_admin_view_time'];
    DateTime? lastAdminViewTime;
    if (lastAdminViewTimeTs is Timestamp) {
      lastAdminViewTime = lastAdminViewTimeTs.toDate();
    }

    final messagesData = data['messages'] as List<dynamic>? ?? [];
    final messages =
        messagesData.map((m) => Message.fromFirestore(m)).toList();

    final lastMessageData = data['lastMessage'] as Map<String, dynamic>?;
    final lastMessage =
        lastMessageData != null ? Message.fromFirestore(lastMessageData) : null;

    return FeedbackEntry(
      id: doc.id,
      creationTime: created,
      userId: (data['user_id'] as String?) ?? 'anonymous',
      lastAdminViewTime: lastAdminViewTime,
      messages: messages,
      lastMessage: lastMessage,
    );
  }
}
