# Character Animator Canonical Spec (v1)

This document defines the runtime semantics for evaluating a
`PosableCharacterSequence`.

The initial v1 spec + fixture were generated from the Python implementation in
`py_quill/common/character_animator.py`. Going forward, this spec is the
source of truth.

The following implementations must strictly conform to this spec:

- `py_quill/common/character_animator.py`
- `py_quill/web/static/js/character_animator.js`
- `lib/src/features/character/application/character_animator.dart`

## 1. Time Model

- All times are seconds (`float`) on a sequence-local timeline.
- Every event must provide both `start_time` and `end_time`.
- `end_time` must satisfy `end_time >= start_time`.
- A sequence duration is the max of every event's `end_time`.
- Sampling is random-access: callers may query any `t` in any order.

## 2. Event Interval Rules

- For boolean and mouth tracks, an event is active when:
  `event.start_time <= t < event_end`.
- `event_end` is always `event.end_time`.
- Instantaneous state changes are represented explicitly with
  `end_time == start_time`.
- If no event is active at `t`, tracks return their defaults:
  - eyes: `True`
  - hand visibility: `True`
  - mouth: `CLOSED`

## 3. Transform Track Rules

- Tracks are sorted by `start_time`.
- While inside an event (`start <= t < end`), transform is linear interpolation
  from previous event's target (or identity for first event) to current target.
- For zero-duration transform events (`end == start`), the target transform
  applies instantly.
- Before first transform event: identity transform.
- Between transform events and after last transform event: hold the most recent
  target transform.

## 4. Sound Event Rules

- Sound events are keyed by `start_time`.
- Sound events must include `end_time`.
- Sound events must have positive duration (`end_time > start_time`).
- Playback starts at `start_time` and is forcibly stopped at `end_time`.
- To play the full clip, set `end_time >= start_time + clip_duration_sec`.
- It is valid to stop early by setting
  `end_time < start_time + clip_duration_sec`.
- `sound_events_between(start, end)` returns events in `[start, end)` when
  called with `include_start=True, include_end=False` (default frame-window
  behavior).
- Ordering is ascending by `start_time`.

## 5. Sequential Wrapper

- `generate_frames(character, fps)` is defined in terms of random-access
  evaluation.
- For frame `i`, `t = i / fps`.
- Sounds for that frame are selected from `[t, t + 1/fps)`.

## 6. Canonical Fixture

- The canonical IO fixture for this spec version is:
  `py_quill/common/testdata/character_animator_canonical_v1.json`
- Python and Flutter tests should assert against this fixture to ensure
  behavior parity.
