import 'dart:math' as math;
import 'package:flutter/widgets.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

/// This implementation must strictly conform to:
/// `py_quill/common/character_animator_spec.md`.
/// Keep runtime semantics aligned with the canonical spec.

/// Configuration object holding ValueNotifiers for the CharacterAnimator.
class CharacterAnimationConfig {
  final ValueNotifier<Matrix4> headTransform;
  final ValueNotifier<Matrix4> leftHandTransform;
  final ValueNotifier<Matrix4> rightHandTransform;
  final ValueNotifier<MouthState> mouthState;
  final ValueNotifier<bool> leftEyeOpen;
  final ValueNotifier<bool> rightEyeOpen;
  final ValueNotifier<bool> leftHandVisible;
  final ValueNotifier<bool> rightHandVisible;
  final ValueNotifier<double> surfaceLineOffset;
  final ValueNotifier<double> maskBoundaryOffset;
  final ValueNotifier<bool> surfaceLineVisible;
  final ValueNotifier<bool> headMaskingEnabled;
  final ValueNotifier<bool> leftHandMaskingEnabled;
  final ValueNotifier<bool> rightHandMaskingEnabled;

  const CharacterAnimationConfig({
    required this.headTransform,
    required this.leftHandTransform,
    required this.rightHandTransform,
    required this.mouthState,
    required this.leftEyeOpen,
    required this.rightEyeOpen,
    required this.leftHandVisible,
    required this.rightHandVisible,
    required this.surfaceLineOffset,
    required this.maskBoundaryOffset,
    required this.surfaceLineVisible,
    required this.headMaskingEnabled,
    required this.leftHandMaskingEnabled,
    required this.rightHandMaskingEnabled,
  });
}

/// Controller logic for animating a posable character.
///
/// Runtime behavior should match `py_quill/common/character_animator_spec.md`.
class CharacterAnimator {
  final CharacterAnimationConfig config;
  final PosableCharacterSequence sequence;
  final AnimationController _controller;
  final Map<int, AudioPlayer> _activeAudioPlayersByEvent = {};
  double _lastAudioTime = -1.0;

  // Animation objects for transforms
  late final Animation<Matrix4> _headAnimation;
  late final Animation<Matrix4> _leftHandAnimation;
  late final Animation<Matrix4> _rightHandAnimation;

  CharacterAnimator({
    required this.config,
    required this.sequence,
    required AnimationController controller,
  }) : _controller = controller {
    _initialize();
    _controller.addListener(_onTick);
  }

  void _initialize() {
    _validateSequenceForSpec();
    // 1. Calculate total duration from sequence
    final double durationSeconds = _calculateTotalDuration();
    final duration = Duration(milliseconds: (durationSeconds * 1000).ceil());
    _controller.duration = duration;

    // 2. Build Animations
    // Prevent division by zero or invalid duration issues
    final safeDuration = durationSeconds > 0 ? durationSeconds : 1.0;

    _headAnimation = _buildTransformAnimation(
      sequence.sequenceHeadTransform,
      safeDuration,
    );
    _leftHandAnimation = _buildTransformAnimation(
      sequence.sequenceLeftHandTransform,
      safeDuration,
    );
    _rightHandAnimation = _buildTransformAnimation(
      sequence.sequenceRightHandTransform,
      safeDuration,
    );
  }

  double _calculateTotalDuration() {
    double maxTime = 0.0;

    void check(Iterable<dynamic> events) {
      for (final e in events) {
        // Access properties dynamically since we know the structure but don't share a base interface
        // with accessible fields for the compiler.
        final num endRaw = (e as dynamic).endTime as num;
        final double end = endRaw.toDouble();
        maxTime = math.max(maxTime, end);
      }
    }

    check(sequence.sequenceLeftEyeOpen);
    check(sequence.sequenceRightEyeOpen);
    check(sequence.sequenceMouthState);
    check(sequence.sequenceLeftHandVisible);
    check(sequence.sequenceRightHandVisible);
    check(sequence.sequenceLeftHandTransform);
    check(sequence.sequenceRightHandTransform);
    check(sequence.sequenceHeadTransform);
    check(sequence.sequenceSurfaceLineOffset);
    check(sequence.sequenceMaskBoundaryOffset);
    check(sequence.sequenceSoundEvents);
    check(sequence.sequenceSurfaceLineVisible);
    check(sequence.sequenceHeadMaskingEnabled);
    check(sequence.sequenceLeftHandMaskingEnabled);
    check(sequence.sequenceRightHandMaskingEnabled);

    return maxTime;
  }

