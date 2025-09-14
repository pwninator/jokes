"""Analytics and usage tracking functions."""

from firebase_functions import https_fn, logger, options
from functions.function_utils import (error_response, get_int_param,
                                      get_user_id, success_response)
from services import firestore as firestore_service


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=10,
)
def usage(req: https_fn.Request) -> https_fn.Response:
  """Track user usage and update per-day distinct usage counter.

  Expects Authorization header with a Firebase ID token. Optionally accepts a
  "num_days_used" parameter for client-reported count (logged only).
  """
  try:
    # Skip processing for health check requests
    if req.path == "/__/health":
      return https_fn.Response("OK", status=200)

    if req.method not in ['GET', 'POST']:
      return error_response(f'Method not allowed: {req.method}')

    user_id = get_user_id(req, allow_unauthenticated=True)
    if not user_id:
      return error_response("Unauthenticated request")

    # Parse client-reported metrics using helpers
    client_days_used_int = get_int_param(req, 'num_days_used', default=None)
    client_num_saved_int = get_int_param(req, 'num_saved', default=None)
    client_num_viewed_int = get_int_param(req, 'num_viewed', default=None)
    client_num_shared_int = get_int_param(req, 'num_shared', default=None)

    final_days_used = firestore_service.upsert_joke_user_usage(
      user_id,
      client_num_days_used=client_days_used_int,
      client_num_saved=client_num_saved_int,
      client_num_viewed=client_num_viewed_int,
      client_num_shared=client_num_shared_int,
    )

    # Client counters are persisted within upsert_joke_user_usage

    logger.info(
      "usage updated",
      extra={
        "json_fields": {
          "user_id": user_id,
          "num_distinct_day_used_server": final_days_used,
          "num_distinct_day_used_client": client_days_used_int,
          "client_num_saved": client_num_saved_int,
          "client_num_viewed": client_num_viewed_int,
          "client_num_shared": client_num_shared_int,
        }
      },
    )
    print(f"""usage updated:
user_id: {user_id}
num_distinct_day_used_server: {final_days_used}
num_distinct_day_used_client: {client_days_used_int}
client_num_saved: {client_num_saved_int}
client_num_viewed: {client_num_viewed_int}
client_num_shared: {client_num_shared_int}
""")

    return success_response({
      "user_id": user_id,
      "num_distinct_day_used": final_days_used,
    })
  except Exception as e:  # pylint: disable=broad-except
    logger.error("usage failed: %s", e)
    return error_response(str(e))
