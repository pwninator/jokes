const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

function loadCharacterAnimatorModule() {
  const filePath = path.resolve(__dirname, 'character_animator.js');
  const source = fs.readFileSync(filePath, 'utf8');
  const dataUrl = `data:text/javascript;base64,${Buffer.from(source, 'utf8').toString('base64')}`;
  return import(dataUrl);
}

function loadCanonicalFixture() {
  const fixturePath = path.resolve(
    __dirname,
    '..',
    '..',
    '..',
    'common',
    'testdata',
    'character_animator_canonical_v1.json',
  );
  const raw = fs.readFileSync(fixturePath, 'utf8');
  return JSON.parse(raw);
}

function assertClose(actual, expected, tolerance = 1e-6) {
  assert.ok(
    Math.abs(Number(actual) - Number(expected)) <= tolerance,
    `Expected ${actual} to be within ${tolerance} of ${expected}`,
  );
}

function minimalDefinition() {
  return {
    width: 100,
    height: 80,
    surface_line_gcs_uri: 'gs://bucket/surface_line.png',
  };
}

test('CharacterAnimator matches canonical fixture samples', async () => {
  const fixture = loadCanonicalFixture();
  const { CharacterAnimator } = await loadCharacterAnimatorModule();

  const animator = new CharacterAnimator(fixture.sequence, {}, minimalDefinition());
  assertClose(animator.durationSec(), fixture.expected_duration_sec);

  const expectedByTime = new Map();
  fixture.expected_samples.forEach((sample) => {
    expectedByTime.set(Number(sample.time_sec), sample);
  });

  fixture.sample_times_sec.forEach((sampleTimeSec) => {
    const timeSec = Number(sampleTimeSec);
    const expected = expectedByTime.get(timeSec);
    assert.ok(expected, `Missing expected sample for time ${timeSec}`);

    const sample = animator.samplePoseAtTime(timeSec);
    assert.equal(sample.left_eye_open, expected.left_eye_open);
    assert.equal(sample.right_eye_open, expected.right_eye_open);
    assert.equal(sample.mouth_state, expected.mouth_state);
    assert.equal(sample.left_hand_visible, expected.left_hand_visible);
    assert.equal(sample.right_hand_visible, expected.right_hand_visible);

    assertClose(
      sample.left_hand_transform.translate_x,
      expected.left_hand_transform.translate_x,
    );
    assertClose(
      sample.left_hand_transform.translate_y,
      expected.left_hand_transform.translate_y,
    );
    assertClose(
      sample.left_hand_transform.scale_x,
      expected.left_hand_transform.scale_x,
    );
    assertClose(
      sample.left_hand_transform.scale_y,
      expected.left_hand_transform.scale_y,
    );

    assertClose(
      sample.right_hand_transform.translate_x,
      expected.right_hand_transform.translate_x,
    );
    assertClose(
      sample.right_hand_transform.translate_y,
      expected.right_hand_transform.translate_y,
    );
    assertClose(
      sample.right_hand_transform.scale_x,
      expected.right_hand_transform.scale_x,
    );
    assertClose(
      sample.right_hand_transform.scale_y,
      expected.right_hand_transform.scale_y,
    );

    assertClose(
      sample.head_transform.translate_x,
      expected.head_transform.translate_x,
    );
    assertClose(
      sample.head_transform.translate_y,
      expected.head_transform.translate_y,
    );
    assertClose(
      sample.head_transform.scale_x,
      expected.head_transform.scale_x,
    );
    assertClose(
      sample.head_transform.scale_y,
      expected.head_transform.scale_y,
    );
    assertClose(sample.surface_line_offset, expected.surface_line_offset);
    assertClose(sample.mask_boundary_offset, expected.mask_boundary_offset);
    assert.equal(sample.surface_line_visible, expected.surface_line_visible);
    assert.equal(sample.head_masking_enabled, expected.head_masking_enabled);
    assert.equal(
      sample.left_hand_masking_enabled,
      expected.left_hand_masking_enabled,
    );
    assert.equal(
      sample.right_hand_masking_enabled,
      expected.right_hand_masking_enabled,
    );
  });
});

