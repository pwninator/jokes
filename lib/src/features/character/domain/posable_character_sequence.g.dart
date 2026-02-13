// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'posable_character_sequence.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_$CharacterTransformImpl _$$CharacterTransformImplFromJson(
  Map<String, dynamic> json,
) => _$CharacterTransformImpl(
  translateX: (json['translate_x'] as num?)?.toDouble() ?? 0.0,
  translateY: (json['translate_y'] as num?)?.toDouble() ?? 0.0,
  scaleX: (json['scale_x'] as num?)?.toDouble() ?? 1.0,
  scaleY: (json['scale_y'] as num?)?.toDouble() ?? 1.0,
);

Map<String, dynamic> _$$CharacterTransformImplToJson(
  _$CharacterTransformImpl instance,
) => <String, dynamic>{
  'translate_x': instance.translateX,
  'translate_y': instance.translateY,
  'scale_x': instance.scaleX,
  'scale_y': instance.scaleY,
};

_$SequenceBooleanEventImpl _$$SequenceBooleanEventImplFromJson(
  Map<String, dynamic> json,
) => _$SequenceBooleanEventImpl(
  startTime: (json['start_time'] as num).toDouble(),
  endTime: (json['end_time'] as num?)?.toDouble(),
  value: json['value'] as bool,
);

Map<String, dynamic> _$$SequenceBooleanEventImplToJson(
  _$SequenceBooleanEventImpl instance,
) => <String, dynamic>{
  'start_time': instance.startTime,
  'end_time': instance.endTime,
  'value': instance.value,
};

_$SequenceMouthEventImpl _$$SequenceMouthEventImplFromJson(
  Map<String, dynamic> json,
) => _$SequenceMouthEventImpl(
  startTime: (json['start_time'] as num).toDouble(),
  endTime: (json['end_time'] as num?)?.toDouble(),
  mouthState: $enumDecode(_$MouthStateEnumMap, json['mouth_state']),
);

Map<String, dynamic> _$$SequenceMouthEventImplToJson(
  _$SequenceMouthEventImpl instance,
) => <String, dynamic>{
  'start_time': instance.startTime,
  'end_time': instance.endTime,
  'mouth_state': _$MouthStateEnumMap[instance.mouthState]!,
};

const _$MouthStateEnumMap = {
  MouthState.closed: 'CLOSED',
  MouthState.open: 'OPEN',
  MouthState.o: 'O',
};

_$SequenceTransformEventImpl _$$SequenceTransformEventImplFromJson(
  Map<String, dynamic> json,
) => _$SequenceTransformEventImpl(
  startTime: (json['start_time'] as num).toDouble(),
  endTime: (json['end_time'] as num?)?.toDouble(),
  targetTransform: CharacterTransform.fromJson(
    json['target_transform'] as Map<String, dynamic>,
  ),
);

Map<String, dynamic> _$$SequenceTransformEventImplToJson(
  _$SequenceTransformEventImpl instance,
) => <String, dynamic>{
  'start_time': instance.startTime,
  'end_time': instance.endTime,
  'target_transform': instance.targetTransform,
};

_$SequenceFloatEventImpl _$$SequenceFloatEventImplFromJson(
  Map<String, dynamic> json,
) => _$SequenceFloatEventImpl(
  startTime: (json['start_time'] as num).toDouble(),
  endTime: (json['end_time'] as num?)?.toDouble(),
  targetValue: (json['target_value'] as num).toDouble(),
);

Map<String, dynamic> _$$SequenceFloatEventImplToJson(
  _$SequenceFloatEventImpl instance,
) => <String, dynamic>{
  'start_time': instance.startTime,
  'end_time': instance.endTime,
  'target_value': instance.targetValue,
};

_$SequenceSoundEventImpl _$$SequenceSoundEventImplFromJson(
  Map<String, dynamic> json,
) => _$SequenceSoundEventImpl(
  startTime: (json['start_time'] as num).toDouble(),
  endTime: (json['end_time'] as num?)?.toDouble(),
  gcsUri: json['gcs_uri'] as String,
  volume: (json['volume'] as num?)?.toDouble() ?? 1.0,
);

