import 'package:cloud_firestore/cloud_firestore.dart';

/// Lightweight model representing a user's login summary
class AppUserSummary {
  final DateTime lastLoginAtUtc;
  final int clientNumDaysUsed; // coerced to >= 1

  const AppUserSummary({
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
        final ts = data['last_login_at'];
        DateTime lastLogin;
        if (ts is Timestamp) {
          lastLogin = ts.toDate();
        } else if (ts is DateTime) {
          lastLogin = ts;
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
        final utc = lastLogin.isUtc ? lastLogin : lastLogin.toUtc();
        return AppUserSummary(lastLoginAtUtc: utc, clientNumDaysUsed: daysUsed);
      }).toList();
    });
  }
}
