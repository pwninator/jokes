import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers_platform_interface/audioplayers_platform_interface.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/character/application/character_animator.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

class _FakeCall {
  final String id;
  final String method;
  final Object? value;

  _FakeCall({required this.id, required this.method, this.value});
}

class _FakeAudioplayersPlatform extends AudioplayersPlatformInterface {
  final List<_FakeCall> calls = <_FakeCall>[];
  final Map<String, StreamController<AudioEvent>> eventStreamControllers =
      <String, StreamController<AudioEvent>>{};

  @override
  Future<void> create(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'create'));
    eventStreamControllers[playerId] = StreamController<AudioEvent>.broadcast();
  }

  @override
  Future<void> dispose(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'dispose'));
    await eventStreamControllers[playerId]?.close();
  }

  @override
  Future<void> emitError(String playerId, String code, String message) async {
    calls.add(_FakeCall(id: playerId, method: 'emitError'));
  }

  @override
  Future<void> emitLog(String playerId, String message) async {
    calls.add(_FakeCall(id: playerId, method: 'emitLog'));
  }

  @override
  Future<int?> getCurrentPosition(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'getCurrentPosition'));
    return 0;
  }

  @override
  Future<int?> getDuration(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'getDuration'));
    return 0;
  }

  @override
  Future<void> pause(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'pause'));
  }

  @override
  Future<void> release(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'release'));
  }

  @override
  Future<void> resume(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'resume'));
  }

  @override
  Future<void> seek(String playerId, Duration position) async {
    calls.add(_FakeCall(id: playerId, method: 'seek', value: position));
  }

  @override
  Future<void> setAudioContext(
    String playerId,
    AudioContext audioContext,
  ) async {
    calls.add(
      _FakeCall(id: playerId, method: 'setAudioContext', value: audioContext),
    );
  }

  @override
  Future<void> setBalance(String playerId, double balance) async {
    calls.add(_FakeCall(id: playerId, method: 'setBalance', value: balance));
  }

  @override
  Future<void> setPlaybackRate(String playerId, double playbackRate) async {
    calls.add(
      _FakeCall(id: playerId, method: 'setPlaybackRate', value: playbackRate),
    );
  }

  @override
  Future<void> setPlayerMode(String playerId, PlayerMode playerMode) async {
    calls.add(
      _FakeCall(id: playerId, method: 'setPlayerMode', value: playerMode),
    );
  }

  @override
  Future<void> setReleaseMode(String playerId, ReleaseMode releaseMode) async {
    calls.add(
      _FakeCall(id: playerId, method: 'setReleaseMode', value: releaseMode),
    );
  }

  @override
  Future<void> setSourceBytes(
    String playerId,
    Uint8List bytes, {
    String? mimeType,
  }) async {
    calls.add(_FakeCall(id: playerId, method: 'setSourceBytes', value: bytes));
    eventStreamControllers[playerId]?.add(
      const AudioEvent(eventType: AudioEventType.prepared, isPrepared: true),
    );
  }

  @override
  Future<void> setSourceUrl(
    String playerId,
    String url, {
    bool? isLocal,
    String? mimeType,
  }) async {
    calls.add(_FakeCall(id: playerId, method: 'setSourceUrl', value: url));
    eventStreamControllers[playerId]?.add(
      const AudioEvent(eventType: AudioEventType.prepared, isPrepared: true),
    );
  }

  @override
  Future<void> setVolume(String playerId, double volume) async {
    calls.add(_FakeCall(id: playerId, method: 'setVolume', value: volume));
  }

  @override
  Future<void> stop(String playerId) async {
    calls.add(_FakeCall(id: playerId, method: 'stop'));
  }

  @override
  Stream<AudioEvent> getEventStream(String playerId) {
    calls.add(_FakeCall(id: playerId, method: 'getEventStream'));
    return eventStreamControllers[playerId]!.stream;
  }
}

