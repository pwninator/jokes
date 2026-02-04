"""Test cloud functions (manual utilities)."""

from __future__ import annotations

from common import utils
from firebase_functions import https_fn, options
from functions import function_utils
from functions.function_utils import get_param
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
    script = get_param(req, "script", "") or ""
    speaker1_name = get_param(req, "speaker1_name", "Speaker 1") or ""
    speaker1_voice = get_param(req, "speaker1_voice", "") or ""
    speaker2_name = get_param(req, "speaker2_name", "Speaker 2") or ""
    speaker2_voice = get_param(req, "speaker2_voice", "") or ""

    speakers: dict[str, gen_audio.Voice] = {}
    if speaker1_name.strip() and speaker1_voice.strip():
      speakers[speaker1_name.strip()] = gen_audio.Voice.from_identifier(
        speaker1_voice.strip(),
        model=gen_audio.VoiceModel.GEMINI,
      )
    if speaker2_name.strip() and speaker2_voice.strip():
      speakers[speaker2_name.strip()] = gen_audio.Voice.from_identifier(
        speaker2_voice.strip(),
        model=gen_audio.VoiceModel.GEMINI,
      )

    if not script.strip():
      return function_utils.error_response(
        "Missing required parameter 'script'",
        req=req,
        status=400,
      )
    if not speakers:
      return function_utils.error_response(
        "Provide at least one (speaker name, voice name) pair",
        req=req,
        status=400,
      )

    try:
      gcs_uri, _ = gen_audio.generate_multi_turn_dialog(
        script=script,
        speakers=speakers,
        output_filename_base="dummy_multi_turn_dialog",
      )
      try:
        audio_url = cloud_storage.get_signed_url(gcs_uri)
      except Exception:
        # Signed URLs may not work in all environments (e.g. local emulators).
        audio_url = cloud_storage.get_public_url(gcs_uri)

      return function_utils.success_response(
        {
          "audio_url": audio_url,
          "audio_gcs_uri": gcs_uri,
          "emulator": utils.is_emulator(),
        },
        req=req,
      )
    except Exception as e:
      return function_utils.error_response(str(e), req=req, status=500)

  default_script = (
    "Alice: Hey Bob, do you have any jokes about cookies?\n"
    "Bob: I do, but they're a little crumby.\n"
    "Alice: That's okay. I can handle the crumbs.\n")
  default_speaker1_name = "Alice"
  default_speaker2_name = "Bob"
  default_speaker1_voice = gen_audio.Voice.GEMINI_KORE
  default_speaker2_voice = gen_audio.Voice.GEMINI_PUCK

  gemini_voice_options = gen_audio.Voice.voices_for_model(
    gen_audio.VoiceModel.GEMINI)
  voice_options_html = "\n".join([
    f'<option value="{voice.name}"'
    f' {"selected" if voice is default_speaker1_voice else ""}>'
    f'{voice.voice_name} ({voice.gender.value})</option>'
    for voice in gemini_voice_options
  ])
  voice_options_html_2 = "\n".join([
    f'<option value="{voice.name}"'
    f' {"selected" if voice is default_speaker2_voice else ""}>'
    f'{voice.voice_name} ({voice.gender.value})</option>'
    for voice in gemini_voice_options
  ])

  html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Generate Multi-Speaker Audio</title>
  <style>
    body {{ font-family: system-ui, Arial, sans-serif; margin: 24px; }}
    input, textarea, select {{ width: 100%; max-width: 900px; }}
    textarea {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
    .row {{ display: flex; gap: 12px; max-width: 900px; }}
    .col {{ flex: 1; }}
    .muted {{ color: #666; font-size: 12px; }}
    .error {{ color: #b00020; white-space: pre-wrap; }}
    .ok {{ color: #0b6b0b; }}
  </style>
</head>
<body>
  <h1>Generate Multi-Speaker Audio (Gemini)</h1>
  <p class="muted">Speaker labels in the script must match the speaker names below.</p>

  <form id="genForm">
    <label for="script">Script</label><br>
    <textarea id="script" name="script" rows="10" required>{default_script}</textarea><br><br>

    <div class="row">
      <div class="col">
        <label for="speaker1_name">Speaker 1 Name</label><br>
        <input id="speaker1_name" name="speaker1_name" value="{default_speaker1_name}" required>
      </div>
      <div class="col">
        <label for="speaker1_voice">Speaker 1 Voice</label><br>
        <select id="speaker1_voice" name="speaker1_voice" required>
          {voice_options_html}
        </select>
      </div>
    </div>
    <br>
    <div class="row">
      <div class="col">
        <label for="speaker2_name">Speaker 2 Name</label><br>
        <input id="speaker2_name" name="speaker2_name" value="{default_speaker2_name}" required>
      </div>
      <div class="col">
        <label for="speaker2_voice">Speaker 2 Voice</label><br>
        <select id="speaker2_voice" name="speaker2_voice" required>
          {voice_options_html_2}
        </select>
      </div>
    </div>
    <br>

    <button id="generateBtn" type="submit">Generate</button>
    <span id="status" class="muted"></span>
  </form>

  <hr>
  <div id="result"></div>
  <audio id="audioPlayer" controls style="display:none; max-width: 900px;"></audio>

  <script>
    const form = document.getElementById('genForm');
    const statusEl = document.getElementById('status');
    const resultEl = document.getElementById('result');
    const audioEl = document.getElementById('audioPlayer');
    const btn = document.getElementById('generateBtn');

    function setStatus(text) {{
      statusEl.textContent = text || '';
    }}

    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      setStatus('Generating...');
      resultEl.innerHTML = '';
      audioEl.style.display = 'none';
      audioEl.removeAttribute('src');
      btn.disabled = true;

      const payload = {{
        data: {{
          script: document.getElementById('script').value,
          speaker1_name: document.getElementById('speaker1_name').value,
          speaker1_voice: document.getElementById('speaker1_voice').value,
          speaker2_name: document.getElementById('speaker2_name').value,
          speaker2_voice: document.getElementById('speaker2_voice').value,
        }}
      }};

      try {{
        const resp = await fetch(window.location.href, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload),
        }});

        const json = await resp.json();
        if (!resp.ok || json.data?.error) {{
          const message = json.data?.error || `HTTP ${{resp.status}}`;
          resultEl.innerHTML = `<div class="error">Error: ${{message}}</div>`;
          setStatus('');
          return;
        }}

        const audioUrl = json.data.audio_url;
        const gcsUri = json.data.audio_gcs_uri;

        resultEl.innerHTML = `
          <div class="ok">Done.</div>
          <div><a href="${{audioUrl}}" target="_blank" rel="noopener">Download audio</a></div>
          <div class="muted">${{gcsUri}}</div>
        `;
        audioEl.src = audioUrl;
        audioEl.style.display = 'block';
        setStatus('');
      }} catch (err) {{
        resultEl.innerHTML = `<div class="error">Error: ${{err}}</div>`;
        setStatus('');
      }} finally {{
        btn.disabled = false;
      }}
    }});
  </script>
</body>
</html>
"""
  return https_fn.Response(html, status=200, mimetype="text/html")
