import 'package:cloud_firestore/cloud_firestore.dart';

/// Enum representing the speaker in a feedback conversation
enum SpeakerType {
  user('USER'),
  admin('ADMIN');

  const SpeakerType(this.value);

  /// The string value used in Firestore
  final String value;

  /// Create SpeakerType from string value
  static SpeakerType fromString(String value) {
    switch (value.toUpperCase()) {
      case 'USER':
        return SpeakerType.user;
      case 'ADMIN':
        return SpeakerType.admin;
      default:
        return SpeakerType.user; // Default to user for unknown values
    }
  }
}

// Represents a single entry in a feedback conversation
class FeedbackConversationEntry {
  final SpeakerType speaker;
  final String text;
  final DateTime timestamp;

  FeedbackConversationEntry({
    required this.speaker,
    required this.text,
    required this.timestamp,
  });

  bool get isFromAdmin => speaker == SpeakerType.admin;

  factory FeedbackConversationEntry.fromMap(Map<String, dynamic> map) {
    return FeedbackConversationEntry(
      speaker: SpeakerType.fromString(map['speaker'] ?? 'USER'),
      text: map['text'] ?? '',
      timestamp: (map['timestamp'] as Timestamp).toDate(),
    );
  }

  /// Convert to Firestore format
  Map<String, dynamic> toFirestore() {
    return {
      'speaker': speaker.value,
      'text': text,
      'timestamp': Timestamp.fromDate(timestamp.toUtc()),
    };
  }
}

/// Repository for handling feedback-related Firestore operations
abstract class FeedbackRepository {
  /// Submit user feedback to Firestore
  Future<void> submitFeedback(String feedbackText, String userId);

  /// Add a message to a feedback conversation
  Future<void> addConversationMessage(
    String docId,
    String text,
    SpeakerType speaker,
  );

  /// Update last admin view time to server time
  Future<void> updateLastAdminViewTime(String docId);

  /// Stream all feedback ordered by creation_time descending
  Stream<List<FeedbackEntry>> watchAllFeedback();

  /// Stream the count of unread feedback items
  Stream<int> watchUnreadCount();
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

    final conversationEntry = {
      'speaker': SpeakerType.user.value,
      'text': text,
      'timestamp': Timestamp.fromDate(DateTime.now().toUtc()),
    };

    await _firestore.collection(_collectionName).doc(docId).set({
      'creation_time': FieldValue.serverTimestamp(),
      'conversation': [conversationEntry],
      'user_id': userId,
      'lastAdminViewTime': null,
    });
  }

  @override
  Future<void> addConversationMessage(
    String docId,
    String text,
    SpeakerType speaker,
  ) async {
    final docRef = _firestore.collection(_collectionName).doc(docId);
    final doc = await docRef.get();

    if (!doc.exists) {
      throw Exception('Feedback document not found: $docId');
    }

    final data = doc.data()!;

    // Use existing fromFirestore logic to handle legacy migration
    final feedbackEntry = FeedbackEntry.fromFirestore(doc);

    // Create new conversation entry
    final newEntry = FeedbackConversationEntry(
      speaker: speaker,
      text: text,
      timestamp: DateTime.now(),
    );

    // Add to existing conversation (which already handles legacy migration)
    final updatedConversation = [...feedbackEntry.conversation, newEntry];

    // Convert back to Firestore format and update
    final updates = <String, dynamic>{
      'conversation': updatedConversation.map((e) => e.toFirestore()).toList(),
    };

    // Remove legacy field if it exists
    if (data.containsKey('feedback_text')) {
      updates['feedback_text'] = FieldValue.delete();
    }

    await docRef.update(updates);
  }

  @override
  Future<void> updateLastAdminViewTime(String docId) async {
    await _firestore.collection(_collectionName).doc(docId).update({
      'lastAdminViewTime': FieldValue.serverTimestamp(),
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
    return watchAllFeedback().map((entries) {
      int count = 0;
      for (final entry in entries) {
        if (entry.conversation.isEmpty) {
          continue;
        }
        final last = entry.conversation.last;
        final lastView = entry.lastAdminViewTime;
        final isUnread =
            !last.isFromAdmin &&
            (lastView == null || lastView.isBefore(last.timestamp));
        if (isUnread) count++;
      }
      return count;
    });
  }
}

/// Feedback entry model used by admin UI
class FeedbackEntry {
  final String id;
  final DateTime? creationTime;
  final List<FeedbackConversationEntry> conversation;
  final String userId;
  final DateTime? lastAdminViewTime;

  FeedbackEntry({
    required this.id,
    required this.creationTime,
    required this.conversation,
    required this.userId,
    required this.lastAdminViewTime,
  });

  FeedbackConversationEntry? get lastMessage =>
      conversation.isNotEmpty ? conversation.last : null;

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

    // Parse last admin view time
    final lastViewRaw = data['lastAdminViewTime'];
    DateTime? lastAdminViewTime;
    if (lastViewRaw is Timestamp) {
      lastAdminViewTime = lastViewRaw.toDate();
    } else if (lastViewRaw is DateTime) {
      lastAdminViewTime = lastViewRaw;
    }

    // Handle both new conversation format and legacy feedback_text format
    List<FeedbackConversationEntry> conversation;
    final conversationData = data['conversation'] as List<dynamic>?;

    if (conversationData != null && conversationData.isNotEmpty) {
      // New format: conversation array exists
      conversation = conversationData
          .map(
            (e) => FeedbackConversationEntry.fromMap(e as Map<String, dynamic>),
          )
          .toList();
    } else {
      // Legacy format: check for feedback_text field
      final feedbackText = data['feedback_text'] as String?;
      if (feedbackText != null && feedbackText.isNotEmpty) {
        // Create a single conversation entry from legacy feedback_text
        conversation = [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: feedbackText,
            timestamp:
                created ?? DateTime.now(), // Use creation_time as timestamp
          ),
        ];
      } else {
        // No conversation data found
        conversation = [];
      }
    }

    return FeedbackEntry(
      id: doc.id,
      creationTime: created,
      conversation: conversation,
      userId: (data['user_id'] as String?) ?? 'anonymous',
      lastAdminViewTime: lastAdminViewTime,
    );
  }
}
