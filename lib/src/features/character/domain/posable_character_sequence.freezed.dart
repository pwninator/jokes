// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'posable_character_sequence.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
  'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models',
);

CharacterTransform _$CharacterTransformFromJson(Map<String, dynamic> json) {
  return _CharacterTransform.fromJson(json);
}

/// @nodoc
mixin _$CharacterTransform {
  double get translateX => throw _privateConstructorUsedError;
  double get translateY => throw _privateConstructorUsedError;
  double get scaleX => throw _privateConstructorUsedError;
  double get scaleY => throw _privateConstructorUsedError;

  /// Serializes this CharacterTransform to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of CharacterTransform
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $CharacterTransformCopyWith<CharacterTransform> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $CharacterTransformCopyWith<$Res> {
  factory $CharacterTransformCopyWith(
    CharacterTransform value,
    $Res Function(CharacterTransform) then,
  ) = _$CharacterTransformCopyWithImpl<$Res, CharacterTransform>;
  @useResult
  $Res call({
    double translateX,
    double translateY,
    double scaleX,
    double scaleY,
  });
}

/// @nodoc
class _$CharacterTransformCopyWithImpl<$Res, $Val extends CharacterTransform>
    implements $CharacterTransformCopyWith<$Res> {
  _$CharacterTransformCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of CharacterTransform
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? translateX = null,
    Object? translateY = null,
    Object? scaleX = null,
    Object? scaleY = null,
  }) {
    return _then(
      _value.copyWith(
            translateX: null == translateX
                ? _value.translateX
                : translateX // ignore: cast_nullable_to_non_nullable
                      as double,
            translateY: null == translateY
                ? _value.translateY
                : translateY // ignore: cast_nullable_to_non_nullable
                      as double,
            scaleX: null == scaleX
                ? _value.scaleX
                : scaleX // ignore: cast_nullable_to_non_nullable
                      as double,
            scaleY: null == scaleY
                ? _value.scaleY
                : scaleY // ignore: cast_nullable_to_non_nullable
                      as double,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$CharacterTransformImplCopyWith<$Res>
    implements $CharacterTransformCopyWith<$Res> {
  factory _$$CharacterTransformImplCopyWith(
    _$CharacterTransformImpl value,
    $Res Function(_$CharacterTransformImpl) then,
  ) = __$$CharacterTransformImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({
    double translateX,
    double translateY,
    double scaleX,
    double scaleY,
  });
}

/// @nodoc
class __$$CharacterTransformImplCopyWithImpl<$Res>
    extends _$CharacterTransformCopyWithImpl<$Res, _$CharacterTransformImpl>
    implements _$$CharacterTransformImplCopyWith<$Res> {
  __$$CharacterTransformImplCopyWithImpl(
    _$CharacterTransformImpl _value,
    $Res Function(_$CharacterTransformImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of CharacterTransform
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? translateX = null,
    Object? translateY = null,
    Object? scaleX = null,
    Object? scaleY = null,
  }) {
    return _then(
      _$CharacterTransformImpl(
        translateX: null == translateX
            ? _value.translateX
            : translateX // ignore: cast_nullable_to_non_nullable
                  as double,
        translateY: null == translateY
            ? _value.translateY
            : translateY // ignore: cast_nullable_to_non_nullable
                  as double,
        scaleX: null == scaleX
            ? _value.scaleX
            : scaleX // ignore: cast_nullable_to_non_nullable
                  as double,
        scaleY: null == scaleY
            ? _value.scaleY
            : scaleY // ignore: cast_nullable_to_non_nullable
                  as double,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$CharacterTransformImpl implements _CharacterTransform {
  const _$CharacterTransformImpl({
    this.translateX = 0.0,
    this.translateY = 0.0,
    this.scaleX = 1.0,
    this.scaleY = 1.0,
  });

  factory _$CharacterTransformImpl.fromJson(Map<String, dynamic> json) =>
      _$$CharacterTransformImplFromJson(json);

  @override
  @JsonKey()
  final double translateX;
  @override
  @JsonKey()
  final double translateY;
  @override
  @JsonKey()
  final double scaleX;
  @override
  @JsonKey()
  final double scaleY;

  @override
  String toString() {
    return 'CharacterTransform(translateX: $translateX, translateY: $translateY, scaleX: $scaleX, scaleY: $scaleY)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$CharacterTransformImpl &&
            (identical(other.translateX, translateX) ||
                other.translateX == translateX) &&
            (identical(other.translateY, translateY) ||
                other.translateY == translateY) &&
            (identical(other.scaleX, scaleX) || other.scaleX == scaleX) &&
            (identical(other.scaleY, scaleY) || other.scaleY == scaleY));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, translateX, translateY, scaleX, scaleY);

  /// Create a copy of CharacterTransform
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$CharacterTransformImplCopyWith<_$CharacterTransformImpl> get copyWith =>
      __$$CharacterTransformImplCopyWithImpl<_$CharacterTransformImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$CharacterTransformImplToJson(this);
  }
}

abstract class _CharacterTransform implements CharacterTransform {
  const factory _CharacterTransform({
    final double translateX,
    final double translateY,
    final double scaleX,
    final double scaleY,
  }) = _$CharacterTransformImpl;

  factory _CharacterTransform.fromJson(Map<String, dynamic> json) =
      _$CharacterTransformImpl.fromJson;

  @override
  double get translateX;
  @override
  double get translateY;
  @override
  double get scaleX;
  @override
  double get scaleY;

  /// Create a copy of CharacterTransform
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$CharacterTransformImplCopyWith<_$CharacterTransformImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

InitialPoseState _$InitialPoseStateFromJson(Map<String, dynamic> json) {
  return _InitialPoseState.fromJson(json);
}

/// @nodoc
mixin _$InitialPoseState {
  bool? get leftEyeOpen => throw _privateConstructorUsedError;
  bool? get rightEyeOpen => throw _privateConstructorUsedError;
  MouthState? get mouthState => throw _privateConstructorUsedError;
  bool? get leftHandVisible => throw _privateConstructorUsedError;
  bool? get rightHandVisible => throw _privateConstructorUsedError;
  CharacterTransform? get leftHandTransform =>
      throw _privateConstructorUsedError;
  CharacterTransform? get rightHandTransform =>
      throw _privateConstructorUsedError;
  CharacterTransform? get headTransform => throw _privateConstructorUsedError;
  double? get surfaceLineOffset => throw _privateConstructorUsedError;
  double? get maskBoundaryOffset => throw _privateConstructorUsedError;
  bool? get surfaceLineVisible => throw _privateConstructorUsedError;
  bool? get headMaskingEnabled => throw _privateConstructorUsedError;
  bool? get leftHandMaskingEnabled => throw _privateConstructorUsedError;
  bool? get rightHandMaskingEnabled => throw _privateConstructorUsedError;

  /// Serializes this InitialPoseState to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $InitialPoseStateCopyWith<InitialPoseState> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $InitialPoseStateCopyWith<$Res> {
  factory $InitialPoseStateCopyWith(
    InitialPoseState value,
    $Res Function(InitialPoseState) then,
  ) = _$InitialPoseStateCopyWithImpl<$Res, InitialPoseState>;
  @useResult
  $Res call({
    bool? leftEyeOpen,
    bool? rightEyeOpen,
    MouthState? mouthState,
    bool? leftHandVisible,
    bool? rightHandVisible,
    CharacterTransform? leftHandTransform,
    CharacterTransform? rightHandTransform,
    CharacterTransform? headTransform,
    double? surfaceLineOffset,
    double? maskBoundaryOffset,
    bool? surfaceLineVisible,
    bool? headMaskingEnabled,
    bool? leftHandMaskingEnabled,
    bool? rightHandMaskingEnabled,
  });

  $CharacterTransformCopyWith<$Res>? get leftHandTransform;
  $CharacterTransformCopyWith<$Res>? get rightHandTransform;
  $CharacterTransformCopyWith<$Res>? get headTransform;
}

/// @nodoc
class _$InitialPoseStateCopyWithImpl<$Res, $Val extends InitialPoseState>
    implements $InitialPoseStateCopyWith<$Res> {
  _$InitialPoseStateCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? leftEyeOpen = freezed,
    Object? rightEyeOpen = freezed,
    Object? mouthState = freezed,
    Object? leftHandVisible = freezed,
    Object? rightHandVisible = freezed,
    Object? leftHandTransform = freezed,
    Object? rightHandTransform = freezed,
    Object? headTransform = freezed,
    Object? surfaceLineOffset = freezed,
    Object? maskBoundaryOffset = freezed,
    Object? surfaceLineVisible = freezed,
    Object? headMaskingEnabled = freezed,
    Object? leftHandMaskingEnabled = freezed,
    Object? rightHandMaskingEnabled = freezed,
  }) {
    return _then(
      _value.copyWith(
            leftEyeOpen: freezed == leftEyeOpen
                ? _value.leftEyeOpen
                : leftEyeOpen // ignore: cast_nullable_to_non_nullable
                      as bool?,
            rightEyeOpen: freezed == rightEyeOpen
                ? _value.rightEyeOpen
                : rightEyeOpen // ignore: cast_nullable_to_non_nullable
                      as bool?,
            mouthState: freezed == mouthState
                ? _value.mouthState
                : mouthState // ignore: cast_nullable_to_non_nullable
                      as MouthState?,
            leftHandVisible: freezed == leftHandVisible
                ? _value.leftHandVisible
                : leftHandVisible // ignore: cast_nullable_to_non_nullable
                      as bool?,
            rightHandVisible: freezed == rightHandVisible
                ? _value.rightHandVisible
                : rightHandVisible // ignore: cast_nullable_to_non_nullable
                      as bool?,
            leftHandTransform: freezed == leftHandTransform
                ? _value.leftHandTransform
                : leftHandTransform // ignore: cast_nullable_to_non_nullable
                      as CharacterTransform?,
            rightHandTransform: freezed == rightHandTransform
                ? _value.rightHandTransform
                : rightHandTransform // ignore: cast_nullable_to_non_nullable
                      as CharacterTransform?,
            headTransform: freezed == headTransform
                ? _value.headTransform
                : headTransform // ignore: cast_nullable_to_non_nullable
                      as CharacterTransform?,
            surfaceLineOffset: freezed == surfaceLineOffset
                ? _value.surfaceLineOffset
                : surfaceLineOffset // ignore: cast_nullable_to_non_nullable
                      as double?,
            maskBoundaryOffset: freezed == maskBoundaryOffset
                ? _value.maskBoundaryOffset
                : maskBoundaryOffset // ignore: cast_nullable_to_non_nullable
                      as double?,
            surfaceLineVisible: freezed == surfaceLineVisible
                ? _value.surfaceLineVisible
                : surfaceLineVisible // ignore: cast_nullable_to_non_nullable
                      as bool?,
            headMaskingEnabled: freezed == headMaskingEnabled
                ? _value.headMaskingEnabled
                : headMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as bool?,
            leftHandMaskingEnabled: freezed == leftHandMaskingEnabled
                ? _value.leftHandMaskingEnabled
                : leftHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as bool?,
            rightHandMaskingEnabled: freezed == rightHandMaskingEnabled
                ? _value.rightHandMaskingEnabled
                : rightHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as bool?,
          )
          as $Val,
    );
  }

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $CharacterTransformCopyWith<$Res>? get leftHandTransform {
    if (_value.leftHandTransform == null) {
      return null;
    }

    return $CharacterTransformCopyWith<$Res>(_value.leftHandTransform!, (
      value,
    ) {
      return _then(_value.copyWith(leftHandTransform: value) as $Val);
    });
  }

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $CharacterTransformCopyWith<$Res>? get rightHandTransform {
    if (_value.rightHandTransform == null) {
      return null;
    }

    return $CharacterTransformCopyWith<$Res>(_value.rightHandTransform!, (
      value,
    ) {
      return _then(_value.copyWith(rightHandTransform: value) as $Val);
    });
  }

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $CharacterTransformCopyWith<$Res>? get headTransform {
    if (_value.headTransform == null) {
      return null;
    }

    return $CharacterTransformCopyWith<$Res>(_value.headTransform!, (value) {
      return _then(_value.copyWith(headTransform: value) as $Val);
    });
  }
}

/// @nodoc
abstract class _$$InitialPoseStateImplCopyWith<$Res>
    implements $InitialPoseStateCopyWith<$Res> {
  factory _$$InitialPoseStateImplCopyWith(
    _$InitialPoseStateImpl value,
    $Res Function(_$InitialPoseStateImpl) then,
  ) = __$$InitialPoseStateImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({
    bool? leftEyeOpen,
    bool? rightEyeOpen,
    MouthState? mouthState,
    bool? leftHandVisible,
    bool? rightHandVisible,
    CharacterTransform? leftHandTransform,
    CharacterTransform? rightHandTransform,
    CharacterTransform? headTransform,
    double? surfaceLineOffset,
    double? maskBoundaryOffset,
    bool? surfaceLineVisible,
    bool? headMaskingEnabled,
    bool? leftHandMaskingEnabled,
    bool? rightHandMaskingEnabled,
  });

  @override
  $CharacterTransformCopyWith<$Res>? get leftHandTransform;
  @override
  $CharacterTransformCopyWith<$Res>? get rightHandTransform;
  @override
  $CharacterTransformCopyWith<$Res>? get headTransform;
}

/// @nodoc
class __$$InitialPoseStateImplCopyWithImpl<$Res>
    extends _$InitialPoseStateCopyWithImpl<$Res, _$InitialPoseStateImpl>
    implements _$$InitialPoseStateImplCopyWith<$Res> {
  __$$InitialPoseStateImplCopyWithImpl(
    _$InitialPoseStateImpl _value,
    $Res Function(_$InitialPoseStateImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? leftEyeOpen = freezed,
    Object? rightEyeOpen = freezed,
    Object? mouthState = freezed,
    Object? leftHandVisible = freezed,
    Object? rightHandVisible = freezed,
    Object? leftHandTransform = freezed,
    Object? rightHandTransform = freezed,
    Object? headTransform = freezed,
    Object? surfaceLineOffset = freezed,
    Object? maskBoundaryOffset = freezed,
    Object? surfaceLineVisible = freezed,
    Object? headMaskingEnabled = freezed,
    Object? leftHandMaskingEnabled = freezed,
    Object? rightHandMaskingEnabled = freezed,
  }) {
    return _then(
      _$InitialPoseStateImpl(
        leftEyeOpen: freezed == leftEyeOpen
            ? _value.leftEyeOpen
            : leftEyeOpen // ignore: cast_nullable_to_non_nullable
                  as bool?,
        rightEyeOpen: freezed == rightEyeOpen
            ? _value.rightEyeOpen
            : rightEyeOpen // ignore: cast_nullable_to_non_nullable
                  as bool?,
        mouthState: freezed == mouthState
            ? _value.mouthState
            : mouthState // ignore: cast_nullable_to_non_nullable
                  as MouthState?,
        leftHandVisible: freezed == leftHandVisible
            ? _value.leftHandVisible
            : leftHandVisible // ignore: cast_nullable_to_non_nullable
                  as bool?,
        rightHandVisible: freezed == rightHandVisible
            ? _value.rightHandVisible
            : rightHandVisible // ignore: cast_nullable_to_non_nullable
                  as bool?,
        leftHandTransform: freezed == leftHandTransform
            ? _value.leftHandTransform
            : leftHandTransform // ignore: cast_nullable_to_non_nullable
                  as CharacterTransform?,
        rightHandTransform: freezed == rightHandTransform
            ? _value.rightHandTransform
            : rightHandTransform // ignore: cast_nullable_to_non_nullable
                  as CharacterTransform?,
        headTransform: freezed == headTransform
            ? _value.headTransform
            : headTransform // ignore: cast_nullable_to_non_nullable
                  as CharacterTransform?,
        surfaceLineOffset: freezed == surfaceLineOffset
            ? _value.surfaceLineOffset
            : surfaceLineOffset // ignore: cast_nullable_to_non_nullable
                  as double?,
        maskBoundaryOffset: freezed == maskBoundaryOffset
            ? _value.maskBoundaryOffset
            : maskBoundaryOffset // ignore: cast_nullable_to_non_nullable
                  as double?,
        surfaceLineVisible: freezed == surfaceLineVisible
            ? _value.surfaceLineVisible
            : surfaceLineVisible // ignore: cast_nullable_to_non_nullable
                  as bool?,
        headMaskingEnabled: freezed == headMaskingEnabled
            ? _value.headMaskingEnabled
            : headMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as bool?,
        leftHandMaskingEnabled: freezed == leftHandMaskingEnabled
            ? _value.leftHandMaskingEnabled
            : leftHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as bool?,
        rightHandMaskingEnabled: freezed == rightHandMaskingEnabled
            ? _value.rightHandMaskingEnabled
            : rightHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as bool?,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$InitialPoseStateImpl implements _InitialPoseState {
  const _$InitialPoseStateImpl({
    this.leftEyeOpen,
    this.rightEyeOpen,
    this.mouthState,
    this.leftHandVisible,
    this.rightHandVisible,
    this.leftHandTransform,
    this.rightHandTransform,
    this.headTransform,
    this.surfaceLineOffset,
    this.maskBoundaryOffset,
    this.surfaceLineVisible,
    this.headMaskingEnabled,
    this.leftHandMaskingEnabled,
    this.rightHandMaskingEnabled,
  });

  factory _$InitialPoseStateImpl.fromJson(Map<String, dynamic> json) =>
      _$$InitialPoseStateImplFromJson(json);

  @override
  final bool? leftEyeOpen;
  @override
  final bool? rightEyeOpen;
  @override
  final MouthState? mouthState;
  @override
  final bool? leftHandVisible;
  @override
  final bool? rightHandVisible;
  @override
  final CharacterTransform? leftHandTransform;
  @override
  final CharacterTransform? rightHandTransform;
  @override
  final CharacterTransform? headTransform;
  @override
  final double? surfaceLineOffset;
  @override
  final double? maskBoundaryOffset;
  @override
  final bool? surfaceLineVisible;
  @override
  final bool? headMaskingEnabled;
  @override
  final bool? leftHandMaskingEnabled;
  @override
  final bool? rightHandMaskingEnabled;

  @override
  String toString() {
    return 'InitialPoseState(leftEyeOpen: $leftEyeOpen, rightEyeOpen: $rightEyeOpen, mouthState: $mouthState, leftHandVisible: $leftHandVisible, rightHandVisible: $rightHandVisible, leftHandTransform: $leftHandTransform, rightHandTransform: $rightHandTransform, headTransform: $headTransform, surfaceLineOffset: $surfaceLineOffset, maskBoundaryOffset: $maskBoundaryOffset, surfaceLineVisible: $surfaceLineVisible, headMaskingEnabled: $headMaskingEnabled, leftHandMaskingEnabled: $leftHandMaskingEnabled, rightHandMaskingEnabled: $rightHandMaskingEnabled)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$InitialPoseStateImpl &&
            (identical(other.leftEyeOpen, leftEyeOpen) ||
                other.leftEyeOpen == leftEyeOpen) &&
            (identical(other.rightEyeOpen, rightEyeOpen) ||
                other.rightEyeOpen == rightEyeOpen) &&
            (identical(other.mouthState, mouthState) ||
                other.mouthState == mouthState) &&
            (identical(other.leftHandVisible, leftHandVisible) ||
                other.leftHandVisible == leftHandVisible) &&
            (identical(other.rightHandVisible, rightHandVisible) ||
                other.rightHandVisible == rightHandVisible) &&
            (identical(other.leftHandTransform, leftHandTransform) ||
                other.leftHandTransform == leftHandTransform) &&
            (identical(other.rightHandTransform, rightHandTransform) ||
                other.rightHandTransform == rightHandTransform) &&
            (identical(other.headTransform, headTransform) ||
                other.headTransform == headTransform) &&
            (identical(other.surfaceLineOffset, surfaceLineOffset) ||
                other.surfaceLineOffset == surfaceLineOffset) &&
            (identical(other.maskBoundaryOffset, maskBoundaryOffset) ||
                other.maskBoundaryOffset == maskBoundaryOffset) &&
            (identical(other.surfaceLineVisible, surfaceLineVisible) ||
                other.surfaceLineVisible == surfaceLineVisible) &&
            (identical(other.headMaskingEnabled, headMaskingEnabled) ||
                other.headMaskingEnabled == headMaskingEnabled) &&
            (identical(other.leftHandMaskingEnabled, leftHandMaskingEnabled) ||
                other.leftHandMaskingEnabled == leftHandMaskingEnabled) &&
            (identical(
                  other.rightHandMaskingEnabled,
                  rightHandMaskingEnabled,
                ) ||
                other.rightHandMaskingEnabled == rightHandMaskingEnabled));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
    runtimeType,
    leftEyeOpen,
    rightEyeOpen,
    mouthState,
    leftHandVisible,
    rightHandVisible,
    leftHandTransform,
    rightHandTransform,
    headTransform,
    surfaceLineOffset,
    maskBoundaryOffset,
    surfaceLineVisible,
    headMaskingEnabled,
    leftHandMaskingEnabled,
    rightHandMaskingEnabled,
  );

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$InitialPoseStateImplCopyWith<_$InitialPoseStateImpl> get copyWith =>
      __$$InitialPoseStateImplCopyWithImpl<_$InitialPoseStateImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$InitialPoseStateImplToJson(this);
  }
}

abstract class _InitialPoseState implements InitialPoseState {
  const factory _InitialPoseState({
    final bool? leftEyeOpen,
    final bool? rightEyeOpen,
    final MouthState? mouthState,
    final bool? leftHandVisible,
    final bool? rightHandVisible,
    final CharacterTransform? leftHandTransform,
    final CharacterTransform? rightHandTransform,
    final CharacterTransform? headTransform,
    final double? surfaceLineOffset,
    final double? maskBoundaryOffset,
    final bool? surfaceLineVisible,
    final bool? headMaskingEnabled,
    final bool? leftHandMaskingEnabled,
    final bool? rightHandMaskingEnabled,
  }) = _$InitialPoseStateImpl;

  factory _InitialPoseState.fromJson(Map<String, dynamic> json) =
      _$InitialPoseStateImpl.fromJson;

  @override
  bool? get leftEyeOpen;
  @override
  bool? get rightEyeOpen;
  @override
  MouthState? get mouthState;
  @override
  bool? get leftHandVisible;
  @override
  bool? get rightHandVisible;
  @override
  CharacterTransform? get leftHandTransform;
  @override
  CharacterTransform? get rightHandTransform;
  @override
  CharacterTransform? get headTransform;
  @override
  double? get surfaceLineOffset;
  @override
  double? get maskBoundaryOffset;
  @override
  bool? get surfaceLineVisible;
  @override
  bool? get headMaskingEnabled;
  @override
  bool? get leftHandMaskingEnabled;
  @override
  bool? get rightHandMaskingEnabled;

  /// Create a copy of InitialPoseState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$InitialPoseStateImplCopyWith<_$InitialPoseStateImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

SequenceBooleanEvent _$SequenceBooleanEventFromJson(Map<String, dynamic> json) {
  return _SequenceBooleanEvent.fromJson(json);
}

/// @nodoc
mixin _$SequenceBooleanEvent {
  double get startTime => throw _privateConstructorUsedError;
  double? get endTime => throw _privateConstructorUsedError;
  bool get value => throw _privateConstructorUsedError;

  /// Serializes this SequenceBooleanEvent to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of SequenceBooleanEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $SequenceBooleanEventCopyWith<SequenceBooleanEvent> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $SequenceBooleanEventCopyWith<$Res> {
  factory $SequenceBooleanEventCopyWith(
    SequenceBooleanEvent value,
    $Res Function(SequenceBooleanEvent) then,
  ) = _$SequenceBooleanEventCopyWithImpl<$Res, SequenceBooleanEvent>;
  @useResult
  $Res call({double startTime, double? endTime, bool value});
}

/// @nodoc
class _$SequenceBooleanEventCopyWithImpl<
  $Res,
  $Val extends SequenceBooleanEvent
>
    implements $SequenceBooleanEventCopyWith<$Res> {
  _$SequenceBooleanEventCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of SequenceBooleanEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? value = null,
  }) {
    return _then(
      _value.copyWith(
            startTime: null == startTime
                ? _value.startTime
                : startTime // ignore: cast_nullable_to_non_nullable
                      as double,
            endTime: freezed == endTime
                ? _value.endTime
                : endTime // ignore: cast_nullable_to_non_nullable
                      as double?,
            value: null == value
                ? _value.value
                : value // ignore: cast_nullable_to_non_nullable
                      as bool,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$SequenceBooleanEventImplCopyWith<$Res>
    implements $SequenceBooleanEventCopyWith<$Res> {
  factory _$$SequenceBooleanEventImplCopyWith(
    _$SequenceBooleanEventImpl value,
    $Res Function(_$SequenceBooleanEventImpl) then,
  ) = __$$SequenceBooleanEventImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({double startTime, double? endTime, bool value});
}

/// @nodoc
class __$$SequenceBooleanEventImplCopyWithImpl<$Res>
    extends _$SequenceBooleanEventCopyWithImpl<$Res, _$SequenceBooleanEventImpl>
    implements _$$SequenceBooleanEventImplCopyWith<$Res> {
  __$$SequenceBooleanEventImplCopyWithImpl(
    _$SequenceBooleanEventImpl _value,
    $Res Function(_$SequenceBooleanEventImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of SequenceBooleanEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? value = null,
  }) {
    return _then(
      _$SequenceBooleanEventImpl(
        startTime: null == startTime
            ? _value.startTime
            : startTime // ignore: cast_nullable_to_non_nullable
                  as double,
        endTime: freezed == endTime
            ? _value.endTime
            : endTime // ignore: cast_nullable_to_non_nullable
                  as double?,
        value: null == value
            ? _value.value
            : value // ignore: cast_nullable_to_non_nullable
                  as bool,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$SequenceBooleanEventImpl implements _SequenceBooleanEvent {
  const _$SequenceBooleanEventImpl({
    required this.startTime,
    this.endTime,
    required this.value,
  });

  factory _$SequenceBooleanEventImpl.fromJson(Map<String, dynamic> json) =>
      _$$SequenceBooleanEventImplFromJson(json);

  @override
  final double startTime;
  @override
  final double? endTime;
  @override
  final bool value;

  @override
  String toString() {
    return 'SequenceBooleanEvent(startTime: $startTime, endTime: $endTime, value: $value)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$SequenceBooleanEventImpl &&
            (identical(other.startTime, startTime) ||
                other.startTime == startTime) &&
            (identical(other.endTime, endTime) || other.endTime == endTime) &&
            (identical(other.value, value) || other.value == value));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, startTime, endTime, value);

  /// Create a copy of SequenceBooleanEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$SequenceBooleanEventImplCopyWith<_$SequenceBooleanEventImpl>
  get copyWith =>
      __$$SequenceBooleanEventImplCopyWithImpl<_$SequenceBooleanEventImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$SequenceBooleanEventImplToJson(this);
  }
}

abstract class _SequenceBooleanEvent implements SequenceBooleanEvent {
  const factory _SequenceBooleanEvent({
    required final double startTime,
    final double? endTime,
    required final bool value,
  }) = _$SequenceBooleanEventImpl;

  factory _SequenceBooleanEvent.fromJson(Map<String, dynamic> json) =
      _$SequenceBooleanEventImpl.fromJson;

  @override
  double get startTime;
  @override
  double? get endTime;
  @override
  bool get value;

  /// Create a copy of SequenceBooleanEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$SequenceBooleanEventImplCopyWith<_$SequenceBooleanEventImpl>
  get copyWith => throw _privateConstructorUsedError;
}

SequenceMouthEvent _$SequenceMouthEventFromJson(Map<String, dynamic> json) {
  return _SequenceMouthEvent.fromJson(json);
}

/// @nodoc
mixin _$SequenceMouthEvent {
  double get startTime => throw _privateConstructorUsedError;
  double? get endTime => throw _privateConstructorUsedError;
  MouthState get mouthState => throw _privateConstructorUsedError;

  /// Serializes this SequenceMouthEvent to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of SequenceMouthEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $SequenceMouthEventCopyWith<SequenceMouthEvent> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $SequenceMouthEventCopyWith<$Res> {
  factory $SequenceMouthEventCopyWith(
    SequenceMouthEvent value,
    $Res Function(SequenceMouthEvent) then,
  ) = _$SequenceMouthEventCopyWithImpl<$Res, SequenceMouthEvent>;
  @useResult
  $Res call({double startTime, double? endTime, MouthState mouthState});
}

/// @nodoc
class _$SequenceMouthEventCopyWithImpl<$Res, $Val extends SequenceMouthEvent>
    implements $SequenceMouthEventCopyWith<$Res> {
  _$SequenceMouthEventCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of SequenceMouthEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? mouthState = null,
  }) {
    return _then(
      _value.copyWith(
            startTime: null == startTime
                ? _value.startTime
                : startTime // ignore: cast_nullable_to_non_nullable
                      as double,
            endTime: freezed == endTime
                ? _value.endTime
                : endTime // ignore: cast_nullable_to_non_nullable
                      as double?,
            mouthState: null == mouthState
                ? _value.mouthState
                : mouthState // ignore: cast_nullable_to_non_nullable
                      as MouthState,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$SequenceMouthEventImplCopyWith<$Res>
    implements $SequenceMouthEventCopyWith<$Res> {
  factory _$$SequenceMouthEventImplCopyWith(
    _$SequenceMouthEventImpl value,
    $Res Function(_$SequenceMouthEventImpl) then,
  ) = __$$SequenceMouthEventImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({double startTime, double? endTime, MouthState mouthState});
}

/// @nodoc
class __$$SequenceMouthEventImplCopyWithImpl<$Res>
    extends _$SequenceMouthEventCopyWithImpl<$Res, _$SequenceMouthEventImpl>
    implements _$$SequenceMouthEventImplCopyWith<$Res> {
  __$$SequenceMouthEventImplCopyWithImpl(
    _$SequenceMouthEventImpl _value,
    $Res Function(_$SequenceMouthEventImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of SequenceMouthEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? mouthState = null,
  }) {
    return _then(
      _$SequenceMouthEventImpl(
        startTime: null == startTime
            ? _value.startTime
            : startTime // ignore: cast_nullable_to_non_nullable
                  as double,
        endTime: freezed == endTime
            ? _value.endTime
            : endTime // ignore: cast_nullable_to_non_nullable
                  as double?,
        mouthState: null == mouthState
            ? _value.mouthState
            : mouthState // ignore: cast_nullable_to_non_nullable
                  as MouthState,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$SequenceMouthEventImpl implements _SequenceMouthEvent {
  const _$SequenceMouthEventImpl({
    required this.startTime,
    this.endTime,
    required this.mouthState,
  });

  factory _$SequenceMouthEventImpl.fromJson(Map<String, dynamic> json) =>
      _$$SequenceMouthEventImplFromJson(json);

  @override
  final double startTime;
  @override
  final double? endTime;
  @override
  final MouthState mouthState;

  @override
  String toString() {
    return 'SequenceMouthEvent(startTime: $startTime, endTime: $endTime, mouthState: $mouthState)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$SequenceMouthEventImpl &&
            (identical(other.startTime, startTime) ||
                other.startTime == startTime) &&
            (identical(other.endTime, endTime) || other.endTime == endTime) &&
            (identical(other.mouthState, mouthState) ||
                other.mouthState == mouthState));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, startTime, endTime, mouthState);

  /// Create a copy of SequenceMouthEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$SequenceMouthEventImplCopyWith<_$SequenceMouthEventImpl> get copyWith =>
      __$$SequenceMouthEventImplCopyWithImpl<_$SequenceMouthEventImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$SequenceMouthEventImplToJson(this);
  }
}

abstract class _SequenceMouthEvent implements SequenceMouthEvent {
  const factory _SequenceMouthEvent({
    required final double startTime,
    final double? endTime,
    required final MouthState mouthState,
  }) = _$SequenceMouthEventImpl;

  factory _SequenceMouthEvent.fromJson(Map<String, dynamic> json) =
      _$SequenceMouthEventImpl.fromJson;

  @override
  double get startTime;
  @override
  double? get endTime;
  @override
  MouthState get mouthState;

  /// Create a copy of SequenceMouthEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$SequenceMouthEventImplCopyWith<_$SequenceMouthEventImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

SequenceTransformEvent _$SequenceTransformEventFromJson(
  Map<String, dynamic> json,
) {
  return _SequenceTransformEvent.fromJson(json);
}

/// @nodoc
mixin _$SequenceTransformEvent {
  double get startTime => throw _privateConstructorUsedError;
  double? get endTime => throw _privateConstructorUsedError;
  CharacterTransform get targetTransform => throw _privateConstructorUsedError;

  /// Serializes this SequenceTransformEvent to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $SequenceTransformEventCopyWith<SequenceTransformEvent> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $SequenceTransformEventCopyWith<$Res> {
  factory $SequenceTransformEventCopyWith(
    SequenceTransformEvent value,
    $Res Function(SequenceTransformEvent) then,
  ) = _$SequenceTransformEventCopyWithImpl<$Res, SequenceTransformEvent>;
  @useResult
  $Res call({
    double startTime,
    double? endTime,
    CharacterTransform targetTransform,
  });

  $CharacterTransformCopyWith<$Res> get targetTransform;
}

/// @nodoc
class _$SequenceTransformEventCopyWithImpl<
  $Res,
  $Val extends SequenceTransformEvent
>
    implements $SequenceTransformEventCopyWith<$Res> {
  _$SequenceTransformEventCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? targetTransform = null,
  }) {
    return _then(
      _value.copyWith(
            startTime: null == startTime
                ? _value.startTime
                : startTime // ignore: cast_nullable_to_non_nullable
                      as double,
            endTime: freezed == endTime
                ? _value.endTime
                : endTime // ignore: cast_nullable_to_non_nullable
                      as double?,
            targetTransform: null == targetTransform
                ? _value.targetTransform
                : targetTransform // ignore: cast_nullable_to_non_nullable
                      as CharacterTransform,
          )
          as $Val,
    );
  }

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $CharacterTransformCopyWith<$Res> get targetTransform {
    return $CharacterTransformCopyWith<$Res>(_value.targetTransform, (value) {
      return _then(_value.copyWith(targetTransform: value) as $Val);
    });
  }
}

/// @nodoc
abstract class _$$SequenceTransformEventImplCopyWith<$Res>
    implements $SequenceTransformEventCopyWith<$Res> {
  factory _$$SequenceTransformEventImplCopyWith(
    _$SequenceTransformEventImpl value,
    $Res Function(_$SequenceTransformEventImpl) then,
  ) = __$$SequenceTransformEventImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({
    double startTime,
    double? endTime,
    CharacterTransform targetTransform,
  });

  @override
  $CharacterTransformCopyWith<$Res> get targetTransform;
}

/// @nodoc
class __$$SequenceTransformEventImplCopyWithImpl<$Res>
    extends
        _$SequenceTransformEventCopyWithImpl<$Res, _$SequenceTransformEventImpl>
    implements _$$SequenceTransformEventImplCopyWith<$Res> {
  __$$SequenceTransformEventImplCopyWithImpl(
    _$SequenceTransformEventImpl _value,
    $Res Function(_$SequenceTransformEventImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? targetTransform = null,
  }) {
    return _then(
      _$SequenceTransformEventImpl(
        startTime: null == startTime
            ? _value.startTime
            : startTime // ignore: cast_nullable_to_non_nullable
                  as double,
        endTime: freezed == endTime
            ? _value.endTime
            : endTime // ignore: cast_nullable_to_non_nullable
                  as double?,
        targetTransform: null == targetTransform
            ? _value.targetTransform
            : targetTransform // ignore: cast_nullable_to_non_nullable
                  as CharacterTransform,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$SequenceTransformEventImpl implements _SequenceTransformEvent {
  const _$SequenceTransformEventImpl({
    required this.startTime,
    this.endTime,
    required this.targetTransform,
  });

  factory _$SequenceTransformEventImpl.fromJson(Map<String, dynamic> json) =>
      _$$SequenceTransformEventImplFromJson(json);

  @override
  final double startTime;
  @override
  final double? endTime;
  @override
  final CharacterTransform targetTransform;

  @override
  String toString() {
    return 'SequenceTransformEvent(startTime: $startTime, endTime: $endTime, targetTransform: $targetTransform)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$SequenceTransformEventImpl &&
            (identical(other.startTime, startTime) ||
                other.startTime == startTime) &&
            (identical(other.endTime, endTime) || other.endTime == endTime) &&
            (identical(other.targetTransform, targetTransform) ||
                other.targetTransform == targetTransform));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, startTime, endTime, targetTransform);

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$SequenceTransformEventImplCopyWith<_$SequenceTransformEventImpl>
  get copyWith =>
      __$$SequenceTransformEventImplCopyWithImpl<_$SequenceTransformEventImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$SequenceTransformEventImplToJson(this);
  }
}

abstract class _SequenceTransformEvent implements SequenceTransformEvent {
  const factory _SequenceTransformEvent({
    required final double startTime,
    final double? endTime,
    required final CharacterTransform targetTransform,
  }) = _$SequenceTransformEventImpl;

  factory _SequenceTransformEvent.fromJson(Map<String, dynamic> json) =
      _$SequenceTransformEventImpl.fromJson;

  @override
  double get startTime;
  @override
  double? get endTime;
  @override
  CharacterTransform get targetTransform;

  /// Create a copy of SequenceTransformEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$SequenceTransformEventImplCopyWith<_$SequenceTransformEventImpl>
  get copyWith => throw _privateConstructorUsedError;
}

SequenceFloatEvent _$SequenceFloatEventFromJson(Map<String, dynamic> json) {
  return _SequenceFloatEvent.fromJson(json);
}

/// @nodoc
mixin _$SequenceFloatEvent {
  double get startTime => throw _privateConstructorUsedError;
  double? get endTime => throw _privateConstructorUsedError;
  double get targetValue => throw _privateConstructorUsedError;

  /// Serializes this SequenceFloatEvent to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of SequenceFloatEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $SequenceFloatEventCopyWith<SequenceFloatEvent> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $SequenceFloatEventCopyWith<$Res> {
  factory $SequenceFloatEventCopyWith(
    SequenceFloatEvent value,
    $Res Function(SequenceFloatEvent) then,
  ) = _$SequenceFloatEventCopyWithImpl<$Res, SequenceFloatEvent>;
  @useResult
  $Res call({double startTime, double? endTime, double targetValue});
}

/// @nodoc
class _$SequenceFloatEventCopyWithImpl<$Res, $Val extends SequenceFloatEvent>
    implements $SequenceFloatEventCopyWith<$Res> {
  _$SequenceFloatEventCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of SequenceFloatEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? targetValue = null,
  }) {
    return _then(
      _value.copyWith(
            startTime: null == startTime
                ? _value.startTime
                : startTime // ignore: cast_nullable_to_non_nullable
                      as double,
            endTime: freezed == endTime
                ? _value.endTime
                : endTime // ignore: cast_nullable_to_non_nullable
                      as double?,
            targetValue: null == targetValue
                ? _value.targetValue
                : targetValue // ignore: cast_nullable_to_non_nullable
                      as double,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$SequenceFloatEventImplCopyWith<$Res>
    implements $SequenceFloatEventCopyWith<$Res> {
  factory _$$SequenceFloatEventImplCopyWith(
    _$SequenceFloatEventImpl value,
    $Res Function(_$SequenceFloatEventImpl) then,
  ) = __$$SequenceFloatEventImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({double startTime, double? endTime, double targetValue});
}

/// @nodoc
class __$$SequenceFloatEventImplCopyWithImpl<$Res>
    extends _$SequenceFloatEventCopyWithImpl<$Res, _$SequenceFloatEventImpl>
    implements _$$SequenceFloatEventImplCopyWith<$Res> {
  __$$SequenceFloatEventImplCopyWithImpl(
    _$SequenceFloatEventImpl _value,
    $Res Function(_$SequenceFloatEventImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of SequenceFloatEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? targetValue = null,
  }) {
    return _then(
      _$SequenceFloatEventImpl(
        startTime: null == startTime
            ? _value.startTime
            : startTime // ignore: cast_nullable_to_non_nullable
                  as double,
        endTime: freezed == endTime
            ? _value.endTime
            : endTime // ignore: cast_nullable_to_non_nullable
                  as double?,
        targetValue: null == targetValue
            ? _value.targetValue
            : targetValue // ignore: cast_nullable_to_non_nullable
                  as double,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$SequenceFloatEventImpl implements _SequenceFloatEvent {
  const _$SequenceFloatEventImpl({
    required this.startTime,
    this.endTime,
    required this.targetValue,
  });

  factory _$SequenceFloatEventImpl.fromJson(Map<String, dynamic> json) =>
      _$$SequenceFloatEventImplFromJson(json);

  @override
  final double startTime;
  @override
  final double? endTime;
  @override
  final double targetValue;

  @override
  String toString() {
    return 'SequenceFloatEvent(startTime: $startTime, endTime: $endTime, targetValue: $targetValue)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$SequenceFloatEventImpl &&
            (identical(other.startTime, startTime) ||
                other.startTime == startTime) &&
            (identical(other.endTime, endTime) || other.endTime == endTime) &&
            (identical(other.targetValue, targetValue) ||
                other.targetValue == targetValue));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, startTime, endTime, targetValue);

  /// Create a copy of SequenceFloatEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$SequenceFloatEventImplCopyWith<_$SequenceFloatEventImpl> get copyWith =>
      __$$SequenceFloatEventImplCopyWithImpl<_$SequenceFloatEventImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$SequenceFloatEventImplToJson(this);
  }
}

abstract class _SequenceFloatEvent implements SequenceFloatEvent {
  const factory _SequenceFloatEvent({
    required final double startTime,
    final double? endTime,
    required final double targetValue,
  }) = _$SequenceFloatEventImpl;

  factory _SequenceFloatEvent.fromJson(Map<String, dynamic> json) =
      _$SequenceFloatEventImpl.fromJson;

  @override
  double get startTime;
  @override
  double? get endTime;
  @override
  double get targetValue;

  /// Create a copy of SequenceFloatEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$SequenceFloatEventImplCopyWith<_$SequenceFloatEventImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

SequenceSoundEvent _$SequenceSoundEventFromJson(Map<String, dynamic> json) {
  return _SequenceSoundEvent.fromJson(json);
}

/// @nodoc
mixin _$SequenceSoundEvent {
  double get startTime => throw _privateConstructorUsedError;
  double? get endTime => throw _privateConstructorUsedError;
  String get gcsUri => throw _privateConstructorUsedError;
  double get volume => throw _privateConstructorUsedError;

  /// Serializes this SequenceSoundEvent to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of SequenceSoundEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $SequenceSoundEventCopyWith<SequenceSoundEvent> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $SequenceSoundEventCopyWith<$Res> {
  factory $SequenceSoundEventCopyWith(
    SequenceSoundEvent value,
    $Res Function(SequenceSoundEvent) then,
  ) = _$SequenceSoundEventCopyWithImpl<$Res, SequenceSoundEvent>;
  @useResult
  $Res call({double startTime, double? endTime, String gcsUri, double volume});
}

/// @nodoc
class _$SequenceSoundEventCopyWithImpl<$Res, $Val extends SequenceSoundEvent>
    implements $SequenceSoundEventCopyWith<$Res> {
  _$SequenceSoundEventCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of SequenceSoundEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? gcsUri = null,
    Object? volume = null,
  }) {
    return _then(
      _value.copyWith(
            startTime: null == startTime
                ? _value.startTime
                : startTime // ignore: cast_nullable_to_non_nullable
                      as double,
            endTime: freezed == endTime
                ? _value.endTime
                : endTime // ignore: cast_nullable_to_non_nullable
                      as double?,
            gcsUri: null == gcsUri
                ? _value.gcsUri
                : gcsUri // ignore: cast_nullable_to_non_nullable
                      as String,
            volume: null == volume
                ? _value.volume
                : volume // ignore: cast_nullable_to_non_nullable
                      as double,
          )
          as $Val,
    );
  }
}

/// @nodoc
abstract class _$$SequenceSoundEventImplCopyWith<$Res>
    implements $SequenceSoundEventCopyWith<$Res> {
  factory _$$SequenceSoundEventImplCopyWith(
    _$SequenceSoundEventImpl value,
    $Res Function(_$SequenceSoundEventImpl) then,
  ) = __$$SequenceSoundEventImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({double startTime, double? endTime, String gcsUri, double volume});
}

/// @nodoc
class __$$SequenceSoundEventImplCopyWithImpl<$Res>
    extends _$SequenceSoundEventCopyWithImpl<$Res, _$SequenceSoundEventImpl>
    implements _$$SequenceSoundEventImplCopyWith<$Res> {
  __$$SequenceSoundEventImplCopyWithImpl(
    _$SequenceSoundEventImpl _value,
    $Res Function(_$SequenceSoundEventImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of SequenceSoundEvent
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? startTime = null,
    Object? endTime = freezed,
    Object? gcsUri = null,
    Object? volume = null,
  }) {
    return _then(
      _$SequenceSoundEventImpl(
        startTime: null == startTime
            ? _value.startTime
            : startTime // ignore: cast_nullable_to_non_nullable
                  as double,
        endTime: freezed == endTime
            ? _value.endTime
            : endTime // ignore: cast_nullable_to_non_nullable
                  as double?,
        gcsUri: null == gcsUri
            ? _value.gcsUri
            : gcsUri // ignore: cast_nullable_to_non_nullable
                  as String,
        volume: null == volume
            ? _value.volume
            : volume // ignore: cast_nullable_to_non_nullable
                  as double,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$SequenceSoundEventImpl implements _SequenceSoundEvent {
  const _$SequenceSoundEventImpl({
    required this.startTime,
    this.endTime,
    required this.gcsUri,
    this.volume = 1.0,
  });

  factory _$SequenceSoundEventImpl.fromJson(Map<String, dynamic> json) =>
      _$$SequenceSoundEventImplFromJson(json);

  @override
  final double startTime;
  @override
  final double? endTime;
  @override
  final String gcsUri;
  @override
  @JsonKey()
  final double volume;

  @override
  String toString() {
    return 'SequenceSoundEvent(startTime: $startTime, endTime: $endTime, gcsUri: $gcsUri, volume: $volume)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$SequenceSoundEventImpl &&
            (identical(other.startTime, startTime) ||
                other.startTime == startTime) &&
            (identical(other.endTime, endTime) || other.endTime == endTime) &&
            (identical(other.gcsUri, gcsUri) || other.gcsUri == gcsUri) &&
            (identical(other.volume, volume) || other.volume == volume));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, startTime, endTime, gcsUri, volume);

  /// Create a copy of SequenceSoundEvent
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$SequenceSoundEventImplCopyWith<_$SequenceSoundEventImpl> get copyWith =>
      __$$SequenceSoundEventImplCopyWithImpl<_$SequenceSoundEventImpl>(
        this,
        _$identity,
      );

  @override
  Map<String, dynamic> toJson() {
    return _$$SequenceSoundEventImplToJson(this);
  }
}

abstract class _SequenceSoundEvent implements SequenceSoundEvent {
  const factory _SequenceSoundEvent({
    required final double startTime,
    final double? endTime,
    required final String gcsUri,
    final double volume,
  }) = _$SequenceSoundEventImpl;

  factory _SequenceSoundEvent.fromJson(Map<String, dynamic> json) =
      _$SequenceSoundEventImpl.fromJson;

  @override
  double get startTime;
  @override
  double? get endTime;
  @override
  String get gcsUri;
  @override
  double get volume;

  /// Create a copy of SequenceSoundEvent
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$SequenceSoundEventImplCopyWith<_$SequenceSoundEventImpl> get copyWith =>
      throw _privateConstructorUsedError;
}

PosableCharacterSequence _$PosableCharacterSequenceFromJson(
  Map<String, dynamic> json,
) {
  return _PosableCharacterSequence.fromJson(json);
}

/// @nodoc
mixin _$PosableCharacterSequence {
  String? get key => throw _privateConstructorUsedError;
  InitialPoseState? get initialPose => throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceLeftEyeOpen =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceRightEyeOpen =>
      throw _privateConstructorUsedError;
  List<SequenceMouthEvent> get sequenceMouthState =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceLeftHandVisible =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceRightHandVisible =>
      throw _privateConstructorUsedError;
  List<SequenceTransformEvent> get sequenceLeftHandTransform =>
      throw _privateConstructorUsedError;
  List<SequenceTransformEvent> get sequenceRightHandTransform =>
      throw _privateConstructorUsedError;
  List<SequenceTransformEvent> get sequenceHeadTransform =>
      throw _privateConstructorUsedError;
  List<SequenceFloatEvent> get sequenceSurfaceLineOffset =>
      throw _privateConstructorUsedError;
  List<SequenceFloatEvent> get sequenceMaskBoundaryOffset =>
      throw _privateConstructorUsedError;
  List<SequenceSoundEvent> get sequenceSoundEvents =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceSurfaceLineVisible =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceHeadMaskingEnabled =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceLeftHandMaskingEnabled =>
      throw _privateConstructorUsedError;
  List<SequenceBooleanEvent> get sequenceRightHandMaskingEnabled =>
      throw _privateConstructorUsedError;

  /// Serializes this PosableCharacterSequence to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $PosableCharacterSequenceCopyWith<PosableCharacterSequence> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $PosableCharacterSequenceCopyWith<$Res> {
  factory $PosableCharacterSequenceCopyWith(
    PosableCharacterSequence value,
    $Res Function(PosableCharacterSequence) then,
  ) = _$PosableCharacterSequenceCopyWithImpl<$Res, PosableCharacterSequence>;
  @useResult
  $Res call({
    String? key,
    InitialPoseState? initialPose,
    List<SequenceBooleanEvent> sequenceLeftEyeOpen,
    List<SequenceBooleanEvent> sequenceRightEyeOpen,
    List<SequenceMouthEvent> sequenceMouthState,
    List<SequenceBooleanEvent> sequenceLeftHandVisible,
    List<SequenceBooleanEvent> sequenceRightHandVisible,
    List<SequenceTransformEvent> sequenceLeftHandTransform,
    List<SequenceTransformEvent> sequenceRightHandTransform,
    List<SequenceTransformEvent> sequenceHeadTransform,
    List<SequenceFloatEvent> sequenceSurfaceLineOffset,
    List<SequenceFloatEvent> sequenceMaskBoundaryOffset,
    List<SequenceSoundEvent> sequenceSoundEvents,
    List<SequenceBooleanEvent> sequenceSurfaceLineVisible,
    List<SequenceBooleanEvent> sequenceHeadMaskingEnabled,
    List<SequenceBooleanEvent> sequenceLeftHandMaskingEnabled,
    List<SequenceBooleanEvent> sequenceRightHandMaskingEnabled,
  });

  $InitialPoseStateCopyWith<$Res>? get initialPose;
}

/// @nodoc
class _$PosableCharacterSequenceCopyWithImpl<
  $Res,
  $Val extends PosableCharacterSequence
>
    implements $PosableCharacterSequenceCopyWith<$Res> {
  _$PosableCharacterSequenceCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? key = freezed,
    Object? initialPose = freezed,
    Object? sequenceLeftEyeOpen = null,
    Object? sequenceRightEyeOpen = null,
    Object? sequenceMouthState = null,
    Object? sequenceLeftHandVisible = null,
    Object? sequenceRightHandVisible = null,
    Object? sequenceLeftHandTransform = null,
    Object? sequenceRightHandTransform = null,
    Object? sequenceHeadTransform = null,
    Object? sequenceSurfaceLineOffset = null,
    Object? sequenceMaskBoundaryOffset = null,
    Object? sequenceSoundEvents = null,
    Object? sequenceSurfaceLineVisible = null,
    Object? sequenceHeadMaskingEnabled = null,
    Object? sequenceLeftHandMaskingEnabled = null,
    Object? sequenceRightHandMaskingEnabled = null,
  }) {
    return _then(
      _value.copyWith(
            key: freezed == key
                ? _value.key
                : key // ignore: cast_nullable_to_non_nullable
                      as String?,
            initialPose: freezed == initialPose
                ? _value.initialPose
                : initialPose // ignore: cast_nullable_to_non_nullable
                      as InitialPoseState?,
            sequenceLeftEyeOpen: null == sequenceLeftEyeOpen
                ? _value.sequenceLeftEyeOpen
                : sequenceLeftEyeOpen // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceRightEyeOpen: null == sequenceRightEyeOpen
                ? _value.sequenceRightEyeOpen
                : sequenceRightEyeOpen // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceMouthState: null == sequenceMouthState
                ? _value.sequenceMouthState
                : sequenceMouthState // ignore: cast_nullable_to_non_nullable
                      as List<SequenceMouthEvent>,
            sequenceLeftHandVisible: null == sequenceLeftHandVisible
                ? _value.sequenceLeftHandVisible
                : sequenceLeftHandVisible // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceRightHandVisible: null == sequenceRightHandVisible
                ? _value.sequenceRightHandVisible
                : sequenceRightHandVisible // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceLeftHandTransform: null == sequenceLeftHandTransform
                ? _value.sequenceLeftHandTransform
                : sequenceLeftHandTransform // ignore: cast_nullable_to_non_nullable
                      as List<SequenceTransformEvent>,
            sequenceRightHandTransform: null == sequenceRightHandTransform
                ? _value.sequenceRightHandTransform
                : sequenceRightHandTransform // ignore: cast_nullable_to_non_nullable
                      as List<SequenceTransformEvent>,
            sequenceHeadTransform: null == sequenceHeadTransform
                ? _value.sequenceHeadTransform
                : sequenceHeadTransform // ignore: cast_nullable_to_non_nullable
                      as List<SequenceTransformEvent>,
            sequenceSurfaceLineOffset: null == sequenceSurfaceLineOffset
                ? _value.sequenceSurfaceLineOffset
                : sequenceSurfaceLineOffset // ignore: cast_nullable_to_non_nullable
                      as List<SequenceFloatEvent>,
            sequenceMaskBoundaryOffset: null == sequenceMaskBoundaryOffset
                ? _value.sequenceMaskBoundaryOffset
                : sequenceMaskBoundaryOffset // ignore: cast_nullable_to_non_nullable
                      as List<SequenceFloatEvent>,
            sequenceSoundEvents: null == sequenceSoundEvents
                ? _value.sequenceSoundEvents
                : sequenceSoundEvents // ignore: cast_nullable_to_non_nullable
                      as List<SequenceSoundEvent>,
            sequenceSurfaceLineVisible: null == sequenceSurfaceLineVisible
                ? _value.sequenceSurfaceLineVisible
                : sequenceSurfaceLineVisible // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceHeadMaskingEnabled: null == sequenceHeadMaskingEnabled
                ? _value.sequenceHeadMaskingEnabled
                : sequenceHeadMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceLeftHandMaskingEnabled:
                null == sequenceLeftHandMaskingEnabled
                ? _value.sequenceLeftHandMaskingEnabled
                : sequenceLeftHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
            sequenceRightHandMaskingEnabled:
                null == sequenceRightHandMaskingEnabled
                ? _value.sequenceRightHandMaskingEnabled
                : sequenceRightHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                      as List<SequenceBooleanEvent>,
          )
          as $Val,
    );
  }

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $InitialPoseStateCopyWith<$Res>? get initialPose {
    if (_value.initialPose == null) {
      return null;
    }

    return $InitialPoseStateCopyWith<$Res>(_value.initialPose!, (value) {
      return _then(_value.copyWith(initialPose: value) as $Val);
    });
  }
}

/// @nodoc
abstract class _$$PosableCharacterSequenceImplCopyWith<$Res>
    implements $PosableCharacterSequenceCopyWith<$Res> {
  factory _$$PosableCharacterSequenceImplCopyWith(
    _$PosableCharacterSequenceImpl value,
    $Res Function(_$PosableCharacterSequenceImpl) then,
  ) = __$$PosableCharacterSequenceImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call({
    String? key,
    InitialPoseState? initialPose,
    List<SequenceBooleanEvent> sequenceLeftEyeOpen,
    List<SequenceBooleanEvent> sequenceRightEyeOpen,
    List<SequenceMouthEvent> sequenceMouthState,
    List<SequenceBooleanEvent> sequenceLeftHandVisible,
    List<SequenceBooleanEvent> sequenceRightHandVisible,
    List<SequenceTransformEvent> sequenceLeftHandTransform,
    List<SequenceTransformEvent> sequenceRightHandTransform,
    List<SequenceTransformEvent> sequenceHeadTransform,
    List<SequenceFloatEvent> sequenceSurfaceLineOffset,
    List<SequenceFloatEvent> sequenceMaskBoundaryOffset,
    List<SequenceSoundEvent> sequenceSoundEvents,
    List<SequenceBooleanEvent> sequenceSurfaceLineVisible,
    List<SequenceBooleanEvent> sequenceHeadMaskingEnabled,
    List<SequenceBooleanEvent> sequenceLeftHandMaskingEnabled,
    List<SequenceBooleanEvent> sequenceRightHandMaskingEnabled,
  });

  @override
  $InitialPoseStateCopyWith<$Res>? get initialPose;
}

/// @nodoc
class __$$PosableCharacterSequenceImplCopyWithImpl<$Res>
    extends
        _$PosableCharacterSequenceCopyWithImpl<
          $Res,
          _$PosableCharacterSequenceImpl
        >
    implements _$$PosableCharacterSequenceImplCopyWith<$Res> {
  __$$PosableCharacterSequenceImplCopyWithImpl(
    _$PosableCharacterSequenceImpl _value,
    $Res Function(_$PosableCharacterSequenceImpl) _then,
  ) : super(_value, _then);

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? key = freezed,
    Object? initialPose = freezed,
    Object? sequenceLeftEyeOpen = null,
    Object? sequenceRightEyeOpen = null,
    Object? sequenceMouthState = null,
    Object? sequenceLeftHandVisible = null,
    Object? sequenceRightHandVisible = null,
    Object? sequenceLeftHandTransform = null,
    Object? sequenceRightHandTransform = null,
    Object? sequenceHeadTransform = null,
    Object? sequenceSurfaceLineOffset = null,
    Object? sequenceMaskBoundaryOffset = null,
    Object? sequenceSoundEvents = null,
    Object? sequenceSurfaceLineVisible = null,
    Object? sequenceHeadMaskingEnabled = null,
    Object? sequenceLeftHandMaskingEnabled = null,
    Object? sequenceRightHandMaskingEnabled = null,
  }) {
    return _then(
      _$PosableCharacterSequenceImpl(
        key: freezed == key
            ? _value.key
            : key // ignore: cast_nullable_to_non_nullable
                  as String?,
        initialPose: freezed == initialPose
            ? _value.initialPose
            : initialPose // ignore: cast_nullable_to_non_nullable
                  as InitialPoseState?,
        sequenceLeftEyeOpen: null == sequenceLeftEyeOpen
            ? _value._sequenceLeftEyeOpen
            : sequenceLeftEyeOpen // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceRightEyeOpen: null == sequenceRightEyeOpen
            ? _value._sequenceRightEyeOpen
            : sequenceRightEyeOpen // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceMouthState: null == sequenceMouthState
            ? _value._sequenceMouthState
            : sequenceMouthState // ignore: cast_nullable_to_non_nullable
                  as List<SequenceMouthEvent>,
        sequenceLeftHandVisible: null == sequenceLeftHandVisible
            ? _value._sequenceLeftHandVisible
            : sequenceLeftHandVisible // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceRightHandVisible: null == sequenceRightHandVisible
            ? _value._sequenceRightHandVisible
            : sequenceRightHandVisible // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceLeftHandTransform: null == sequenceLeftHandTransform
            ? _value._sequenceLeftHandTransform
            : sequenceLeftHandTransform // ignore: cast_nullable_to_non_nullable
                  as List<SequenceTransformEvent>,
        sequenceRightHandTransform: null == sequenceRightHandTransform
            ? _value._sequenceRightHandTransform
            : sequenceRightHandTransform // ignore: cast_nullable_to_non_nullable
                  as List<SequenceTransformEvent>,
        sequenceHeadTransform: null == sequenceHeadTransform
            ? _value._sequenceHeadTransform
            : sequenceHeadTransform // ignore: cast_nullable_to_non_nullable
                  as List<SequenceTransformEvent>,
        sequenceSurfaceLineOffset: null == sequenceSurfaceLineOffset
            ? _value._sequenceSurfaceLineOffset
            : sequenceSurfaceLineOffset // ignore: cast_nullable_to_non_nullable
                  as List<SequenceFloatEvent>,
        sequenceMaskBoundaryOffset: null == sequenceMaskBoundaryOffset
            ? _value._sequenceMaskBoundaryOffset
            : sequenceMaskBoundaryOffset // ignore: cast_nullable_to_non_nullable
                  as List<SequenceFloatEvent>,
        sequenceSoundEvents: null == sequenceSoundEvents
            ? _value._sequenceSoundEvents
            : sequenceSoundEvents // ignore: cast_nullable_to_non_nullable
                  as List<SequenceSoundEvent>,
        sequenceSurfaceLineVisible: null == sequenceSurfaceLineVisible
            ? _value._sequenceSurfaceLineVisible
            : sequenceSurfaceLineVisible // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceHeadMaskingEnabled: null == sequenceHeadMaskingEnabled
            ? _value._sequenceHeadMaskingEnabled
            : sequenceHeadMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceLeftHandMaskingEnabled: null == sequenceLeftHandMaskingEnabled
            ? _value._sequenceLeftHandMaskingEnabled
            : sequenceLeftHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
        sequenceRightHandMaskingEnabled: null == sequenceRightHandMaskingEnabled
            ? _value._sequenceRightHandMaskingEnabled
            : sequenceRightHandMaskingEnabled // ignore: cast_nullable_to_non_nullable
                  as List<SequenceBooleanEvent>,
      ),
    );
  }
}

/// @nodoc

@JsonSerializable(fieldRename: FieldRename.snake)
class _$PosableCharacterSequenceImpl implements _PosableCharacterSequence {
  const _$PosableCharacterSequenceImpl({
    this.key,
    this.initialPose,
    final List<SequenceBooleanEvent> sequenceLeftEyeOpen = const [],
    final List<SequenceBooleanEvent> sequenceRightEyeOpen = const [],
    final List<SequenceMouthEvent> sequenceMouthState = const [],
    final List<SequenceBooleanEvent> sequenceLeftHandVisible = const [],
    final List<SequenceBooleanEvent> sequenceRightHandVisible = const [],
    final List<SequenceTransformEvent> sequenceLeftHandTransform = const [],
    final List<SequenceTransformEvent> sequenceRightHandTransform = const [],
    final List<SequenceTransformEvent> sequenceHeadTransform = const [],
    final List<SequenceFloatEvent> sequenceSurfaceLineOffset = const [],
    final List<SequenceFloatEvent> sequenceMaskBoundaryOffset = const [],
    final List<SequenceSoundEvent> sequenceSoundEvents = const [],
    final List<SequenceBooleanEvent> sequenceSurfaceLineVisible = const [],
    final List<SequenceBooleanEvent> sequenceHeadMaskingEnabled = const [],
    final List<SequenceBooleanEvent> sequenceLeftHandMaskingEnabled = const [],
    final List<SequenceBooleanEvent> sequenceRightHandMaskingEnabled = const [],
  }) : _sequenceLeftEyeOpen = sequenceLeftEyeOpen,
       _sequenceRightEyeOpen = sequenceRightEyeOpen,
       _sequenceMouthState = sequenceMouthState,
       _sequenceLeftHandVisible = sequenceLeftHandVisible,
       _sequenceRightHandVisible = sequenceRightHandVisible,
       _sequenceLeftHandTransform = sequenceLeftHandTransform,
       _sequenceRightHandTransform = sequenceRightHandTransform,
       _sequenceHeadTransform = sequenceHeadTransform,
       _sequenceSurfaceLineOffset = sequenceSurfaceLineOffset,
       _sequenceMaskBoundaryOffset = sequenceMaskBoundaryOffset,
       _sequenceSoundEvents = sequenceSoundEvents,
       _sequenceSurfaceLineVisible = sequenceSurfaceLineVisible,
       _sequenceHeadMaskingEnabled = sequenceHeadMaskingEnabled,
       _sequenceLeftHandMaskingEnabled = sequenceLeftHandMaskingEnabled,
       _sequenceRightHandMaskingEnabled = sequenceRightHandMaskingEnabled;

  factory _$PosableCharacterSequenceImpl.fromJson(Map<String, dynamic> json) =>
      _$$PosableCharacterSequenceImplFromJson(json);

  @override
  final String? key;
  @override
  final InitialPoseState? initialPose;
  final List<SequenceBooleanEvent> _sequenceLeftEyeOpen;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceLeftEyeOpen {
    if (_sequenceLeftEyeOpen is EqualUnmodifiableListView)
      return _sequenceLeftEyeOpen;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceLeftEyeOpen);
  }

  final List<SequenceBooleanEvent> _sequenceRightEyeOpen;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceRightEyeOpen {
    if (_sequenceRightEyeOpen is EqualUnmodifiableListView)
      return _sequenceRightEyeOpen;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceRightEyeOpen);
  }

  final List<SequenceMouthEvent> _sequenceMouthState;
  @override
  @JsonKey()
  List<SequenceMouthEvent> get sequenceMouthState {
    if (_sequenceMouthState is EqualUnmodifiableListView)
      return _sequenceMouthState;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceMouthState);
  }

  final List<SequenceBooleanEvent> _sequenceLeftHandVisible;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceLeftHandVisible {
    if (_sequenceLeftHandVisible is EqualUnmodifiableListView)
      return _sequenceLeftHandVisible;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceLeftHandVisible);
  }

  final List<SequenceBooleanEvent> _sequenceRightHandVisible;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceRightHandVisible {
    if (_sequenceRightHandVisible is EqualUnmodifiableListView)
      return _sequenceRightHandVisible;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceRightHandVisible);
  }

  final List<SequenceTransformEvent> _sequenceLeftHandTransform;
  @override
  @JsonKey()
  List<SequenceTransformEvent> get sequenceLeftHandTransform {
    if (_sequenceLeftHandTransform is EqualUnmodifiableListView)
      return _sequenceLeftHandTransform;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceLeftHandTransform);
  }

  final List<SequenceTransformEvent> _sequenceRightHandTransform;
  @override
  @JsonKey()
  List<SequenceTransformEvent> get sequenceRightHandTransform {
    if (_sequenceRightHandTransform is EqualUnmodifiableListView)
      return _sequenceRightHandTransform;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceRightHandTransform);
  }

  final List<SequenceTransformEvent> _sequenceHeadTransform;
  @override
  @JsonKey()
  List<SequenceTransformEvent> get sequenceHeadTransform {
    if (_sequenceHeadTransform is EqualUnmodifiableListView)
      return _sequenceHeadTransform;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceHeadTransform);
  }

  final List<SequenceFloatEvent> _sequenceSurfaceLineOffset;
  @override
  @JsonKey()
  List<SequenceFloatEvent> get sequenceSurfaceLineOffset {
    if (_sequenceSurfaceLineOffset is EqualUnmodifiableListView)
      return _sequenceSurfaceLineOffset;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceSurfaceLineOffset);
  }

  final List<SequenceFloatEvent> _sequenceMaskBoundaryOffset;
  @override
  @JsonKey()
  List<SequenceFloatEvent> get sequenceMaskBoundaryOffset {
    if (_sequenceMaskBoundaryOffset is EqualUnmodifiableListView)
      return _sequenceMaskBoundaryOffset;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceMaskBoundaryOffset);
  }

  final List<SequenceSoundEvent> _sequenceSoundEvents;
  @override
  @JsonKey()
  List<SequenceSoundEvent> get sequenceSoundEvents {
    if (_sequenceSoundEvents is EqualUnmodifiableListView)
      return _sequenceSoundEvents;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceSoundEvents);
  }

  final List<SequenceBooleanEvent> _sequenceSurfaceLineVisible;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceSurfaceLineVisible {
    if (_sequenceSurfaceLineVisible is EqualUnmodifiableListView)
      return _sequenceSurfaceLineVisible;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceSurfaceLineVisible);
  }

  final List<SequenceBooleanEvent> _sequenceHeadMaskingEnabled;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceHeadMaskingEnabled {
    if (_sequenceHeadMaskingEnabled is EqualUnmodifiableListView)
      return _sequenceHeadMaskingEnabled;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceHeadMaskingEnabled);
  }

  final List<SequenceBooleanEvent> _sequenceLeftHandMaskingEnabled;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceLeftHandMaskingEnabled {
    if (_sequenceLeftHandMaskingEnabled is EqualUnmodifiableListView)
      return _sequenceLeftHandMaskingEnabled;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceLeftHandMaskingEnabled);
  }

  final List<SequenceBooleanEvent> _sequenceRightHandMaskingEnabled;
  @override
  @JsonKey()
  List<SequenceBooleanEvent> get sequenceRightHandMaskingEnabled {
    if (_sequenceRightHandMaskingEnabled is EqualUnmodifiableListView)
      return _sequenceRightHandMaskingEnabled;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_sequenceRightHandMaskingEnabled);
  }

  @override
  String toString() {
    return 'PosableCharacterSequence(key: $key, initialPose: $initialPose, sequenceLeftEyeOpen: $sequenceLeftEyeOpen, sequenceRightEyeOpen: $sequenceRightEyeOpen, sequenceMouthState: $sequenceMouthState, sequenceLeftHandVisible: $sequenceLeftHandVisible, sequenceRightHandVisible: $sequenceRightHandVisible, sequenceLeftHandTransform: $sequenceLeftHandTransform, sequenceRightHandTransform: $sequenceRightHandTransform, sequenceHeadTransform: $sequenceHeadTransform, sequenceSurfaceLineOffset: $sequenceSurfaceLineOffset, sequenceMaskBoundaryOffset: $sequenceMaskBoundaryOffset, sequenceSoundEvents: $sequenceSoundEvents, sequenceSurfaceLineVisible: $sequenceSurfaceLineVisible, sequenceHeadMaskingEnabled: $sequenceHeadMaskingEnabled, sequenceLeftHandMaskingEnabled: $sequenceLeftHandMaskingEnabled, sequenceRightHandMaskingEnabled: $sequenceRightHandMaskingEnabled)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$PosableCharacterSequenceImpl &&
            (identical(other.key, key) || other.key == key) &&
            (identical(other.initialPose, initialPose) ||
                other.initialPose == initialPose) &&
            const DeepCollectionEquality().equals(
              other._sequenceLeftEyeOpen,
              _sequenceLeftEyeOpen,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceRightEyeOpen,
              _sequenceRightEyeOpen,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceMouthState,
              _sequenceMouthState,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceLeftHandVisible,
              _sequenceLeftHandVisible,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceRightHandVisible,
              _sequenceRightHandVisible,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceLeftHandTransform,
              _sequenceLeftHandTransform,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceRightHandTransform,
              _sequenceRightHandTransform,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceHeadTransform,
              _sequenceHeadTransform,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceSurfaceLineOffset,
              _sequenceSurfaceLineOffset,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceMaskBoundaryOffset,
              _sequenceMaskBoundaryOffset,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceSoundEvents,
              _sequenceSoundEvents,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceSurfaceLineVisible,
              _sequenceSurfaceLineVisible,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceHeadMaskingEnabled,
              _sequenceHeadMaskingEnabled,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceLeftHandMaskingEnabled,
              _sequenceLeftHandMaskingEnabled,
            ) &&
            const DeepCollectionEquality().equals(
              other._sequenceRightHandMaskingEnabled,
              _sequenceRightHandMaskingEnabled,
            ));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
    runtimeType,
    key,
    initialPose,
    const DeepCollectionEquality().hash(_sequenceLeftEyeOpen),
    const DeepCollectionEquality().hash(_sequenceRightEyeOpen),
    const DeepCollectionEquality().hash(_sequenceMouthState),
    const DeepCollectionEquality().hash(_sequenceLeftHandVisible),
    const DeepCollectionEquality().hash(_sequenceRightHandVisible),
    const DeepCollectionEquality().hash(_sequenceLeftHandTransform),
    const DeepCollectionEquality().hash(_sequenceRightHandTransform),
    const DeepCollectionEquality().hash(_sequenceHeadTransform),
    const DeepCollectionEquality().hash(_sequenceSurfaceLineOffset),
    const DeepCollectionEquality().hash(_sequenceMaskBoundaryOffset),
    const DeepCollectionEquality().hash(_sequenceSoundEvents),
    const DeepCollectionEquality().hash(_sequenceSurfaceLineVisible),
    const DeepCollectionEquality().hash(_sequenceHeadMaskingEnabled),
    const DeepCollectionEquality().hash(_sequenceLeftHandMaskingEnabled),
    const DeepCollectionEquality().hash(_sequenceRightHandMaskingEnabled),
  );

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$PosableCharacterSequenceImplCopyWith<_$PosableCharacterSequenceImpl>
  get copyWith =>
      __$$PosableCharacterSequenceImplCopyWithImpl<
        _$PosableCharacterSequenceImpl
      >(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$$PosableCharacterSequenceImplToJson(this);
  }
}

abstract class _PosableCharacterSequence implements PosableCharacterSequence {
  const factory _PosableCharacterSequence({
    final String? key,
    final InitialPoseState? initialPose,
    final List<SequenceBooleanEvent> sequenceLeftEyeOpen,
    final List<SequenceBooleanEvent> sequenceRightEyeOpen,
    final List<SequenceMouthEvent> sequenceMouthState,
    final List<SequenceBooleanEvent> sequenceLeftHandVisible,
    final List<SequenceBooleanEvent> sequenceRightHandVisible,
    final List<SequenceTransformEvent> sequenceLeftHandTransform,
    final List<SequenceTransformEvent> sequenceRightHandTransform,
    final List<SequenceTransformEvent> sequenceHeadTransform,
    final List<SequenceFloatEvent> sequenceSurfaceLineOffset,
    final List<SequenceFloatEvent> sequenceMaskBoundaryOffset,
    final List<SequenceSoundEvent> sequenceSoundEvents,
    final List<SequenceBooleanEvent> sequenceSurfaceLineVisible,
    final List<SequenceBooleanEvent> sequenceHeadMaskingEnabled,
    final List<SequenceBooleanEvent> sequenceLeftHandMaskingEnabled,
    final List<SequenceBooleanEvent> sequenceRightHandMaskingEnabled,
  }) = _$PosableCharacterSequenceImpl;

  factory _PosableCharacterSequence.fromJson(Map<String, dynamic> json) =
      _$PosableCharacterSequenceImpl.fromJson;

  @override
  String? get key;
  @override
  InitialPoseState? get initialPose;
  @override
  List<SequenceBooleanEvent> get sequenceLeftEyeOpen;
  @override
  List<SequenceBooleanEvent> get sequenceRightEyeOpen;
  @override
  List<SequenceMouthEvent> get sequenceMouthState;
  @override
  List<SequenceBooleanEvent> get sequenceLeftHandVisible;
  @override
  List<SequenceBooleanEvent> get sequenceRightHandVisible;
  @override
  List<SequenceTransformEvent> get sequenceLeftHandTransform;
  @override
  List<SequenceTransformEvent> get sequenceRightHandTransform;
  @override
  List<SequenceTransformEvent> get sequenceHeadTransform;
  @override
  List<SequenceFloatEvent> get sequenceSurfaceLineOffset;
  @override
  List<SequenceFloatEvent> get sequenceMaskBoundaryOffset;
  @override
  List<SequenceSoundEvent> get sequenceSoundEvents;
  @override
  List<SequenceBooleanEvent> get sequenceSurfaceLineVisible;
  @override
  List<SequenceBooleanEvent> get sequenceHeadMaskingEnabled;
  @override
  List<SequenceBooleanEvent> get sequenceLeftHandMaskingEnabled;
  @override
  List<SequenceBooleanEvent> get sequenceRightHandMaskingEnabled;

  /// Create a copy of PosableCharacterSequence
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$PosableCharacterSequenceImplCopyWith<_$PosableCharacterSequenceImpl>
  get copyWith => throw _privateConstructorUsedError;
}
