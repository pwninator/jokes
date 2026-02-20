"""Manual utility function endpoints."""

from __future__ import annotations

import html

import flask
from firebase_functions import https_fn, options
from functions import function_utils
from services import amazon


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  timeout_sec=600,
)
def dummy_endpoint(req: flask.Request) -> flask.Response:
  """List Amazon Ads profiles by calling the shared Amazon Ads service client."""
  if preflight := function_utils.handle_cors_preflight(req):
    return preflight
  if health := function_utils.handle_health_check(req):
    return health

  if req.method != "GET":
    return function_utils.error_response(
      "Only GET requests are supported",
      error_type="invalid_request",
      status=405,
      req=req,
    )

  # yapf: disable
  products = [
    "joke book", "joke books", "jokes",
    "kids joke book", "kids joke books",
    "kid joke book", "kid joke books",
    "childrens joke book", "childrens joke books",
    "children's joke book", "children's joke books",
    "funny jokes", "funny joke book",
    "silly jokes","silly joke book",
    "best joke book",
  ]
  numbers = [
    "5", "6", "7", "8", "9",
    "five", "six", "seven", "eight", "nine",
    "5-6", "5-7", "5-8", "5-9",
    "6-7", "6-8", "6-9",
    "7-8", "7-9",
    "8-9",
    "5 to 6", "5 to 7", "5 to 8", "5 to 9",
    "6 to 7", "6 to 8", "6 to 9",
    "7 to 8", "7 to 9",
    "8 to 9",
    "five to six", "five to seven", "five to eight", "five to nine",
    "six to seven", "six to eight", "six to nine",
    "seven to eight", "seven to nine",
    "eight to nine",
  ]
  ages = [
    "",
    "year old", "year olds",
    "years old",
    "year-old", "year-olds",
    "yo", "y.o."
  ]
  recipients = [
    "",
    "kids", "children",
    "boy", "boys",
    "girl", "girls",
    "son", "daughter",
    "grandson", "granddaughter",
  ]
  grades = [
    "kindergarten", "kindergartener", "kindergarteners",
    "1st grade", "1st grader", "1st graders",
    "first grade", "first grader", "first graders",
    "2nd grade", "2nd grader", "2nd graders",
    "second grade", "second grader", "second graders",
    "3rd grade", "3rd grader", "3rd graders",
    "third grade", "third grader", "third graders"
  ]
  proficiencies = [
    "my first",
    "easy to read", "easy read",
    "beginning reader", "early reader",
    "level 1", "level 2", "level 3",
    "first reader", "reluctant reader"
  ]
  # yapf: enable

  phrases: list[str] = []

  for product in products:
    phrases.append(product.strip())
    for recipient in recipients:
      if recipient not in product:
        phrases.append(f"{product} for {recipient}".strip())
        for number in numbers:
          for age in ages:
            phrases.append(f"{product} for {number} {age} {recipient}".strip())
            phrases.append(f"{product} for {recipient} {number} {age}".strip())

    for grade in grades:
      phrases.append(f"{product} for {grade}".strip())

    for proficiency in proficiencies:
      phrases.append(f"{proficiency} {product}".strip())

  try:

    return function_utils.html_response(
      "\n".join(phrases),
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
