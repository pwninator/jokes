"""Character cloud functions."""

from common import models
from firebase_functions import https_fn, options
from functions.function_utils import (AuthError, error_response, get_user_id,
                                      success_response)
from functions.prompts import character_prompts
from services import firestore, image_client, leonardo

_IMAGE_FILE_NAME_BASE = "quill_character_portrait"

_CHARACTER_IMAGE_CLIENT_LOW = image_client.get_client(
  label="quill_character_portrait_low",
  model=image_client.ImageModel.OPENAI_RESPONSES_API_LOW,
  file_name_base=_IMAGE_FILE_NAME_BASE,
)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def create_character(req: https_fn.Request) -> https_fn.Response:
  """Creates a new character document in Firestore"""
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  print(f"Creating character: {req.get_json()}")

  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}')

  try:
    user_id = get_user_id(req)
  except AuthError:
    return error_response('User not authenticated', status=401)

  # Get the character data from request body
  request_data = req.get_json().get('data')
  character_data = request_data.get('character_data')

  if not character_data:
    return error_response(f'Character data is required: {req.get_json()}')

  name = character_data.get("name")
  age = int(character_data.get("age"))
  gender = character_data.get("gender")
  user_description = character_data.get("user_description")
  portrait_image = None
  generation_metadata = models.GenerationMetadata()

  if not name or not age or not gender or not user_description:
    return error_response(f'Invalid character data: {character_data}')

  (sanitized_description, tagline, portrait_description,
   desc_metadata) = character_prompts.generate_character_description(
     name, age, gender, user_description)
  generation_metadata.add_generation(desc_metadata)

  portrait_image = generate_portrait(
    name=name,
    age=age,
    gender=gender,
    portrait_description=portrait_description,
    user_id=user_id,
  )
  if portrait_image:
    generation_metadata.add_generation(portrait_image.generation_metadata)

  # Save to firestore
  character = firestore.create_character(
    models.Character(
      name=name,
      age=age,
      gender=gender,
      user_description=user_description,
      tagline=tagline,
      sanitized_description=sanitized_description,
      portrait_description=portrait_description,
      portrait_image_key=portrait_image.key if portrait_image else None,
      all_portrait_image_keys=[portrait_image.key] if portrait_image else [],
      owner_user_id=user_id,
      generation_metadata=generation_metadata,
    ))

  return success_response(character.to_dict(include_key=True))


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def update_character(req: https_fn.Request) -> https_fn.Response:
  """Updates an existing character document in Firestore"""
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  if req.method not in ('POST', 'PUT'):
    return error_response(f'Method must be POST or PUT: {req.method}')

  # Get the character data from request body
  request_data = req.get_json().get('data')
  character_data = request_data.get('character_data')
  if not character_data:
    return error_response(f'Character data is required: {req.get_json()}')

  new_character = models.Character.from_dict(character_data)
  generation_metadata = models.GenerationMetadata()

  try:
    user_id = get_user_id(req)
  except AuthError:
    return error_response('User not authenticated', status=401)
  character = firestore.get_character(new_character.key)

  if not character:
    return error_response(f'Character not found: {new_character}')

  if character.owner_user_id != user_id:
    return error_response(f'Character not owned by user: {new_character.key}')

  (
    sanitized_description,
    tagline,
    portrait_description,
    desc_metadata,
  ) = character_prompts.generate_character_description(
    name=new_character.name,
    age=new_character.age,
    gender=new_character.gender,
    user_description=new_character.user_description,
  )
  generation_metadata.add_generation(desc_metadata)
  new_character.tagline = tagline
  new_character.sanitized_description = sanitized_description
  new_character.portrait_description = portrait_description

  if request_data.get('generate_portrait_image'):
    new_image = generate_portrait(
      name=new_character.name,
      age=new_character.age,
      gender=new_character.gender,
      portrait_description=new_character.portrait_description,
      user_id=user_id,
    )
    if new_image:
      generation_metadata.add_generation(new_image.generation_metadata)
      new_character.portrait_image_key = new_image.key

  new_character.generation_metadata = generation_metadata
  character.update(new_character)
  firestore.update_character(character)

  return success_response(character.to_dict(include_key=True))


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def delete_character(req: https_fn.Request) -> https_fn.Response:
  """Deletes a character document from Firestore"""
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  try:
    if req.method not in ('POST', 'DELETE'):
      return error_response(f'Method must be POST or DELETE: {req.method}')

    character_id = get_data("id", req)
    if not character_id:
      return error_response(f'Character ID is required: {req}')

    firestore.delete_character(character_id)

    return success_response({})

  except Exception as e:  # pylint: disable=broad-exception-caught
    print(f"Failed to delete character: {str(e)}")
    return error_response(f'Failed to delete character: {str(e)}')


def get_data(param_name, request) -> str | None:
  """Get the data from the request."""
  request_json = request.get_json(silent=True)
  if not request_json:
    return None

  return request_json.get("data", {}).get(param_name)


def generate_portrait(name: str, age: int, gender: str,
                      portrait_description: str,
                      user_id: str) -> models.Image | None:
  """Generate a portrait for a character."""

  full_description = models.Character.get_full_description(
    name=name,
    age=age,
    gender=gender,
    portrait_description=portrait_description,
  )
  prompt = f"""A portrait of {name}.
{portrait_description}
{full_description}

{leonardo.CUSTOM_STYLE_PROMPT}
"""

  try:
    # Generate the initial image and get the callback
    image = _CHARACTER_IMAGE_CLIENT_LOW.generate_image(
      prompt=prompt,
      save_to_firestore=True,
      user_uid=user_id,
    )

    return image
  except Exception as e:
    print(f'Error generating image: {e}')
    return None