  Animation<Matrix4> _buildTransformAnimation(
    List<SequenceTransformEvent> events,
    double totalDuration,
  ) {
    if (events.isEmpty) {
      return ConstantTween<Matrix4>(Matrix4.identity()).animate(_controller);
    }

    // Sort events by start time
    final sortedEvents = List<SequenceTransformEvent>.from(events)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));

    final List<TweenSequenceItem<Matrix4>> items = [];
    double currentTime = 0.0;
    Matrix4 currentMatrix = Matrix4.identity();

    for (int i = 0; i < sortedEvents.length; i++) {
      final event = sortedEvents[i];
      final eventStart = event.startTime;
      final eventEnd = event.endTime!;

      // Handle Gap (Hold previous)
      if (eventStart > currentTime) {
        final duration = eventStart - currentTime;
        if (duration > 0) {
          items.add(
            TweenSequenceItem(
              tween: ConstantTween<Matrix4>(currentMatrix),
              weight: duration,
            ),
          );
        }
        currentTime = eventStart;
      }

      final targetTransform = event.targetTransform;
      final targetMatrix = _transformToMatrix(targetTransform);
      final eventDuration = eventEnd - eventStart;

      if (eventDuration > 0) {
        // Interpolate
        items.add(
          TweenSequenceItem(
            tween: Matrix4Tween(
              begin: currentMatrix,
              end: targetMatrix,
            ).chain(CurveTween(curve: Curves.linear)),
            weight: eventDuration,
          ),
        );
        currentTime = eventEnd;
        currentMatrix = targetMatrix;
      } else {
        // Instant update
        currentMatrix = targetMatrix;
        currentTime = eventEnd;
      }
    }

    // Fill remaining time
    if (currentTime < totalDuration) {
      final duration = totalDuration - currentTime;
      if (duration > 0) {
        items.add(
          TweenSequenceItem(
            tween: ConstantTween<Matrix4>(currentMatrix),
            weight: duration,
          ),
        );
      }
    }

    if (items.isEmpty) {
      return ConstantTween<Matrix4>(Matrix4.identity()).animate(_controller);
    }

    return TweenSequence<Matrix4>(items).animate(_controller);
  }

  Matrix4 _transformToMatrix(CharacterTransform t) {
    // T * S
    return Matrix4.identity()
      ..translateByDouble(t.translateX, t.translateY, 0.0, 1.0)
      ..scaleByDouble(t.scaleX, t.scaleY, 1.0, 1.0);
  }

  void _onTick() {
    // Update transforms
    config.headTransform.value = _headAnimation.value;
    config.leftHandTransform.value = _leftHandAnimation.value;
    config.rightHandTransform.value = _rightHandAnimation.value;

    final durationSeconds =
        (_controller.duration?.inMilliseconds.toDouble() ?? 0.0) / 1000.0;
    final double t = _controller.value * durationSeconds;

    _updateDiscreteProperties(t);
    _updateAudio(t);
  }

  void _updateDiscreteProperties(double t) {
    config.mouthState.value = _getMouthState(t);
    config.leftEyeOpen.value = _getBooleanValue(
      sequence.sequenceLeftEyeOpen,
      t,
      true,
    );
    config.rightEyeOpen.value = _getBooleanValue(
      sequence.sequenceRightEyeOpen,
      t,
      true,
    );
    config.leftHandVisible.value = _getBooleanValue(
      sequence.sequenceLeftHandVisible,
      t,
      true,
    );
    config.rightHandVisible.value = _getBooleanValue(
      sequence.sequenceRightHandVisible,
      t,
      true,
    );
    config.surfaceLineOffset.value = _getFloatValue(
      sequence.sequenceSurfaceLineOffset,
      t,
      50.0,
    );
    config.maskBoundaryOffset.value = _getFloatValue(
      sequence.sequenceMaskBoundaryOffset,
      t,
      50.0,
    );
    config.surfaceLineVisible.value = _getBooleanValue(
      sequence.sequenceSurfaceLineVisible,
      t,
      true,
    );
    config.headMaskingEnabled.value = _getBooleanValue(
      sequence.sequenceHeadMaskingEnabled,
      t,
      true,
    );
    config.leftHandMaskingEnabled.value = _getBooleanValue(
      sequence.sequenceLeftHandMaskingEnabled,
      t,
      false,
    );
    config.rightHandMaskingEnabled.value = _getBooleanValue(
      sequence.sequenceRightHandMaskingEnabled,
      t,
      false,
    );
  }

  MouthState _getMouthState(double t) {
    // Spec: active window is [start, end) and track sorted by start_time.
    if (sequence.sequenceMouthState.isEmpty) {
      return MouthState.closed;
    }
    final sorted = List<SequenceMouthEvent>.from(sequence.sequenceMouthState)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));
    for (final event in sorted) {
      final start = event.startTime;
      final end = event.endTime!;
      if (start <= t && t < end) {
        return event.mouthState;
      }
      if (start > t) {
        break;
      }
    }
    return MouthState.closed;
  }

  bool _getBooleanValue(
    List<SequenceBooleanEvent> track,
    double t,
    bool defaultValue,
  ) {
    // Spec: active window is [start, end) and track sorted by start_time.
    if (track.isEmpty) {
      return defaultValue;
    }
    final sorted = List<SequenceBooleanEvent>.from(track)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));
    for (final event in sorted) {
      final start = event.startTime;
      final end = event.endTime!;
      if (start <= t && t < end) {
        return event.value;
      }
      if (start > t) {
        break;
      }
    }
    return defaultValue;
  }

  double _getFloatValue(
    List<SequenceFloatEvent> track,
    double t,
    double defaultValue,
  ) {
    if (track.isEmpty) {
      return defaultValue;
    }
    final sorted = List<SequenceFloatEvent>.from(track)
      ..sort((a, b) => a.startTime.compareTo(b.startTime));
    double previousTarget = defaultValue;
    for (final event in sorted) {
      final end = event.endTime!;
      if (t < event.startTime) {
        return previousTarget;
      }
      // Spec: active window is [start, end)
      if (event.startTime <= t && t < end) {
        final duration = end - event.startTime;
        if (duration <= 0) {
          return event.targetValue;
        }
        final progress = (t - event.startTime) / duration;
        return previousTarget +
            ((event.targetValue - previousTarget) * progress);
      }
      previousTarget = event.targetValue;
    }
    return previousTarget;
  }

  void _updateAudio(double t) {
    // Handle loop/seek: if t jumped backwards, reset _lastAudioTime
    if (t < _lastAudioTime) {
      _lastAudioTime = -1.0;
    }

    for (
      int eventIndex = 0;
      eventIndex < sequence.sequenceSoundEvents.length;
      eventIndex++
    ) {
      final event = sequence.sequenceSoundEvents[eventIndex];
      final end = event.endTime!;
      // Check if event started between _lastAudioTime (exclusive) and t (inclusive)
      if (event.startTime > _lastAudioTime && event.startTime <= t && t < end) {
        _playAudio(eventIndex, event);
      }
      if (t >= end) {
        _stopAudio(eventIndex);
      }
    }
    _lastAudioTime = t;
  }

  Future<void> _playAudio(int eventIndex, SequenceSoundEvent event) async {
    _stopAudio(eventIndex);
    final player = AudioPlayer();
    _activeAudioPlayersByEvent[eventIndex] = player;

    // Cleanup on complete
    player.onPlayerComplete.listen((_) {
      if (_activeAudioPlayersByEvent[eventIndex] == player) {
        _activeAudioPlayersByEvent.remove(eventIndex);
      }
      player.dispose();
    });

    try {
      await player.play(UrlSource(event.gcsUri), volume: event.volume);
    } catch (e) {
      debugPrint('Error playing audio: $e');
      if (_activeAudioPlayersByEvent[eventIndex] == player) {
        _activeAudioPlayersByEvent.remove(eventIndex);
      }
      player.dispose();
    }
  }

  void _stopAudio(int eventIndex) {
    final player = _activeAudioPlayersByEvent.remove(eventIndex);
    if (player == null) {
      return;
    }
    player.stop();
    player.dispose();
  }

  void _stopAllAudio() {
    final eventIndexes = _activeAudioPlayersByEvent.keys.toList();
    for (final eventIndex in eventIndexes) {
      _stopAudio(eventIndex);
    }
  }

  void _validateSequenceForSpec() {
    void checkEvents(Iterable<dynamic> events, String trackName) {
      for (final event in events) {
        final num startRaw = (event as dynamic).startTime as num;
        final double start = startRaw.toDouble();
        final num? endRaw = (event as dynamic).endTime as num?;
        final double? end = endRaw?.toDouble();
        if (end == null) {
          throw StateError('$trackName event missing required endTime');
        }
        if (end < start) {
          throw StateError('$trackName event has endTime < startTime');
        }
      }
    }

    checkEvents(sequence.sequenceLeftEyeOpen, 'sequenceLeftEyeOpen');
    checkEvents(sequence.sequenceRightEyeOpen, 'sequenceRightEyeOpen');
    checkEvents(sequence.sequenceMouthState, 'sequenceMouthState');
    checkEvents(sequence.sequenceLeftHandVisible, 'sequenceLeftHandVisible');
    checkEvents(sequence.sequenceRightHandVisible, 'sequenceRightHandVisible');
    checkEvents(
      sequence.sequenceLeftHandTransform,
      'sequenceLeftHandTransform',
    );
    checkEvents(
      sequence.sequenceRightHandTransform,
      'sequenceRightHandTransform',
    );
    checkEvents(sequence.sequenceHeadTransform, 'sequenceHeadTransform');
    checkEvents(sequence.sequenceSoundEvents, 'sequenceSoundEvents');
    checkEvents(
      sequence.sequenceSurfaceLineOffset,
      'sequenceSurfaceLineOffset',
    );
    checkEvents(
      sequence.sequenceMaskBoundaryOffset,
      'sequenceMaskBoundaryOffset',
    );
    checkEvents(
      sequence.sequenceSurfaceLineVisible,
      'sequenceSurfaceLineVisible',
    );
    checkEvents(
      sequence.sequenceHeadMaskingEnabled,
      'sequenceHeadMaskingEnabled',
    );
    checkEvents(
      sequence.sequenceLeftHandMaskingEnabled,
      'sequenceLeftHandMaskingEnabled',
    );
    checkEvents(
      sequence.sequenceRightHandMaskingEnabled,
      'sequenceRightHandMaskingEnabled',
    );
  }

  void dispose() {
    _controller.removeListener(_onTick);
    for (final player in _activeAudioPlayersByEvent.values) {
      player.dispose();
    }
    _activeAudioPlayersByEvent.clear();
  }

  // Proxies for controller
  void play() => _controller.forward();
  void pause() => _controller.stop();
  void seek(Duration pos) {
    _stopAllAudio();
    _lastAudioTime = -1.0;
    final duration = _controller.duration;
    if (duration != null && duration.inMilliseconds > 0) {
      _controller.value = pos.inMilliseconds / duration.inMilliseconds;
    }
  }
}
