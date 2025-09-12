"""Cloud Functions entry point."""

import logging

import vertexai
from common import config
from firebase_admin import initialize_app
from firebase_functions.core import init
from functions import (admin_fns, analytics_fns, book_fns, character_fns,
                       dummy_fns, joke_fns, story_prompt_fns, user_fns,
                       util_fns, web_fns)

# Configure basic logging for the application (primarily for emulator visibility)
logging.basicConfig(level=logging.INFO)

app = initialize_app()


@init
def initialize():
  """Initializes the application."""
  vertexai.init(project=config.PROJECT_ID, location=config.PROJECT_LOCATION)


# Export the story prompt functions
get_random_prompt = story_prompt_fns.get_random_prompt

# Export the character functions
create_character = character_fns.create_character
update_character = character_fns.update_character
delete_character = character_fns.delete_character

# Export test functions
dummy_endpoint = dummy_fns.dummy_endpoint

# Export the user functions
on_user_created = user_fns.on_user_created
initialize_user_http = user_fns.initialize_user_http

# Export the book functions
populate_book = book_fns.populate_book
on_book_created = book_fns.on_book_created
populate_page = book_fns.populate_page
on_page_created = book_fns.on_page_created

# Export the joke functions
create_joke = joke_fns.create_joke
critique_jokes = joke_fns.critique_jokes
populate_joke = joke_fns.populate_joke
modify_joke_image = joke_fns.modify_joke_image
send_daily_joke_http = joke_fns.send_daily_joke_http
send_daily_joke_scheduler = joke_fns.send_daily_joke_scheduler
search_jokes = joke_fns.search_jokes
on_joke_write = joke_fns.on_joke_write

# Export the admin functions
set_user_role = admin_fns.set_user_role

# Export util functions
run_firestore_migration = util_fns.run_firestore_migration

# Export the web functions
web_search_page = web_fns.web_search_page

# Export analytics functions
usage = analytics_fns.usage
