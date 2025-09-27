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

  /// Update last user view time to server time
  Future<void> updateLastUserViewTime(String docId);

  /// Stream all feedback ordered by creation_time descending
  Stream<List<FeedbackEntry>> watchAllFeedback();

  /// Stream all feedback for a user ordered by creation_time descending
  Stream<List<FeedbackEntry>> watchAllFeedbackForUser(String userId);

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

    final docRef = _firestore.collection(_collectionName).doc(userId);
    final newEntry = FeedbackConversationEntry(
      speaker: SpeakerType.user,
      text: text,
      timestamp: DateTime.now().toUtc(),
    );

    await _firestore.runTransaction((transaction) async {
      final snapshot = await transaction.get(docRef);

      if (!snapshot.exists) {
        transaction.set(docRef, {
          'creation_time': FieldValue.serverTimestamp(),
          'conversation': [newEntry.toFirestore()],
          'user_id': userId,
          'lastAdminViewTime': null,
          'lastUserViewTime': null,
        });
        return;
      }

      final feedbackEntry = FeedbackEntry.fromFirestore(snapshot);
      final updatedConversation = [...feedbackEntry.conversation, newEntry];

      final updates = <String, dynamic>{
        'conversation': updatedConversation
            .map((e) => e.toFirestore())
            .toList(),
      };

      final data = snapshot.data();
      if (data != null) {
        if (data.containsKey('feedback_text')) {
          updates['feedback_text'] = FieldValue.delete();
        }
        if ((data['user_id'] as String?) != userId) {
          updates['user_id'] = userId;
        }
      } else {
        updates['user_id'] = userId;
      }

      transaction.update(docRef, updates);
    });
  }

  @override
  Future<void> addConversationMessage(
    String docId,
    String text,
    SpeakerType speaker,
  ) async {
    final trimmedText = text.trim();
    if (trimmedText.isEmpty) {
      return;
    }

    final docRef = _firestore.collection(_collectionName).doc(docId);
    final newEntry = FeedbackConversationEntry(
      speaker: speaker,
      text: trimmedText,
      timestamp: DateTime.now().toUtc(),
    );

    await _firestore.runTransaction((transaction) async {
      final snapshot = await transaction.get(docRef);

      if (!snapshot.exists) {
        transaction.set(docRef, {
          'creation_time': FieldValue.serverTimestamp(),
          'conversation': [newEntry.toFirestore()],
          'user_id': docId,
          'lastAdminViewTime': null,
          'lastUserViewTime': null,
        });
        return;
      }

      final feedbackEntry = FeedbackEntry.fromFirestore(snapshot);
      final updatedConversation = [...feedbackEntry.conversation, newEntry];

      final updates = <String, dynamic>{
        'conversation': updatedConversation
            .map((e) => e.toFirestore())
            .toList(),
      };

      final data = snapshot.data();
      if (data != null) {
        if (data.containsKey('feedback_text')) {
          updates['feedback_text'] = FieldValue.delete();
        }
        if ((data['user_id'] as String?) != docId) {
          updates['user_id'] = docId;
        }
      } else {
        updates['user_id'] = docId;
      }

      transaction.update(docRef, updates);
    });
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
  Future<void> updateLastUserViewTime(String docId) async {
    await _firestore.collection(_collectionName).doc(docId).update({
      'lastUserViewTime': FieldValue.serverTimestamp(),
    });
  }

  @override
  Stream<List<FeedbackEntry>> watchAllFeedbackForUser(String userId) {
    return _firestore
        .collection(_collectionName)
        .where('user_id', isEqualTo: userId)
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
  final DateTime? lastUserViewTime;

  FeedbackEntry({
    required this.id,
    required this.creationTime,
    required this.conversation,
    required this.userId,
    required this.lastAdminViewTime,
    required this.lastUserViewTime,
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
    final lastAdminViewRaw = data['lastAdminViewTime'];
    DateTime? lastAdminViewTime;
    if (lastAdminViewRaw is Timestamp) {
      lastAdminViewTime = lastAdminViewRaw.toDate();
    } else if (lastAdminViewRaw is DateTime) {
      lastAdminViewTime = lastAdminViewRaw;
    }

    // Parse last user view time
    final lastUserViewRaw = data['lastUserViewTime'];
    DateTime? lastUserViewTime;
    if (lastUserViewRaw is Timestamp) {
      lastUserViewTime = lastUserViewRaw.toDate();
    } else if (lastUserViewRaw is DateTime) {
      lastUserViewTime = lastUserViewRaw;
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
      lastUserViewTime: lastUserViewTime,
    );
  }
}
