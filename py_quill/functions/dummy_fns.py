"""Test cloud functions."""

import json
import pprint

from agents import agents_common, constants
from agents.endpoints import all_agents
from common import image_generation
from firebase_functions import https_fn, options


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """Simple test endpoint that returns a success message.

  Args:
      req: The HTTP request.

  Returns:
      HTTP response with test message.
  """
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method != 'GET':
    return https_fn.Response(json.dumps({
      "error": "Only GET requests are supported",
      "success": False
    }),
                             status=405,
                             mimetype='application/json')

  joke_categorizer_agent = all_agents.get_joke_categorizer_agent_adk_app()
  output, final_state, agent_generation_metadata = agents_common.run_agent(
    adk_app=joke_categorizer_agent,
    inputs="Group jokes into categories.",
    user_id="dummy_user",
  )

  return_val = f"""
<html>
<body>
<p>Output: {output}</p>
<p>Final State: {pprint.pformat(final_state, width=120, sort_dicts=False)}</p>
<p>Agent Generation Metadata: {agent_generation_metadata}</p>
</body>
</html>
"""

  return https_fn.Response(return_val, status=200, mimetype='text/html')
