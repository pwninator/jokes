"""Operations for jokes."""

from services import firestore, image_client, cloud_storage
from common import models

def upscale_joke(joke_id: str) -> models.PunnyJoke:
    """Upscales a joke's images.

    This function is idempotent. If the joke already has upscaled URLs,
    it will return immediately.
    """
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
        raise ValueError(f'Joke not found: {joke_id}')

    if joke.setup_image_url_upscaled and joke.punchline_image_url_upscaled:
        return joke

    new_size = 4096
    client = image_client.get_client(
        label="upscale_joke",
        model=image_client.ImageModel.IMAGEN_1,
        file_name_base="upscaled_joke_image",
    )

    if joke.setup_image_url and not joke.setup_image_url_upscaled:
        gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
            joke.setup_image_url
        )
        upscaled_image = client.upscale_image(gcs_uri=gcs_uri, new_size=new_size)
        joke.setup_image_url_upscaled = upscaled_image.url_upscaled
        joke.generation_metadata.add_generation(
            upscaled_image.generation_metadata
        )

    if joke.punchline_image_url and not joke.punchline_image_url_upscaled:
        gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
            joke.punchline_image_url
        )
        upscaled_image = client.upscale_image(gcs_uri=gcs_uri, new_size=new_size)
        joke.punchline_image_url_upscaled = upscaled_image.url_upscaled
        joke.generation_metadata.add_generation(
            upscaled_image.generation_metadata
        )

    return joke