test('CharacterAnimator matches canonical fixture sound windows', async () => {
  const fixture = loadCanonicalFixture();
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const animator = new CharacterAnimator(fixture.sequence, {}, minimalDefinition());

  fixture.sound_windows.forEach((window) => {
    const sounds = animator.soundEventsBetween(
      Number(window.start_time_sec),
      Number(window.end_time_sec),
      { includeStart: true, includeEnd: false },
    );
    const actualStarts = sounds.map((event) => Number(event.start_time));
    const expectedStarts = window.expected_sound_starts.map((value) => Number(value));
    assert.deepEqual(actualStarts, expectedStarts);
  });
});

test('CharacterAnimator updateSequence uses updated track data after cache has been primed', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const initialSequence = {
    sequence_left_eye_open: [],
    sequence_right_eye_open: [],
    sequence_mouth_state: [
      { start_time: 0, end_time: 1, mouth_state: 'CLOSED' },
    ],
    sequence_left_hand_visible: [],
    sequence_right_hand_visible: [],
    sequence_left_hand_transform: [],
    sequence_right_hand_transform: [],
    sequence_head_transform: [],
    sequence_sound_events: [],
  };
  const updatedSequence = {
    ...initialSequence,
    sequence_mouth_state: [
      { start_time: 0, end_time: 1, mouth_state: 'OPEN' },
    ],
  };

  const animator = new CharacterAnimator(initialSequence, {}, minimalDefinition());

  // Avoid requiring GSAP runtime in this unit test.
  animator._preloadAudio = async () => {};
  animator._buildTimeline = () => {};

  // Prime internal sorted-track cache from the initial sequence.
  assert.equal(animator.samplePoseAtTime(0.5).mouth_state, 'CLOSED');

  await animator.updateSequence(updatedSequence);

  // Must reflect updated sequence data after updateSequence.
  assert.equal(animator.samplePoseAtTime(0.5).mouth_state, 'OPEN');
});

test('CharacterAnimator play always restarts from time zero', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const animator = new CharacterAnimator({}, {}, minimalDefinition());

  let seekCalledWith = null;
  animator.seek = (time) => {
    seekCalledWith = time;
  };

  let played = false;
  animator.timeline = {
    play() {
      played = true;
    },
  };

  animator.play();

  assert.equal(seekCalledWith, 0);
  assert.equal(played, true);
});

test('CharacterAnimator applies clip-path masking style deterministically', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const element = { style: {} };
  const animator = new CharacterAnimator({}, {}, minimalDefinition());

  animator._applyMasking(element, 12, true);
  assert.equal(element.style.clipPath, 'inset(-10000px -10000px 12px -10000px)');

  animator._applyMasking(element, 12, false);
  assert.equal(element.style.clipPath, 'none');
});

test('CharacterAnimator positions surface line from bottom offset', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const lineElement = { style: {} };
  const animator = new CharacterAnimator(
    {},
    { surfaceLine: lineElement },
    minimalDefinition(),
  );

  animator._applySurfaceLineOffset(30);
  // height (80) - offset (30) => top 50.
  assert.equal(lineElement.style.top, '50px');
});

