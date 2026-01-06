"""Cloud Functions for user management."""

from firebase_functions import https_fn, identity_fn, logger, options
from services import firestore as firestore_service


@identity_fn.before_user_signed_in(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
  min_instances=1,
)
def on_user_signin(
  event: identity_fn.AuthBlockingEvent
) -> identity_fn.BeforeSignInResponse | None:
  """Triggered before a Firebase Authentication user signs in.

  Ensures the user document exists in Firestore for non-anonymous users.
  """
  try:
    user = event.data
    user_id = user.uid
    email = user.email

    if not email:
      return None

    user_created = firestore_service.initialize_user_document(
      user_id,
      email=email,
    )
    if user_created:
      logger.info(
        f"Initialized Firestore user document on sign-in for: {user_id}")

    return None

  except Exception as e:
    logger.error(f"TOP LEVEL EXCEPTION in on_user_signin: {e}", exc_info=True)
    return None


@https_fn.on_call(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def initialize_user_http(req: https_fn.CallableRequest) -> dict:
  """Callable function to manually initialize the *calling* user's Firestore document transactionally.

  User ID is obtained from the authentication context.
  """
  # Check for authenticated user
  if not req.auth or not req.auth.uid:
    raise https_fn.HttpsError(
      code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
      message="Authentication required to initialize user document.")

  # Get user_id and email from the authentication context
  user_id = req.auth.uid
  email = req.auth.token.get('email')

  try:
    logger.info(
      f"Callable function received to initialize calling user: {user_id}, Email: {email}"
    )

    if not email:
      raise https_fn.HttpsError(
        code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
        message="Email is required to initialize user document.")

    user_created = firestore_service.initialize_user_document(user_id,
                                                              email=email)
    if user_created:
      return {"success": True, "message": f"User {user_id} initialized."}
    else:
      return {"success": True, "message": f"User {user_id} already exists."}

  except Exception as e:
    logger.error(
      f"Error in initialize_user_http for calling user {user_id}: {e}",
      exc_info=True)
    return {
      "success": False,
      "message": f"Error initializing user {user_id}: {e}"
    }
