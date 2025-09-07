import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class FirestoreJokeScheduleRepository implements JokeScheduleRepository {
  final FirebaseFirestore _firestore;
  final JokeRepository _jokeRepository;
  final tz.Location? _laLocation;

  FirestoreJokeScheduleRepository({
    FirebaseFirestore? firestore,
    required JokeRepository jokeRepository,
    tz.Location? laLocation,
  }) : _firestore = firestore ?? FirebaseFirestore.instance,
       _jokeRepository = jokeRepository,
       _laLocation = laLocation;

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
        .where(
          FieldPath.documentId,
          isGreaterThanOrEqualTo: '${scheduleId}_2000',
        )
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
  Future<void> updateBatches(List<JokeScheduleBatch> batches) async {
    if (batches.isEmpty) return;
    final writeBatch = _firestore.batch();
    for (final b in batches) {
      final ref = _firestore.collection(_batchesCollection).doc(b.id);
      writeBatch.set(ref, b.toMap());
    }
    await writeBatch.commit();
  }

  @override
  Future<void> deleteBatch(String batchId) async {
    // Parse batchId to extract scheduleId_year_month
    final parsed = JokeScheduleBatch.parseBatchId(batchId);
    if (parsed == null) {
      throw ArgumentError('Invalid batch ID: $batchId');
    }
    final year = parsed['year'] as int;
    final month = parsed['month'] as int;

    // Ensure timezone database is initialized (safe to call multiple times)
    tzdata.initializeTimeZones();
    final la = _laLocation ?? tz.getLocation('America/Los_Angeles');
    final nowLa = tz.TZDateTime.now(la);
    // Only allow deletion if batch month is strictly in the future in LA
    final isFuture =
        (year > nowLa.year) || (year == nowLa.year && month > nowLa.month);
    if (!isFuture) {
      throw StateError('Cannot delete schedule for current or past months.');
    }

    // Load batch to gather jokeIds
    final snapshot = await _firestore
        .collection(_batchesCollection)
        .doc(batchId)
        .get();
    if (!snapshot.exists) {
      // Nothing to do
      return;
    }
    final batchModel = JokeScheduleBatch.fromMap(snapshot.data()!, batchId);
    final jokeIds = batchModel.jokes.values.map((j) => j.id);

    // Reset jokes to APPROVED and clear public_timestamp, then delete the batch
    await _jokeRepository.resetJokesToApproved(
      jokeIds,
      expectedState: JokeState.daily,
    );
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
