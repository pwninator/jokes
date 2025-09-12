"""Cloud Functions for user management."""

from firebase_functions import https_fn, identity_fn, logger, options
from services import firestore as firestore_service


@identity_fn.before_user_created(
    memory=options.MemoryOption.GB_1,
    timeout_sec=600,
)
def on_user_created(
        event: identity_fn.AuthBlockingEvent) -> identity_fn.BeforeCreateResponse | None:
  """Triggered before a new Firebase Authentication user is created.

  Initializes the user document in Firestore transactionally for non-anonymous users.
  """
  try:
    user = event.data
    user_id = user.uid
    email = user.email

    logger.info(f"User creation event triggered for: {user_id}, Email: {email}")

    # Not sure if this is needed. before_user_created might not fire for anonymous users.
    if not email:
      logger.info(f"Skipping Firestore initialization for anonymous user: {user_id}")
      return None  # Allow anonymous user creation without Firestore doc

    firestore_service.initialize_user_document(user_id, email=email)

    # Return None to allow user creation to proceed
    return None

  except Exception as e:
    logger.error(f"TOP LEVEL EXCEPTION in on_user_created: {e}", exc_info=True)
    # Re-raise the exception to block user creation in case of error during init
    raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message=str(e))


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
    raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
                              message="Authentication required to initialize user document.")

  # Get user_id and email from the authentication context
  user_id = req.auth.uid
  email = req.auth.token.get('email')

  try:
    logger.info(f"Callable function received to initialize calling user: {user_id}, Email: {email}")

    if not email:
      raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                                message="Email is required to initialize user document.")

    user_created = firestore_service.initialize_user_document(user_id, email=email)
    if user_created:
      return {"success": True, "message": f"User {user_id} initialized."}
    else:
      return {"success": True, "message": f"User {user_id} already exists."}

  except Exception as e:
    logger.error(f"Error in initialize_user_http for calling user {user_id}: {e}", exc_info=True)
    return {"success": False, "message": f"Error initializing user {user_id}: {e}"}