class _FakeGlobalAudioplayersPlatform
    extends GlobalAudioplayersPlatformInterface {
  @override
  Future<void> init() async {}

  @override
  Future<void> setGlobalAudioContext(AudioContext ctx) async {}

  @override
  Future<void> emitGlobalLog(String message) async {}

  @override
  Future<void> emitGlobalError(String code, String message) async {}

  @override
  Stream<GlobalAudioEvent> getGlobalEventStream() {
    return const Stream<GlobalAudioEvent>.empty();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  GlobalAudioplayersPlatformInterface.instance =
      _FakeGlobalAudioplayersPlatform();

  late _FakeAudioplayersPlatform fakeAudioPlatform;
  setUp(() {
    fakeAudioPlatform = _FakeAudioplayersPlatform();
    AudioplayersPlatformInterface.instance = fakeAudioPlatform;
  });

  Future<void> flushAudioTasks() async {
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);
  }

  CharacterAnimationConfig createConfig() {
    return CharacterAnimationConfig(
      headTransform: ValueNotifier(Matrix4.identity()),
      leftHandTransform: ValueNotifier(Matrix4.identity()),
      rightHandTransform: ValueNotifier(Matrix4.identity()),
      mouthState: ValueNotifier(MouthState.closed),
      leftEyeOpen: ValueNotifier(true),
      rightEyeOpen: ValueNotifier(true),
      leftHandVisible: ValueNotifier(true),
      rightHandVisible: ValueNotifier(true),
      surfaceLineOffset: ValueNotifier(50.0),
      maskBoundaryOffset: ValueNotifier(50.0),
      surfaceLineVisible: ValueNotifier(true),
      headMaskingEnabled: ValueNotifier(true),
      leftHandMaskingEnabled: ValueNotifier(false),
      rightHandMaskingEnabled: ValueNotifier(false),
    );
  }

  test('CharacterAnimator matches canonical Python fixture outputs', () {
    final fixtureFile = File(
      'py_quill/common/testdata/character_animator_canonical_v1.json',
    );
    final fixture =
        jsonDecode(fixtureFile.readAsStringSync()) as Map<String, dynamic>;
    final sequenceJson = Map<String, dynamic>.from(
      fixture['sequence'] as Map<String, dynamic>,
    );
    sequenceJson['sequence_sound_events'] = <dynamic>[];
    final sequence = PosableCharacterSequence.fromJson(sequenceJson);

    final expectedDuration = (fixture['expected_duration_sec'] as num)
        .toDouble();
    final expectedSamples = (fixture['expected_samples'] as List<dynamic>)
        .cast<Map<String, dynamic>>();

    final controller = AnimationController(vsync: const TestVSync());
    final config = createConfig();

    final animator = CharacterAnimator(
      config: config,
      sequence: sequence,
      controller: controller,
    );

    expect(
      controller.duration!.inMilliseconds / 1000.0,
      closeTo(expectedDuration, 0.001),
    );

    MouthState parseMouthState(String value) {
      switch (value) {
        case 'OPEN':
          return MouthState.open;
        case 'O':
          return MouthState.o;
        case 'CLOSED':
          return MouthState.closed;
      }
      throw StateError('Unknown mouth state $value');
    }

    for (final expected in expectedSamples) {
      final sampleTimeSec = (expected['time_sec'] as num).toDouble();
      controller.value = expectedDuration == 0.0
          ? 0.0
          : sampleTimeSec / expectedDuration;

      expect(config.leftEyeOpen.value, expected['left_eye_open'] as bool);
      expect(config.rightEyeOpen.value, expected['right_eye_open'] as bool);
      expect(
        config.leftHandVisible.value,
        expected['left_hand_visible'] as bool,
      );
      expect(
        config.rightHandVisible.value,
        expected['right_hand_visible'] as bool,
      );
      expect(
        config.mouthState.value,
        parseMouthState(expected['mouth_state'] as String),
      );

      final leftHandExpected =
          expected['left_hand_transform'] as Map<String, dynamic>;
      final rightHandExpected =
          expected['right_hand_transform'] as Map<String, dynamic>;
      final headExpected = expected['head_transform'] as Map<String, dynamic>;

      expect(
        config.leftHandTransform.value.getTranslation().x,
        closeTo((leftHandExpected['translate_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.leftHandTransform.value.getTranslation().y,
        closeTo((leftHandExpected['translate_y'] as num).toDouble(), 0.001),
      );
      expect(
        config.leftHandTransform.value.storage[0],
        closeTo((leftHandExpected['scale_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.leftHandTransform.value.storage[5],
        closeTo((leftHandExpected['scale_y'] as num).toDouble(), 0.001),
      );

      expect(
        config.rightHandTransform.value.getTranslation().x,
        closeTo((rightHandExpected['translate_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.rightHandTransform.value.getTranslation().y,
        closeTo((rightHandExpected['translate_y'] as num).toDouble(), 0.001),
      );
      expect(
        config.rightHandTransform.value.storage[0],
        closeTo((rightHandExpected['scale_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.rightHandTransform.value.storage[5],
        closeTo((rightHandExpected['scale_y'] as num).toDouble(), 0.001),
      );

      expect(
        config.headTransform.value.getTranslation().x,
        closeTo((headExpected['translate_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.headTransform.value.getTranslation().y,
        closeTo((headExpected['translate_y'] as num).toDouble(), 0.001),
      );
      expect(
        config.headTransform.value.storage[0],
        closeTo((headExpected['scale_x'] as num).toDouble(), 0.001),
      );
      expect(
        config.headTransform.value.storage[5],
        closeTo((headExpected['scale_y'] as num).toDouble(), 0.001),
      );
      expect(
        config.surfaceLineOffset.value,
        closeTo((expected['surface_line_offset'] as num).toDouble(), 0.001),
      );
      expect(
        config.maskBoundaryOffset.value,
        closeTo((expected['mask_boundary_offset'] as num).toDouble(), 0.001),
      );
      expect(
        config.surfaceLineVisible.value,
        expected['surface_line_visible'] as bool,
      );
      expect(
        config.headMaskingEnabled.value,
        expected['head_masking_enabled'] as bool,
      );
      expect(
        config.leftHandMaskingEnabled.value,
        expected['left_hand_masking_enabled'] as bool,
      );
      expect(
        config.rightHandMaskingEnabled.value,
        expected['right_hand_masking_enabled'] as bool,
      );
    }

    animator.dispose();
    controller.dispose();
  });

  test('CharacterAnimator initializes duration correctly', () {
    final sequence = PosableCharacterSequence(
      sequenceHeadTransform: [
        SequenceTransformEvent(
          startTime: 0.0,
          endTime: 2.0,
          targetTransform: CharacterTransform(),
        ),
      ],
      sequenceMouthState: [
        SequenceMouthEvent(
          startTime: 1.0,
          endTime: 3.0,
          mouthState: MouthState.open,
        ),
      ],
    );

    final controller = AnimationController(vsync: const TestVSync());

    final config = createConfig();

    final animator = CharacterAnimator(
      config: config,
      sequence: sequence,
      controller: controller,
    );

    expect(controller.duration, const Duration(seconds: 3));

    animator.dispose();
    controller.dispose();
  });

  test('CharacterAnimator interpolates transforms', () {
    final sequence = PosableCharacterSequence(
      sequenceHeadTransform: [
        SequenceTransformEvent(
          startTime: 0.0,
          endTime: 1.0,
          targetTransform: CharacterTransform(
            translateX: 100.0,
            translateY: 50.0,
          ),
        ),
      ],
    );

    final controller = AnimationController(vsync: const TestVSync());
    final headTransform = ValueNotifier(Matrix4.identity());

    final config = CharacterAnimationConfig(
      headTransform: headTransform,
      leftHandTransform: ValueNotifier(Matrix4.identity()),
      rightHandTransform: ValueNotifier(Matrix4.identity()),
      mouthState: ValueNotifier(MouthState.closed),
      leftEyeOpen: ValueNotifier(true),
      rightEyeOpen: ValueNotifier(true),
      leftHandVisible: ValueNotifier(true),
      rightHandVisible: ValueNotifier(true),
      surfaceLineOffset: ValueNotifier(50.0),
      maskBoundaryOffset: ValueNotifier(50.0),
      surfaceLineVisible: ValueNotifier(true),
      headMaskingEnabled: ValueNotifier(true),
      leftHandMaskingEnabled: ValueNotifier(false),
      rightHandMaskingEnabled: ValueNotifier(false),
    );

    final animator = CharacterAnimator(
      config: config,
      sequence: sequence,
      controller: controller,
    );

    expect(controller.duration, const Duration(seconds: 1));

    // At 0.0
    controller.value = 0.0;
    expect(headTransform.value.getTranslation().x, 0.0);
    expect(headTransform.value.getTranslation().y, 0.0);

    // At 0.5 (Halfway)
    controller.value = 0.5;
    expect(headTransform.value.getTranslation().x, closeTo(50.0, 0.1));
    expect(headTransform.value.getTranslation().y, closeTo(25.0, 0.1));

    // At 1.0 (Target)
    controller.value = 1.0;
    expect(headTransform.value.getTranslation().x, closeTo(100.0, 0.1));
    expect(headTransform.value.getTranslation().y, closeTo(50.0, 0.1));

    animator.dispose();
    controller.dispose();
  });

  test('CharacterAnimator handles discrete properties', () {
    final sequence = PosableCharacterSequence(
      sequenceMouthState: [
        SequenceMouthEvent(
          startTime: 0.5,
          endTime: 1.5,
          mouthState: MouthState.open,
        ),
        SequenceMouthEvent(
          startTime: 2.0,
          endTime: 3.0,
          mouthState: MouthState.o,
        ),
      ],
    );

    final controller = AnimationController(vsync: const TestVSync());
    final mouthState = ValueNotifier(MouthState.closed);

    final config = CharacterAnimationConfig(
      headTransform: ValueNotifier(Matrix4.identity()),
      leftHandTransform: ValueNotifier(Matrix4.identity()),
      rightHandTransform: ValueNotifier(Matrix4.identity()),
      mouthState: mouthState,
      leftEyeOpen: ValueNotifier(true),
      rightEyeOpen: ValueNotifier(true),
      leftHandVisible: ValueNotifier(true),
      rightHandVisible: ValueNotifier(true),
      surfaceLineOffset: ValueNotifier(50.0),
      maskBoundaryOffset: ValueNotifier(50.0),
      surfaceLineVisible: ValueNotifier(true),
      headMaskingEnabled: ValueNotifier(true),
      leftHandMaskingEnabled: ValueNotifier(false),
      rightHandMaskingEnabled: ValueNotifier(false),
    );

    final animator = CharacterAnimator(
      config: config,
      sequence: sequence,
      controller: controller,
    );

    expect(controller.duration, const Duration(seconds: 3));

    // 0.0: Closed (default)
    controller.value = 0.0;
    expect(mouthState.value, MouthState.closed);

    // 0.4: Closed (gap)
    controller.value = 0.4 / 3.0;
    expect(mouthState.value, MouthState.closed);

    // 0.5: Open (start)
    controller.value = 0.5 / 3.0;
    expect(mouthState.value, MouthState.open);

    // 1.0: Open (middle)
    controller.value = 1.0 / 3.0;
    expect(mouthState.value, MouthState.open);

    // 1.6: Closed (gap)
    controller.value = 1.6 / 3.0;
    expect(mouthState.value, MouthState.closed);

    // 2.5: O (middle of 2nd event)
    controller.value = 2.5 / 3.0;
    expect(mouthState.value, MouthState.o);

    animator.dispose();
    controller.dispose();
  });

  test('CharacterAnimator starts and stops audio by event window', () async {
    final sequence = PosableCharacterSequence(
      sequenceSoundEvents: [
        SequenceSoundEvent(
          startTime: 0.2,
          endTime: 0.6,
          gcsUri: 'https://example.com/sfx.mp3',
          volume: 0.5,
        ),
      ],
    );

    final controller = AnimationController(vsync: const TestVSync());
    final animator = CharacterAnimator(
      config: createConfig(),
      sequence: sequence,
      controller: controller,
    );

    controller.value = 0.1 / 0.6;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'resume').length,
      0,
    );

    controller.value = 0.25 / 0.6;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'resume').length,
      1,
    );

    controller.value = 0.4 / 0.6;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'resume').length,
      1,
    );

    controller.value = 0.6 / 0.6;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'stop').length,
      greaterThanOrEqualTo(1),
    );

    animator.dispose();
    controller.dispose();
  });

  test('CharacterAnimator seek resets audio window gating', () async {
    final sequence = PosableCharacterSequence(
      sequenceSoundEvents: [
        SequenceSoundEvent(
          startTime: 0.2,
          endTime: 0.9,
          gcsUri: 'https://example.com/sfx.mp3',
          volume: 1.0,
        ),
      ],
    );

    final controller = AnimationController(vsync: const TestVSync());
    final animator = CharacterAnimator(
      config: createConfig(),
      sequence: sequence,
      controller: controller,
    );

    controller.value = 0.3 / 0.9;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'resume').length,
      1,
    );

    animator.seek(const Duration(milliseconds: 100));
    await flushAudioTasks();

    controller.value = 0.3 / 0.9;
    await flushAudioTasks();
    expect(
      fakeAudioPlatform.calls.where((call) => call.method == 'resume').length,
      2,
    );

    animator.dispose();
    controller.dispose();
  });
}
