"""Test cloud functions (manual utilities)."""

from __future__ import annotations

from firebase_functions import https_fn, options
from functions import function_utils
from services import cloud_storage, gen_audio


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Manual endpoint to generate multi-speaker dialog audio via Gemini."""
  if preflight := function_utils.handle_cors_preflight(req):
    return preflight
  if health := function_utils.handle_health_check(req):
    return health

  if req.method == "POST":
    if not getattr(req, "is_json", False):
      return function_utils.error_response("Expected JSON body",
                                           error_type="invalid_request",
                                           status=400,
                                           req=req)
    payload = req.get_json() or {}
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    script = (data.get("script") or "").strip()
    speaker1_name = (data.get("speaker1_name") or "").strip()
    speaker2_name = (data.get("speaker2_name") or "").strip()
    speaker1_voice_raw = (data.get("speaker1_voice") or "").strip()
    speaker2_voice_raw = (data.get("speaker2_voice") or "").strip()

    if not script:
      return function_utils.error_response("script is required",
                                           error_type="invalid_request",
                                           status=400,
                                           req=req)
    if not speaker1_name or not speaker2_name:
      return function_utils.error_response("speaker names are required",
                                           error_type="invalid_request",
                                           status=400,
                                           req=req)
    if not speaker1_voice_raw or not speaker2_voice_raw:
      return function_utils.error_response("speaker voices are required",
                                           error_type="invalid_request",
                                           status=400,
                                           req=req)

    try:
      speaker1_voice = gen_audio.Voice.from_identifier(speaker1_voice_raw)
      speaker2_voice = gen_audio.Voice.from_identifier(speaker2_voice_raw)
    except ValueError as exc:
      return function_utils.error_response(str(exc),
                                           error_type="invalid_request",
                                           status=400,
                                           req=req)

    audio_gcs_uri, _metadata = gen_audio.generate_multi_turn_dialog(
      script=script,
      speakers={
        speaker1_name: speaker1_voice,
        speaker2_name: speaker2_voice,
      },
      output_filename_base="dummy_multi_speaker_dialog",
    )
    audio_url = cloud_storage.get_signed_url(audio_gcs_uri)
    return function_utils.success_response(
      {
        "audio_url": audio_url,
        "audio_gcs_uri": audio_gcs_uri,
      },
      req=req,
    )

  html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Generate Multi-Speaker Audio</title>
</head>
<body>
  <h1>Generate Multi-Speaker Audio</h1>
  <form id="genForm">
    <div>
      <label for="script">Script</label><br/>
      <textarea id="script" name="script" rows="6" cols="60">Alice: Hello
Bob: Hi</textarea>
    </div>
    <div>
      <label>Speaker 1</label><br/>
      <input type="text" name="speaker1_name" value="Alice"/>
      <input type="text" name="speaker1_voice" value="GEMINI_KORE"/>
    </div>
    <div>
      <label>Speaker 2</label><br/>
      <input type="text" name="speaker2_name" value="Bob"/>
      <input type="text" name="speaker2_voice" value="GEMINI_PUCK"/>
    </div>
    <button type="submit">Generate</button>
  </form>

  <pre id="result"></pre>

  <script>
    document.getElementById('genForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const data = {
        script: form.script.value,
        speaker1_name: form.speaker1_name.value,
        speaker1_voice: form.speaker1_voice.value,
        speaker2_name: form.speaker2_name.value,
        speaker2_voice: form.speaker2_voice.value,
      };

      const resp = await fetch(window.location.href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data }),
      });
      const json = await resp.json();
      document.getElementById('result').textContent = JSON.stringify(json, null, 2);
    });
  </script>
</body>
</html>
"""
  return https_fn.Response(html, status=200, mimetype="text/html")
