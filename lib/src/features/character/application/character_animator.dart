import 'dart:math' as math;
import 'package:flutter/widgets.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

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

  const CharacterAnimationConfig({
    required this.headTransform,
    required this.leftHandTransform,
    required this.rightHandTransform,
    required this.mouthState,
    required this.leftEyeOpen,
    required this.rightEyeOpen,
    required this.leftHandVisible,
    required this.rightHandVisible,
  });
}

/// Controller logic for animating a posable character.
class CharacterAnimator {
  final CharacterAnimationConfig config;
  final PosableCharacterSequence sequence;
  final AnimationController _controller;
  final List<AudioPlayer> _activeAudioPlayers = [];
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
    // 1. Calculate total duration from sequence
    final double durationSeconds = _calculateTotalDuration();
    final duration = Duration(milliseconds: (durationSeconds * 1000).ceil());
    _controller.duration = duration;

    // 2. Build Animations
    // Prevent division by zero or invalid duration issues
    final safeDuration = durationSeconds > 0 ? durationSeconds : 1.0;

    _headAnimation = _buildTransformAnimation(sequence.sequenceHeadTransform, safeDuration);
    _leftHandAnimation = _buildTransformAnimation(sequence.sequenceLeftHandTransform, safeDuration);
    _rightHandAnimation = _buildTransformAnimation(sequence.sequenceRightHandTransform, safeDuration);
  }

  double _calculateTotalDuration() {
    double maxTime = 0.0;

    void check(Iterable<dynamic> events) {
      for (final e in events) {
        // Access properties dynamically since we know the structure but don't share a base interface
        // with accessible fields for the compiler.
        final double start = (e as dynamic).startTime;
        final double? end = (e as dynamic).endTime;
        maxTime = math.max(maxTime, end ?? start);
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
    check(sequence.sequenceSoundEvents);

    return maxTime;
  }

  Animation<Matrix4> _buildTransformAnimation(List<SequenceTransformEvent> events, double totalDuration) {
    if (events.isEmpty) {
      return ConstantTween<Matrix4>(Matrix4.identity()).animate(_controller);
    }

    // Sort events by start time
    final sortedEvents = List<SequenceTransformEvent>.from(events)..sort((a, b) => a.startTime.compareTo(b.startTime));

    final List<TweenSequenceItem<Matrix4>> items = [];
    double currentTime = 0.0;
    Matrix4 currentMatrix = Matrix4.identity();

    for (int i = 0; i < sortedEvents.length; i++) {
      final event = sortedEvents[i];
      final eventStart = event.startTime;
      final eventEnd = event.endTime ?? event.startTime;

      // Handle Gap (Hold previous)
      if (eventStart > currentTime) {
        final duration = eventStart - currentTime;
        if (duration > 0) {
           items.add(TweenSequenceItem(
            tween: ConstantTween<Matrix4>(currentMatrix),
            weight: duration,
          ));
        }
        currentTime = eventStart;
      }

      final targetTransform = event.targetTransform;
      final targetMatrix = _transformToMatrix(targetTransform);
      final eventDuration = eventEnd - eventStart;

      if (eventDuration > 0) {
        // Interpolate
        items.add(TweenSequenceItem(
          tween: Matrix4Tween(begin: currentMatrix, end: targetMatrix).chain(CurveTween(curve: Curves.linear)),
          weight: eventDuration,
        ));
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
         items.add(TweenSequenceItem(
            tween: ConstantTween<Matrix4>(currentMatrix),
            weight: duration,
         ));
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
      ..translate(t.translateX, t.translateY)
      ..scale(t.scaleX, t.scaleY, 1.0);
  }

  void _onTick() {
    // Update transforms
    config.headTransform.value = _headAnimation.value;
    config.leftHandTransform.value = _leftHandAnimation.value;
    config.rightHandTransform.value = _rightHandAnimation.value;

    final durationSeconds = (_controller.duration?.inMilliseconds.toDouble() ?? 0.0) / 1000.0;
    final double t = _controller.value * durationSeconds;

    _updateDiscreteProperties(t);
    _updateAudio(t);
  }

  void _updateDiscreteProperties(double t) {
    config.mouthState.value = _getMouthState(t);
    config.leftEyeOpen.value = _getBooleanValue(sequence.sequenceLeftEyeOpen, t, true);
    config.rightEyeOpen.value = _getBooleanValue(sequence.sequenceRightEyeOpen, t, true);
    config.leftHandVisible.value = _getBooleanValue(sequence.sequenceLeftHandVisible, t, true);
    config.rightHandVisible.value = _getBooleanValue(sequence.sequenceRightHandVisible, t, true);
  }

  MouthState _getMouthState(double t) {
    // Defaults to CLOSED
    // Find active event
    for (final event in sequence.sequenceMouthState) {
       final end = event.endTime ?? event.startTime;
       if (t >= event.startTime && t <= end) {
         return event.mouthState;
       }
    }
    return MouthState.closed;
  }

  bool _getBooleanValue(List<SequenceBooleanEvent> track, double t, bool defaultValue) {
    for (final event in track) {
       final end = event.endTime ?? event.startTime;
       if (t >= event.startTime && t <= end) {
         return event.value;
       }
    }
    return defaultValue;
  }

  void _updateAudio(double t) {
     // Handle loop/seek: if t jumped backwards, reset _lastAudioTime
     if (t < _lastAudioTime) {
       _lastAudioTime = -1.0;
     }

     for (final event in sequence.sequenceSoundEvents) {
       // Check if event started between _lastAudioTime (exclusive) and t (inclusive)
       if (event.startTime > _lastAudioTime && event.startTime <= t) {
         _playAudio(event);
       }
     }
     _lastAudioTime = t;
  }

  Future<void> _playAudio(SequenceSoundEvent event) async {
    final player = AudioPlayer();
    _activeAudioPlayers.add(player);

    // Cleanup on complete
    player.onPlayerComplete.listen((_) {
      _activeAudioPlayers.remove(player);
      player.dispose();
    });

    try {
      await player.play(UrlSource(event.gcsUri), volume: event.volume);
    } catch (e) {
      debugPrint('Error playing audio: $e');
      _activeAudioPlayers.remove(player);
      player.dispose();
    }
  }

  void dispose() {
    _controller.removeListener(_onTick);
    for (final player in _activeAudioPlayers) {
      player.dispose();
    }
    _activeAudioPlayers.clear();
  }

  // Proxies for controller
  void play() => _controller.forward();
  void pause() => _controller.stop();
  void seek(Duration pos) {
     final duration = _controller.duration;
     if (duration != null && duration.inMilliseconds > 0) {
       _controller.value = pos.inMilliseconds / duration.inMilliseconds;
     }
  }
}
