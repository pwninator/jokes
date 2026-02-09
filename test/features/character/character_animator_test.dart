import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/character/application/character_animator.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';

void main() {
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

    final config = CharacterAnimationConfig(
      headTransform: ValueNotifier(Matrix4.identity()),
      leftHandTransform: ValueNotifier(Matrix4.identity()),
      rightHandTransform: ValueNotifier(Matrix4.identity()),
      mouthState: ValueNotifier(MouthState.closed),
      leftEyeOpen: ValueNotifier(true),
      rightEyeOpen: ValueNotifier(true),
      leftHandVisible: ValueNotifier(true),
      rightHandVisible: ValueNotifier(true),
    );

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
          targetTransform: CharacterTransform(translateX: 100.0, translateY: 50.0),
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
        SequenceMouthEvent(startTime: 0.5, endTime: 1.5, mouthState: MouthState.open),
        SequenceMouthEvent(startTime: 2.0, endTime: 3.0, mouthState: MouthState.o),
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
}
