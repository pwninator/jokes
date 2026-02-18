"""Manual utility function endpoints."""

from __future__ import annotations

import html

from firebase_functions import https_fn, options
from functions import function_utils
from services import amazon


def _render_usage_html() -> str:
  """Render a simple form for manually listing Amazon Ads profiles."""
  return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Amazon Ads Profiles</title>
</head>
<body>
  <h1>Fetch Amazon Ads Profiles</h1>
  <p>Submit this form to fetch profile scope IDs and render them as HTML.</p>
  <form method="post">
    <label for="region">Region:</label>
    <select id="region" name="region">
      <option value="all" selected>all</option>
      <option value="na">na</option>
      <option value="eu">eu</option>
      <option value="fe">fe</option>
    </select>
    <br/><br/>
    <button type="submit">Fetch Profiles</button>
  </form>
</body>
</html>"""


def _render_profiles_html(
  *,
  requested_region: str,
  profiles: list[amazon.AmazonAdsProfile],
) -> str:
  """Render Amazon Ads profiles as an HTML table."""
  rows: list[str] = []
  for profile in profiles:
    rows.append(
      "<tr>"
      f"<td>{html.escape(profile.profile_id)}</td>"
      f"<td>{html.escape(profile.region)}</td>"
      f"<td>{html.escape(profile.api_base)}</td>"
      f"<td>{html.escape(profile.country_code)}</td>"
      "</tr>")

  table_html = (
    "<p>No profiles found.</p>" if not rows else
    "<table border='1' cellpadding='6' cellspacing='0'>"
    "<thead><tr>"
    "<th>Profile ID</th>"
    "<th>Region</th>"
    "<th>API Base</th>"
    "<th>Country</th>"
    "</tr></thead>"
    f"<tbody>{''.join(rows)}</tbody>"
    "</table>")

  return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Amazon Ads Profiles</title>
</head>
<body>
  <h1>Amazon Ads Profiles</h1>
  <p><strong>Requested Region:</strong> {html.escape(requested_region)}</p>
  <p><strong>Profile Count:</strong> {len(profiles)}</p>
  {table_html}
</body>
</html>"""


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: https_fn.Request) -> https_fn.Response:
  """List Amazon Ads profiles by calling the shared Amazon Ads service client."""
  if preflight := function_utils.handle_cors_preflight(req):
    return preflight
  if health := function_utils.handle_health_check(req):
    return health

  if req.method == "GET":
    return function_utils.html_response(_render_usage_html(), req=req)

  if req.method != "POST":
    return function_utils.error_response(
      "Only GET and POST requests are supported",
      error_type="invalid_request",
      status=405,
      req=req,
    )

  region = (function_utils.get_str_param(req, "region", "all")
            or "all").strip().lower()
  try:
    profiles = amazon.get_profiles(region=region)
    return function_utils.html_response(
      _render_profiles_html(requested_region=region, profiles=profiles),
      req=req,
    )
  except ValueError as exc:
    return function_utils.error_response(
      str(exc),
      error_type="invalid_request",
      status=400,
      req=req,
    )
  except amazon.AmazonAdsError as exc:
    return function_utils.error_response(
      str(exc),
      error_type="amazon_api_error",
      status=502,
      req=req,
    )
