import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/character/application/character_animator.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

/// Defines the asset providers for the character parts.
/// Can be AssetImages or NetworkImages.
class CharacterAssetConfig {
  final ImageProvider head;
  final ImageProvider? surfaceLine;
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
    this.surfaceLine,
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

class _CharacterWidgetState extends ConsumerState<CharacterWidget>
    with SingleTickerProviderStateMixin {
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
  final _surfaceLineOffset = ValueNotifier<double>(50.0);
  final _maskBoundaryOffset = ValueNotifier<double>(50.0);
  final _surfaceLineVisible = ValueNotifier<bool>(true);
  final _headMaskingEnabled = ValueNotifier<bool>(true);
  final _leftHandMaskingEnabled = ValueNotifier<bool>(false);
  final _rightHandMaskingEnabled = ValueNotifier<bool>(false);

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
      surfaceLineOffset: _surfaceLineOffset,
      maskBoundaryOffset: _maskBoundaryOffset,
      surfaceLineVisible: _surfaceLineVisible,
      headMaskingEnabled: _headMaskingEnabled,
      leftHandMaskingEnabled: _leftHandMaskingEnabled,
      rightHandMaskingEnabled: _rightHandMaskingEnabled,
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
    _surfaceLineOffset.dispose();
    _maskBoundaryOffset.dispose();
    _surfaceLineVisible.dispose();
    _headMaskingEnabled.dispose();
    _leftHandMaskingEnabled.dispose();
    _rightHandMaskingEnabled.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final canvasHeight = constraints.maxHeight.isFinite
            ? constraints.maxHeight
            : 0.0;
        return Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            _buildHeadLayer(canvasHeight),
            _buildSurfaceLineLayer(canvasHeight),
            _buildHandLayer(
              visibleNotifier: _leftHandVisible,
              transformNotifier: _leftHandTransform,
              maskingEnabledNotifier: _leftHandMaskingEnabled,
              image: widget.assets.leftHand,
              canvasHeight: canvasHeight,
            ),
            _buildHandLayer(
              visibleNotifier: _rightHandVisible,
              transformNotifier: _rightHandTransform,
              maskingEnabledNotifier: _rightHandMaskingEnabled,
              image: widget.assets.rightHand,
              canvasHeight: canvasHeight,
            ),
          ],
        );
      },
    );
  }

  Widget _buildHeadLayer(double canvasHeight) {
    return ValueListenableBuilder<Matrix4>(
      valueListenable: _headTransform,
      builder: (context, transform, child) {
        return _buildMaskedLayer(
          canvasHeight: canvasHeight,
          maskingEnabledNotifier: _headMaskingEnabled,
          child: Center(
            child: Transform(
              transform: transform,
              alignment: Alignment.center,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Image(image: widget.assets.head, fit: BoxFit.contain),
                  _buildEye(
                    widget.assets.leftEyeOpen,
                    widget.assets.leftEyeClosed,
                    _leftEyeOpen,
                  ),
                  _buildEye(
                    widget.assets.rightEyeOpen,
                    widget.assets.rightEyeClosed,
                    _rightEyeOpen,
                  ),
                  _buildMouth(),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildSurfaceLineLayer(double canvasHeight) {
    if (widget.assets.surfaceLine == null) {
      return const SizedBox.shrink();
    }
    return ValueListenableBuilder<bool>(
      valueListenable: _surfaceLineVisible,
      builder: (context, visible, child) {
        if (!visible) {
          return const SizedBox.shrink();
        }
        return ValueListenableBuilder<double>(
          valueListenable: _surfaceLineOffset,
          builder: (context, offset, child) {
            final top = canvasHeight - offset;
            return Positioned(
              left: 0,
              right: 0,
              top: top,
              child: Align(
                alignment: Alignment.topCenter,
                child: Image(
                  image: widget.assets.surfaceLine!,
                  fit: BoxFit.contain,
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildHandLayer({
    required ValueNotifier<bool> visibleNotifier,
    required ValueNotifier<Matrix4> transformNotifier,
    required ValueNotifier<bool> maskingEnabledNotifier,
    required ImageProvider image,
    required double canvasHeight,
  }) {
    return ValueListenableBuilder<bool>(
      valueListenable: visibleNotifier,
      builder: (context, visible, child) {
        if (!visible) {
          return const SizedBox.shrink();
        }
        return ValueListenableBuilder<Matrix4>(
          valueListenable: transformNotifier,
          builder: (context, transform, child) {
            return _buildMaskedLayer(
              canvasHeight: canvasHeight,
              maskingEnabledNotifier: maskingEnabledNotifier,
              child: Center(
                child: Transform(
                  transform: transform,
                  alignment: Alignment.center,
                  child: Image(image: image, fit: BoxFit.contain),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildMaskedLayer({
    required double canvasHeight,
    required ValueNotifier<bool> maskingEnabledNotifier,
    required Widget child,
  }) {
    return ValueListenableBuilder<bool>(
      valueListenable: maskingEnabledNotifier,
      builder: (context, maskingEnabled, _) {
        if (!maskingEnabled) {
          return Positioned.fill(child: child);
        }
        return ValueListenableBuilder<double>(
          valueListenable: _maskBoundaryOffset,
          builder: (context, boundaryOffset, _) {
            return Positioned.fill(
              child: ClipRect(
                clipper: _BelowBoundaryClipper(
                  boundaryOffset: boundaryOffset,
                  canvasHeight: canvasHeight,
                ),
                child: child,
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildEye(
    ImageProvider open,
    ImageProvider closed,
    ValueNotifier<bool> notifier,
  ) {
    return ValueListenableBuilder<bool>(
      valueListenable: notifier,
      builder: (context, isOpen, child) {
        return Image(image: isOpen ? open : closed, fit: BoxFit.contain);
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
            image = widget.assets.mouthClosed;
            break;
        }
        return Image(image: image, fit: BoxFit.contain);
      },
    );
  }
}

class _BelowBoundaryClipper extends CustomClipper<Rect> {
  static const double _overscan = 100000.0;

  final double boundaryOffset;
  final double canvasHeight;

  const _BelowBoundaryClipper({
    required this.boundaryOffset,
    required this.canvasHeight,
  });

  @override
  Rect getClip(Size size) {
    final maxHeight = canvasHeight > 0 ? canvasHeight : size.height;
    final cutoffY = (maxHeight - boundaryOffset).clamp(0.0, maxHeight);
    return Rect.fromLTRB(
      -_overscan,
      -_overscan,
      size.width + _overscan,
      cutoffY,
    );
  }

  @override
  bool shouldReclip(_BelowBoundaryClipper oldClipper) {
    return oldClipper.boundaryOffset != boundaryOffset ||
        oldClipper.canvasHeight != canvasHeight;
  }
}
