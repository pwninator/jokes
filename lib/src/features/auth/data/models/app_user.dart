enum UserRole {
  anonymous,
  user,
  admin,
}

class AppUser {
  final String id;
  final String? email;
  final String? displayName;
  final UserRole role;
  final bool isAnonymous;

  const AppUser({
    required this.id,
    this.email,
    this.displayName,
    required this.role,
    required this.isAnonymous,
  });

  factory AppUser.anonymous(String id) {
    return AppUser(
      id: id,
      role: UserRole.anonymous,
      isAnonymous: true,
    );
  }

  factory AppUser.authenticated({
    required String id,
    String? email,
    String? displayName,
    UserRole role = UserRole.user,
  }) {
    return AppUser(
      id: id,
      email: email,
      displayName: displayName,
      role: role,
      isAnonymous: false,
    );
  }

  bool get isAdmin => role == UserRole.admin;
  bool get isUser => role == UserRole.user;

  AppUser copyWith({
    String? id,
    String? email,
    String? displayName,
    UserRole? role,
    bool? isAnonymous,
  }) {
    return AppUser(
      id: id ?? this.id,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      role: role ?? this.role,
      isAnonymous: isAnonymous ?? this.isAnonymous,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AppUser &&
        other.id == id &&
        other.email == email &&
        other.displayName == displayName &&
        other.role == role &&
        other.isAnonymous == isAnonymous;
  }

  @override
  int get hashCode {
    return id.hashCode ^
        email.hashCode ^
        displayName.hashCode ^
        role.hashCode ^
        isAnonymous.hashCode;
  }

  @override
  String toString() {
    return 'AppUser(id: $id, email: $email, displayName: $displayName, role: $role, isAnonymous: $isAnonymous)';
  }
} 