test('CharacterAnimator render loop applies masking independent of transforms', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();

  const leftHandClip = { style: {} };
  const leftHandTransform = { style: {} };
  const surfaceLine = { style: {} };

  const sequence = {
    sequence_left_eye_open: [],
    sequence_right_eye_open: [],
    sequence_mouth_state: [],
    sequence_left_hand_visible: [{ start_time: 0, end_time: 10, value: true }],
    sequence_right_hand_visible: [],
    sequence_left_hand_transform: [
      { start_time: 0, end_time: 2, target_transform: { translate_x: 0, translate_y: 20, scale_x: 1, scale_y: 1 } },
    ],
    sequence_right_hand_transform: [],
    sequence_head_transform: [],
    sequence_surface_line_offset: [{ start_time: 0, end_time: 2, target_value: 20 }],
    sequence_mask_boundary_offset: [
      { start_time: 0, end_time: 1, target_value: 12 },
      { start_time: 1, end_time: 2, target_value: 30 },
    ],
    sequence_surface_line_visible: [{ start_time: 0, end_time: 10, value: true }],
    sequence_head_masking_enabled: [],
    sequence_left_hand_masking_enabled: [{ start_time: 0, end_time: 10, value: true }],
    sequence_right_hand_masking_enabled: [],
    sequence_sound_events: [],
  };

  const animator = new CharacterAnimator(
    sequence,
    {
      leftHandClip,
      leftHandTransform,
      surfaceLine,
    },
    minimalDefinition(),
  );

  // At t=1.0, boundary offset resolves to 12 (from first event).
  animator._renderAtTime(1.0);
  assert.equal(leftHandClip.style.clipPath, 'inset(-10000px -10000px 12px -10000px)');
  assert.ok(
    String(leftHandTransform.style.transform || '').includes('translate('),
    'expected transform wrapper to receive a translate() transform',
  );
  assert.equal(leftHandTransform.style.clipPath, undefined);

  // Surface line should be visible and positioned from the bottom offset.
  // The surface line offset is a float track; verify top using the sampled pose.
  const poseAtOne = animator.samplePoseAtTime(1.0);
  const expectedTop = `${minimalDefinition().height - poseAtOne.surface_line_offset}px`;
  assert.equal(surfaceLine.style.opacity, '1');
  assert.equal(surfaceLine.style.visibility, 'visible');
  assert.equal(surfaceLine.style.top, expectedTop);

  // At t=1.5, boundary offset should have advanced (interpolating 12 -> 30).
  animator._renderAtTime(1.5);
  assert.notEqual(leftHandClip.style.clipPath, 'inset(-10000px -10000px 12px -10000px)');
});

test('CharacterAnimator uses initial_pose as baseline before first events', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const sequence = {
    initial_pose: {
      mouth_state: 'O',
      head_transform: { translate_x: 0, translate_y: 400, scale_x: 1, scale_y: 1 },
    },
    sequence_left_eye_open: [],
    sequence_right_eye_open: [],
    sequence_mouth_state: [],
    sequence_left_hand_visible: [],
    sequence_right_hand_visible: [],
    sequence_left_hand_transform: [],
    sequence_right_hand_transform: [],
    sequence_head_transform: [
      { start_time: 2, end_time: 3, target_transform: { translate_x: 0, translate_y: 450, scale_x: 1, scale_y: 1 } },
    ],
    sequence_surface_line_offset: [],
    sequence_mask_boundary_offset: [],
    sequence_surface_line_visible: [],
    sequence_head_masking_enabled: [],
    sequence_left_hand_masking_enabled: [],
    sequence_right_hand_masking_enabled: [],
    sequence_sound_events: [],
  };

  const animator = new CharacterAnimator(sequence, {}, minimalDefinition());
  const pose = animator.samplePoseAtTime(1.0);
  assert.equal(pose.mouth_state, 'O');
  assert.equal(pose.head_transform.translate_y, 400);
});

test('CharacterAnimator terminal frame samples just before sequence end', async () => {
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const sequence = {
    sequence_left_eye_open: [],
    sequence_right_eye_open: [],
    sequence_mouth_state: [],
    sequence_left_hand_visible: [],
    sequence_right_hand_visible: [],
    sequence_left_hand_transform: [],
    sequence_right_hand_transform: [],
    sequence_head_transform: [],
    sequence_surface_line_offset: [],
    sequence_mask_boundary_offset: [],
    sequence_surface_line_visible: [],
    sequence_head_masking_enabled: [],
    sequence_left_hand_masking_enabled: [
      { start_time: 0, end_time: 1, value: false },
    ],
    sequence_right_hand_masking_enabled: [],
    sequence_sound_events: [],
  };
  const leftHandClip = { style: {} };
  const animator = new CharacterAnimator(
    sequence,
    { leftHandClip },
    minimalDefinition(),
  );

  animator._renderAtTime(1.0);
  // At exact end, renderer should sample just before 1.0, preserving OFF.
  assert.equal(leftHandClip.style.clipPath, 'none');
});
