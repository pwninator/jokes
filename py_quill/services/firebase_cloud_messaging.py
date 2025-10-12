"""Firebase Cloud Messaging service."""

from common import models, utils
from firebase_admin import messaging
from firebase_functions import logger


def send_punny_joke_notification(topic: str, joke: models.PunnyJoke) -> None:
  """Send a punny joke notification to subscribers."""

  logger.info(f"""Sending joke notification to topic: {topic}
{joke.key}
{joke.setup_text}
{joke.punchline_text}""")

  notification_image_url = utils.format_image_url(
    image_url=joke.setup_image_url,
    width=256,
    image_format="webp",
    quality=50,
  )

  message = messaging.Message(
    topic=topic,
    notification=messaging.Notification(
      title=joke.setup_text,
      image=notification_image_url,
    ),
    data={
      "joke_id": joke.key,
      "setup_image_url": joke.setup_image_url,
      "punchline_image_url": joke.punchline_image_url,
    },
    android=messaging.AndroidConfig(notification=messaging.AndroidNotification(
      image=notification_image_url)),
    apns=messaging.APNSConfig(
      payload=messaging.APNSPayload(aps=messaging.Aps(mutable_content=True)),
      fcm_options=messaging.APNSFCMOptions(image=notification_image_url, ),
    ),
  )
  messaging.send(message)
  logger.info(f"Joke notification sent to topic: {topic}")
