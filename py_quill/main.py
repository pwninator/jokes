"""Cloud Functions entry point."""

import logging

import vertexai
from common import config, firebase_init
from firebase_functions.core import init
from functions import (admin_fns, analytics_fns, dummy_fns, joke_auto_fns,
                       joke_book_fns, joke_creation_fns, joke_fns,
                       joke_image_fns, joke_notification_fns, joke_trigger_fns,
                       stats_fns, user_fns, util_fns, web_fns)

# Configure basic logging for the application (primarily for emulator visibility)
logging.basicConfig(level=logging.INFO)

app = firebase_init.app


@init
def initialize():
  """Initializes the application."""
  vertexai.init(project=config.PROJECT_ID, location=config.PROJECT_LOCATION)


# Export the story prompt functions
# get_random_prompt = story_prompt_fns.get_random_prompt

# Export the character functions
# create_character = character_fns.create_character
# update_character = character_fns.update_character
# delete_character = character_fns.delete_character

# Export test functions
dummy_endpoint = dummy_fns.dummy_endpoint

# Export the user functions
on_user_signin = user_fns.on_user_signin
initialize_user_http = user_fns.initialize_user_http

# Export the book functions
# populate_book = book_fns.populate_book
# on_book_created = book_fns.on_book_created
# populate_page = book_fns.populate_page
# on_page_created = book_fns.on_page_created

# Export the joke functions
critique_jokes = joke_fns.critique_jokes
modify_joke_image = joke_fns.modify_joke_image
upscale_joke = joke_fns.upscale_joke
search_jokes = joke_fns.search_jokes
joke_manual_tag = joke_fns.joke_manual_tag
get_joke_bundle = joke_fns.get_joke_bundle
joke_creation_process = joke_creation_fns.joke_creation_process

# Export the joke trigger functions
on_joke_write = joke_trigger_fns.on_joke_write
on_joke_category_write = joke_trigger_fns.on_joke_category_write

# Export the joke image functions
create_ad_assets = joke_image_fns.create_ad_assets

# Export the joke auto functions
joke_daily_maintenance_scheduler = joke_auto_fns.joke_daily_maintenance_scheduler
joke_daily_maintenance_http = joke_auto_fns.joke_daily_maintenance_http

# Export the joke notification functions
send_daily_joke_http = joke_notification_fns.send_daily_joke_http
send_daily_joke_scheduler = joke_notification_fns.send_daily_joke_scheduler

# Export the joke book functions
create_joke_book = joke_book_fns.create_joke_book
get_joke_book = joke_book_fns.get_joke_book
generate_joke_book_page = joke_book_fns.generate_joke_book_page
update_joke_book_zip = joke_book_fns.update_joke_book_zip

# Export the admin functions
set_user_role = admin_fns.set_user_role

# Export util functions
run_firestore_migration = util_fns.run_firestore_migration

# Export the web functions
web_search_page = web_fns.web_search_page

# Export analytics functions
usage = analytics_fns.usage

# Export stats functions
joke_stats_calculate = stats_fns.joke_stats_calculate
joke_stats_calculate_http = stats_fns.joke_stats_calculate_http
