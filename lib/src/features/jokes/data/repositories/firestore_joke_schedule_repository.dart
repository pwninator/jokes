import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';

class FirestoreJokeScheduleRepository implements JokeScheduleRepository {
  final FirebaseFirestore _firestore;

  FirestoreJokeScheduleRepository({
    FirebaseFirestore? firestore,
  }) : _firestore = firestore ?? FirebaseFirestore.instance;

  static const String _schedulesCollection = 'joke_schedules';
  static const String _batchesCollection = 'joke_schedule_batches';

  @override
  Stream<List<JokeSchedule>> watchSchedules() {
    return _firestore
        .collection(_schedulesCollection)
        .orderBy('name')
        .snapshots()
        .map((snapshot) {
      return snapshot.docs
          .map((doc) => JokeSchedule.fromMap(doc.data(), doc.id))
          .toList();
    });
  }

  @override
  Stream<List<JokeScheduleBatch>> watchBatchesForSchedule(String scheduleId) {
    // Query batches that start with the schedule ID
    return _firestore
        .collection(_batchesCollection)
        .where(FieldPath.documentId, isGreaterThanOrEqualTo: '${scheduleId}_2000')
        .where(FieldPath.documentId, isLessThan: '${scheduleId}_3000')
        .snapshots()
        .map((snapshot) {
      return snapshot.docs
          .map((doc) {
            try {
              return JokeScheduleBatch.fromMap(doc.data(), doc.id);
            } catch (e) {
              // Skip invalid batch documents
              return null;
            }
          })
          .where((batch) => batch != null)
          .cast<JokeScheduleBatch>()
          .toList();
    });
  }

  @override
  Future<void> createSchedule(String name) async {
    final sanitizedId = JokeSchedule.sanitizeId(name);
    await _firestore.collection(_schedulesCollection).doc(sanitizedId).set({
      'name': name,
    });
  }

  @override
  Future<void> updateBatch(JokeScheduleBatch batch) async {
    await _firestore
        .collection(_batchesCollection)
        .doc(batch.id)
        .set(batch.toMap());
  }

  @override
  Future<void> deleteBatch(String batchId) async {
    await _firestore.collection(_batchesCollection).doc(batchId).delete();
  }

  @override
  Future<void> deleteSchedule(String scheduleId) async {
    final batch = _firestore.batch();

    // Delete the schedule document
    batch.delete(_firestore.collection(_schedulesCollection).doc(scheduleId));

    // Delete all batch documents for this schedule
    final batchesQuery = await _firestore
        .collection(_batchesCollection)
        .where(FieldPath.documentId, isGreaterThanOrEqualTo: '${scheduleId}_')
        .where(FieldPath.documentId, isLessThan: '${scheduleId}_\uf8ff')
        .get();

    for (final doc in batchesQuery.docs) {
      batch.delete(doc.reference);
    }

    await batch.commit();
  }
} 