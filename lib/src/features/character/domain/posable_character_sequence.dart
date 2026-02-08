import 'package:freezed_annotation/freezed_annotation.dart';

part 'posable_character_sequence.freezed.dart';
part 'posable_character_sequence.g.dart';

enum MouthState {
  @JsonValue('CLOSED')
  closed,
  @JsonValue('OPEN')
  open,
  @JsonValue('O')
  o,
}

@freezed
class CharacterTransform with _$CharacterTransform {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory CharacterTransform({
    @Default(0.0) double translateX,
    @Default(0.0) double translateY,
    @Default(1.0) double scaleX,
    @Default(1.0) double scaleY,
  }) = _CharacterTransform;

  factory CharacterTransform.fromJson(Map<String, dynamic> json) =>
      _$CharacterTransformFromJson(json);
}

@freezed
class SequenceBooleanEvent with _$SequenceBooleanEvent {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SequenceBooleanEvent({
    required double startTime,
    double? endTime,
    required bool value,
  }) = _SequenceBooleanEvent;

  factory SequenceBooleanEvent.fromJson(Map<String, dynamic> json) =>
      _$SequenceBooleanEventFromJson(json);
}

@freezed
class SequenceMouthEvent with _$SequenceMouthEvent {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SequenceMouthEvent({
    required double startTime,
    double? endTime,
    required MouthState mouthState,
  }) = _SequenceMouthEvent;

  factory SequenceMouthEvent.fromJson(Map<String, dynamic> json) =>
      _$SequenceMouthEventFromJson(json);
}

@freezed
class SequenceTransformEvent with _$SequenceTransformEvent {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SequenceTransformEvent({
    required double startTime,
    double? endTime,
    required CharacterTransform targetTransform,
  }) = _SequenceTransformEvent;

  factory SequenceTransformEvent.fromJson(Map<String, dynamic> json) =>
      _$SequenceTransformEventFromJson(json);
}

@freezed
class SequenceSoundEvent with _$SequenceSoundEvent {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SequenceSoundEvent({
    required double startTime,
    double? endTime,
    required String gcsUri,
    @Default(1.0) double volume,
  }) = _SequenceSoundEvent;

  factory SequenceSoundEvent.fromJson(Map<String, dynamic> json) =>
      _$SequenceSoundEventFromJson(json);
}

@freezed
class PosableCharacterSequence with _$PosableCharacterSequence {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory PosableCharacterSequence({
    String? key,
    @Default([]) List<SequenceBooleanEvent> sequenceLeftEyeOpen,
    @Default([]) List<SequenceBooleanEvent> sequenceRightEyeOpen,
    @Default([]) List<SequenceMouthEvent> sequenceMouthState,
    @Default([]) List<SequenceBooleanEvent> sequenceLeftHandVisible,
    @Default([]) List<SequenceBooleanEvent> sequenceRightHandVisible,
    @Default([]) List<SequenceTransformEvent> sequenceLeftHandTransform,
    @Default([]) List<SequenceTransformEvent> sequenceRightHandTransform,
    @Default([]) List<SequenceTransformEvent> sequenceHeadTransform,
    @Default([]) List<SequenceSoundEvent> sequenceSoundEvents,
  }) = _PosableCharacterSequence;

  factory PosableCharacterSequence.fromJson(Map<String, dynamic> json) =>
      _$PosableCharacterSequenceFromJson(json);
}
