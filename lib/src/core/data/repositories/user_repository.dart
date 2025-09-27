import 'package:cloud_firestore/cloud_firestore.dart';

/// Lightweight model representing a user's login summary
class AppUserSummary {
  final DateTime createdAtUtc;
  final DateTime lastLoginAtUtc;
  final int clientNumDaysUsed; // coerced to >= 1

  const AppUserSummary({
    required this.createdAtUtc,
    required this.lastLoginAtUtc,
    required this.clientNumDaysUsed,
  });
}

/// Repository abstraction for reading users
abstract class UserRepository {
  /// Stream all users from 'joke_users' collection (all time)
  Stream<List<AppUserSummary>> watchAllUsers();
}

class FirestoreUserRepository implements UserRepository {
  final FirebaseFirestore _firestore;

  static const String _collection = 'joke_users';

  FirestoreUserRepository({FirebaseFirestore? firestore})
    : _firestore = firestore ?? FirebaseFirestore.instance;

  @override
  Stream<List<AppUserSummary>> watchAllUsers() {
    return _firestore.collection(_collection).snapshots().map((snapshot) {
      return snapshot.docs.map((doc) {
        final data = doc.data();

        // Created at
        final createdAtTs = data['created_at'];
        DateTime createdAt;
        if (createdAtTs is Timestamp) {
          createdAt = createdAtTs.toDate();
        } else if (createdAtTs is DateTime) {
          createdAt = createdAtTs;
        } else {
          // Fallback to epoch if created_at is missing
          createdAt = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
        }

        // Last login
        final lastLoginTs = data['last_login_at'];
        DateTime lastLogin;
        if (lastLoginTs is Timestamp) {
          lastLogin = lastLoginTs.toDate();
        } else if (lastLoginTs is DateTime) {
          lastLogin = lastLoginTs;
        } else {
          // Per assumption: last_login_at always exists; if not, fallback to epoch
          lastLogin = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
        }
        // Coerce client_num_days_used to >= 1
        final daysUsedRaw = data['client_num_days_used'];
        int daysUsed = 1;
        if (daysUsedRaw is num) {
          final v = daysUsedRaw.toInt();
          daysUsed = v >= 1 ? v : 1;
        } else {
          daysUsed = 1;
        }
        final createdAtUtc = createdAt.isUtc ? createdAt : createdAt.toUtc();
        final lastLoginUtc = lastLogin.isUtc ? lastLogin : lastLogin.toUtc();
        return AppUserSummary(
          createdAtUtc: createdAtUtc,
          lastLoginAtUtc: lastLoginUtc,
          clientNumDaysUsed: daysUsed,
        );
      }).toList();
    });
  }
}
