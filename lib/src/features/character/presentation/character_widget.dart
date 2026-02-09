import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/character/application/character_animator.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

/// Defines the asset providers for the character parts.
/// Can be AssetImages or NetworkImages.
class CharacterAssetConfig {
  final ImageProvider head;
  final ImageProvider leftHand;
  final ImageProvider rightHand;
  final ImageProvider mouthOpen;
  final ImageProvider mouthClosed;
  final ImageProvider mouthO;
  final ImageProvider leftEyeOpen;
  final ImageProvider leftEyeClosed;
  final ImageProvider rightEyeOpen;
  final ImageProvider rightEyeClosed;

  const CharacterAssetConfig({
    required this.head,
    required this.leftHand,
    required this.rightHand,
    required this.mouthOpen,
    required this.mouthClosed,
    required this.mouthO,
    required this.leftEyeOpen,
    required this.leftEyeClosed,
    required this.rightEyeOpen,
    required this.rightEyeClosed,
  });
}

class CharacterWidget extends ConsumerStatefulWidget {
  final PosableCharacterSequence sequence;
  final CharacterAssetConfig assets;
  final bool autoPlay;

  const CharacterWidget({
    super.key,
    required this.sequence,
    required this.assets,
    this.autoPlay = true,
  });

  @override
  ConsumerState<CharacterWidget> createState() => _CharacterWidgetState();
}

class _CharacterWidgetState extends ConsumerState<CharacterWidget> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final CharacterAnimator _animator;

  // Notifiers
  final _headTransform = ValueNotifier<Matrix4>(Matrix4.identity());
  final _leftHandTransform = ValueNotifier<Matrix4>(Matrix4.identity());
  final _rightHandTransform = ValueNotifier<Matrix4>(Matrix4.identity());
  final _mouthState = ValueNotifier<MouthState>(MouthState.closed);
  final _leftEyeOpen = ValueNotifier<bool>(true);
  final _rightEyeOpen = ValueNotifier<bool>(true);
  final _leftHandVisible = ValueNotifier<bool>(true);
  final _rightHandVisible = ValueNotifier<bool>(true);

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this);

    final config = CharacterAnimationConfig(
      headTransform: _headTransform,
      leftHandTransform: _leftHandTransform,
      rightHandTransform: _rightHandTransform,
      mouthState: _mouthState,
      leftEyeOpen: _leftEyeOpen,
      rightEyeOpen: _rightEyeOpen,
      leftHandVisible: _leftHandVisible,
      rightHandVisible: _rightHandVisible,
    );

    _animator = CharacterAnimator(
      config: config,
      sequence: widget.sequence,
      controller: _controller,
    );

    if (widget.autoPlay) {
      _animator.play();
    }
  }

  @override
  void dispose() {
    _animator.dispose();
    _controller.dispose();
    _headTransform.dispose();
    _leftHandTransform.dispose();
    _rightHandTransform.dispose();
    _mouthState.dispose();
    _leftEyeOpen.dispose();
    _rightEyeOpen.dispose();
    _leftHandVisible.dispose();
    _rightHandVisible.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // The stack assumes images are layered centered.
    return Stack(
      alignment: Alignment.center,
      children: [
        // Head Group (Includes Eyes and Mouth)
        ValueListenableBuilder<Matrix4>(
          valueListenable: _headTransform,
          builder: (context, transform, child) {
            return Transform(
              transform: transform,
              alignment: Alignment.center,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Image(image: widget.assets.head, fit: BoxFit.contain),
                  _buildEye(widget.assets.leftEyeOpen, widget.assets.leftEyeClosed, _leftEyeOpen),
                  _buildEye(widget.assets.rightEyeOpen, widget.assets.rightEyeClosed, _rightEyeOpen),
                  _buildMouth(),
                ],
              ),
            );
          },
        ),
        // Left Hand
        ValueListenableBuilder<bool>(
          valueListenable: _leftHandVisible,
          builder: (context, visible, child) {
            if (!visible) return const SizedBox.shrink();
            return ValueListenableBuilder<Matrix4>(
              valueListenable: _leftHandTransform,
              builder: (context, transform, child) {
                return Transform(
                  transform: transform,
                  alignment: Alignment.center,
                  child: Image(image: widget.assets.leftHand, fit: BoxFit.contain),
                );
              },
            );
          },
        ),
        // Right Hand
        ValueListenableBuilder<bool>(
          valueListenable: _rightHandVisible,
          builder: (context, visible, child) {
            if (!visible) return const SizedBox.shrink();
            return ValueListenableBuilder<Matrix4>(
              valueListenable: _rightHandTransform,
              builder: (context, transform, child) {
                return Transform(
                  transform: transform,
                  alignment: Alignment.center,
                  child: Image(image: widget.assets.rightHand, fit: BoxFit.contain),
                );
              },
            );
          },
        ),
      ],
    );
  }

  Widget _buildEye(ImageProvider open, ImageProvider closed, ValueNotifier<bool> notifier) {
    return ValueListenableBuilder<bool>(
      valueListenable: notifier,
      builder: (context, isOpen, child) {
        return Image(
          image: isOpen ? open : closed,
          fit: BoxFit.contain,
        );
      },
    );
  }

  Widget _buildMouth() {
    return ValueListenableBuilder<MouthState>(
      valueListenable: _mouthState,
      builder: (context, state, child) {
        ImageProvider image;
        switch (state) {
          case MouthState.open:
            image = widget.assets.mouthOpen;
            break;
          case MouthState.o:
            image = widget.assets.mouthO;
            break;
          case MouthState.closed:
          default:
            image = widget.assets.mouthClosed;
            break;
        }
        return Image(image: image, fit: BoxFit.contain);
      },
    );
  }
}
