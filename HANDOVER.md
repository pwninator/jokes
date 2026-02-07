# Audio Splitting Improvement Handover

## Problem Description
The current system splits a multi-turn joke dialog (Setup, Response, Punchline) into separate audio files based solely on timing data returned by the TTS provider (ElevenLabs). This data is occasionally inaccurate, leading to:
1.  **Bleeding:** The end of the "Setup" clip might contain the first syllable of the "Response".
2.  **Truncation:** The "Response" clip might start too late, missing its first syllable.

## Agreed Solution
We need to implement a **"Scan and Split"** strategy that uses the TTS timing data as a rough guide but relies on audio analysis to find the true silence gap between turns.

### Key Logic
1.  **Search Window:** For each split boundary (e.g., between Setup and Response), define a search window centered on the TTS-reported timestamp (e.g., `timestamp +/- 0.2s`).
2.  **Silence Detection:** Scan the audio within that window to find the point of minimum RMS energy (the "true" silence).
3.  **Splitting:** Cut the audio at that refined split point.
4.  **Trimming:** Trim any leading/trailing silence from the resulting clips using a standard silence threshold (e.g., `librosa.effects.trim`).
5.  **Timing Adjustment:** Update the `JokeAudioTiming` (word-level timestamps) for each clip. The new timestamps must be shifted by:
    *   The start time of the slice within the original file.
    *   PLUS the duration of any leading silence trimmed from the start of the clip.

## Implementation Details

### 1. New File: `py_quill/common/audio_operations.py`
Create this file to house generic audio manipulation logic. It should not depend on "jokes" or higher-level models.

**Functions:**
*   `find_best_split_point(wav_bytes, search_start_sec, search_end_sec) -> float`:
    *   Decodes the WAV (using `librosa` or `soundfile`).
    *   Calculates RMS energy for the slice.
    *   Returns the timestamp of the frame with the lowest energy.
*   `trim_silence(wav_bytes) -> tuple[bytes, float]`:
    *   Trims silence from the start/end.
    *   Returns `(trimmed_wav_bytes, duration_of_trimmed_leading_silence)`.
*   `split_wav_at_point(wav_bytes, split_point_sec) -> tuple[bytes, bytes]`:
    *   Splits a WAV byte string into two valid WAVs at the given time.
*   `split_wav_on_silence(...)`:
    *   Migrate the existing `_split_wav_bytes_on_two_pauses` logic from `joke_operations.py` to here.

### 2. Update: `py_quill/common/joke_operations.py`
Refactor this file to use the new `audio_operations` module.

**Changes:**
*   Import `audio_operations`.
*   **Update `_split_joke_dialog_wav_by_timing`**:
    *   Calculate rough boundaries from `timing.voice_segments` (as it does now).
    *   Call `audio_operations.find_best_split_point` for the gap between turns (Setup/Response and Response/Punchline).
    *   Call `audio_operations.split_wav_at_point` using the found points.
    *   Call `audio_operations.trim_silence` on the resulting parts.
    *   **Crucial:** When shifting word timings in `_shift_words`, the `offset_sec` for a clip is now: `split_start_time + trimmed_leading_silence`.
*   **Update `generate_joke_audio`**:
    *   Use `audio_operations.split_wav_on_silence` instead of the local helper.
*   **Cleanup:** Remove the local helper functions (`_split_wav_bytes_on_two_pauses`, `_slice_wav_bytes`, `_read_wav_bytes`, etc.).

## Testing
*   Create `py_quill/common/audio_operations_test.py`.
*   Use synthetic WAV generation (sine waves + silence) to verify that `find_best_split_point` correctly identifies silence in a gap, even if the "search window" includes some noise.
*   Verify `trim_silence` returns the correct lead duration.
