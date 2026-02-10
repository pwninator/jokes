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

test('CharacterAnimator matches canonical fixture samples', async () => {
  const fixture = loadCanonicalFixture();
  const { CharacterAnimator } = await loadCharacterAnimatorModule();

  const animator = new CharacterAnimator(fixture.sequence, {}, {});
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
  });
});

test('CharacterAnimator matches canonical fixture sound windows', async () => {
  const fixture = loadCanonicalFixture();
  const { CharacterAnimator } = await loadCharacterAnimatorModule();
  const animator = new CharacterAnimator(fixture.sequence, {}, {});

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
