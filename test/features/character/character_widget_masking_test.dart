import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/character/domain/posable_character_sequence.dart';
import 'package:snickerdoodle/src/features/character/presentation/character_widget.dart';

final Uint8List _onePxPng = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2wAAAABJRU5ErkJggg==',
);

ImageProvider _img() => MemoryImage(_onePxPng);

CharacterAssetConfig _assets() {
  return CharacterAssetConfig(
    head: _img(),
    surfaceLine: _img(),
    leftHand: _img(),
    rightHand: _img(),
    mouthOpen: _img(),
    mouthClosed: _img(),
    mouthO: _img(),
    leftEyeOpen: _img(),
    leftEyeClosed: _img(),
    rightEyeOpen: _img(),
    rightEyeClosed: _img(),
  );
}

void main() {
  testWidgets('default masking applies clipper with bottom offset semantics', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Center(
          child: SizedBox(
            width: 120,
            height: 100,
            child: CharacterWidget(
              sequence: const PosableCharacterSequence(),
              assets: _assets(),
              autoPlay: false,
            ),
          ),
        ),
      ),
    );

    await tester.pump();

    final clipRects = find.byType(ClipRect);
    expect(clipRects, findsOneWidget);

    final clipRectWidget = tester.widget<ClipRect>(clipRects.first);
    final clipper = clipRectWidget.clipper!;
    final rect = clipper.getClip(const Size(120, 100));
    expect(rect.bottom, closeTo(50.0, 0.001));
  });

  testWidgets('masking toggles apply per-part without expensive rendering', (
    tester,
  ) async {
    final sequence = PosableCharacterSequence(
      sequenceHeadMaskingEnabled: const [
        SequenceBooleanEvent(startTime: 0.0, endTime: 10.0, value: false),
      ],
      sequenceLeftHandMaskingEnabled: const [
        SequenceBooleanEvent(startTime: 0.0, endTime: 10.0, value: true),
      ],
      sequenceRightHandMaskingEnabled: const [
        SequenceBooleanEvent(startTime: 0.0, endTime: 10.0, value: true),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Center(
          child: SizedBox(
            width: 120,
            height: 100,
            child: CharacterWidget(
              sequence: sequence,
              assets: _assets(),
              autoPlay: true,
            ),
          ),
        ),
      ),
    );

    await tester.pump(const Duration(milliseconds: 100));

    // Head masking disabled + both hands masking enabled => 2 masked layers.
    expect(find.byType(ClipRect), findsNWidgets(2));
  });

  testWidgets('surface line is not subject to masking clip rects', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Center(
          child: SizedBox(
            width: 120,
            height: 100,
            child: CharacterWidget(
              sequence: const PosableCharacterSequence(),
              assets: _assets(),
              autoPlay: false,
            ),
          ),
        ),
      ),
    );

    await tester.pump();

    // Surface line layer is the only Positioned with explicit left/right/top.
    final positionedWidgets = tester.widgetList<Positioned>(find.byType(Positioned));
    final surfaceLinePositioned = positionedWidgets.firstWhere(
      (p) => p.left == 0 && p.right == 0 && p.top != null,
    );

    // The surface line must not be a descendant of any ClipRect masking layer.
    expect(
      find.ancestor(
        of: find.byWidget(surfaceLinePositioned),
        matching: find.byType(ClipRect),
      ),
      findsNothing,
    );
  });
}
