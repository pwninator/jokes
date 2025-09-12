"""Wikipedia API client library."""

from dataclasses import dataclass
import re


import requests
from bs4 import BeautifulSoup

_session = None  # pylint: disable=invalid-name


def _get_session() -> requests.Session:
  """Get a requests session."""
  global _session  # pylint: disable=global-statement
  if _session is None:
    _session = requests.Session()
  return _session


@dataclass(frozen=True)
class WikipediaSearchResult:
  """A Wikipedia search result."""
  title: str
  url: str
  snippet: str


def search(query: str, num_results: int = 1) -> list[WikipediaSearchResult]:
  """Search Wikipedia and return a list of article titles.

  Args:
      query: Search query string
      num_results: Maximum number of results to return (default: 1)

  Returns:
      List of Wikipedia article titles and URLs matching the query
  """
  search_url = "https://en.wikipedia.org/w/api.php"
  web_url = "https://en.wikipedia.org/wiki"
  params = {
      "action": "query",
      "list": "search",
      "format": "json",
      "formatversion": "2",
      "srlimit": num_results,
      "srsearch": query
  }
  response = _get_session().get(url=search_url, params=params, timeout=10)
  response.raise_for_status()
  response_dict = response.json()
  search_results = response_dict.get("query", {}).get("search", [])

  results = []
  for result in search_results:
    title = result["title"]
    snippet = result["snippet"]
    url = f"{web_url}/{requests.utils.quote(title)}"
    results.append(WikipediaSearchResult(title, url, snippet))
  return results


def get_text(title: str) -> str:
  """Get the main text content of a Wikipedia article.

  Args:
      title: Wikipedia article title

  Returns:
      Article text with references and other sections removed
  """
  # Escape the title for use in URL
  escaped_title = requests.utils.quote(title)
  get_url = f"https://en.wikipedia.org/api/rest_v1/page/html/{escaped_title}"
  print(f"Getting Wikipedia article text: {get_url}")

  # Allow redirects and increase timeout
  response = _get_session().get(url=get_url, timeout=10, allow_redirects=True)
  response.raise_for_status()

  html_text = str(response.text.encode('utf-8').decode('ascii', 'ignore'))
  soup = BeautifulSoup(html_text, features="html.parser")
  text = soup.get_text()

  # Remove references and other sections
  text = re.sub(
      r"\n(See also|References|Bibliography|Further reading|External links)\n.*",
      "",
      text,
      flags=re.DOTALL
  )

  return text