Map<String, dynamic> _$$SequenceSoundEventImplToJson(
  _$SequenceSoundEventImpl instance,
) => <String, dynamic>{
  'start_time': instance.startTime,
  'end_time': instance.endTime,
  'gcs_uri': instance.gcsUri,
  'volume': instance.volume,
};

_$PosableCharacterSequenceImpl _$$PosableCharacterSequenceImplFromJson(
  Map<String, dynamic> json,
) => _$PosableCharacterSequenceImpl(
  key: json['key'] as String?,
  sequenceLeftEyeOpen:
      (json['sequence_left_eye_open'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceRightEyeOpen:
      (json['sequence_right_eye_open'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceMouthState:
      (json['sequence_mouth_state'] as List<dynamic>?)
          ?.map((e) => SequenceMouthEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceLeftHandVisible:
      (json['sequence_left_hand_visible'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceRightHandVisible:
      (json['sequence_right_hand_visible'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceLeftHandTransform:
      (json['sequence_left_hand_transform'] as List<dynamic>?)
          ?.map(
            (e) => SequenceTransformEvent.fromJson(e as Map<String, dynamic>),
          )
          .toList() ??
      const [],
  sequenceRightHandTransform:
      (json['sequence_right_hand_transform'] as List<dynamic>?)
          ?.map(
            (e) => SequenceTransformEvent.fromJson(e as Map<String, dynamic>),
          )
          .toList() ??
      const [],
  sequenceHeadTransform:
      (json['sequence_head_transform'] as List<dynamic>?)
          ?.map(
            (e) => SequenceTransformEvent.fromJson(e as Map<String, dynamic>),
          )
          .toList() ??
      const [],
  sequenceSurfaceLineOffset:
      (json['sequence_surface_line_offset'] as List<dynamic>?)
          ?.map((e) => SequenceFloatEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceMaskBoundaryOffset:
      (json['sequence_mask_boundary_offset'] as List<dynamic>?)
          ?.map((e) => SequenceFloatEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceSoundEvents:
      (json['sequence_sound_events'] as List<dynamic>?)
          ?.map((e) => SequenceSoundEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceSurfaceLineVisible:
      (json['sequence_surface_line_visible'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceHeadMaskingEnabled:
      (json['sequence_head_masking_enabled'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceLeftHandMaskingEnabled:
      (json['sequence_left_hand_masking_enabled'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
  sequenceRightHandMaskingEnabled:
      (json['sequence_right_hand_masking_enabled'] as List<dynamic>?)
          ?.map((e) => SequenceBooleanEvent.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const [],
);

Map<String, dynamic> _$$PosableCharacterSequenceImplToJson(
  _$PosableCharacterSequenceImpl instance,
) => <String, dynamic>{
  'key': instance.key,
  'sequence_left_eye_open': instance.sequenceLeftEyeOpen,
  'sequence_right_eye_open': instance.sequenceRightEyeOpen,
  'sequence_mouth_state': instance.sequenceMouthState,
  'sequence_left_hand_visible': instance.sequenceLeftHandVisible,
  'sequence_right_hand_visible': instance.sequenceRightHandVisible,
  'sequence_left_hand_transform': instance.sequenceLeftHandTransform,
  'sequence_right_hand_transform': instance.sequenceRightHandTransform,
  'sequence_head_transform': instance.sequenceHeadTransform,
  'sequence_surface_line_offset': instance.sequenceSurfaceLineOffset,
  'sequence_mask_boundary_offset': instance.sequenceMaskBoundaryOffset,
  'sequence_sound_events': instance.sequenceSoundEvents,
  'sequence_surface_line_visible': instance.sequenceSurfaceLineVisible,
  'sequence_head_masking_enabled': instance.sequenceHeadMaskingEnabled,
  'sequence_left_hand_masking_enabled': instance.sequenceLeftHandMaskingEnabled,
  'sequence_right_hand_masking_enabled':
      instance.sequenceRightHandMaskingEnabled,
};
