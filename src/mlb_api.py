"""
Shared HTTP client for the MLB Stats API.

Every fetch script previously created bare requests.get() calls with
no timeout and no retry logic — one transient 500 or network blip
mid-way through a 6,000-game pull would kill the whole run. This
module gives the project a single session with:

  - automatic retries (with exponential backoff) on 429/5xx responses
  - a connection-reuse Session (faster for thousands of small calls)
  - a default timeout so a hung request can't stall a script forever
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
DEFAULT_TIMEOUT = 15  # seconds

_session = None


def get_session():
    """Returns a shared Session with retry/backoff configured."""
    global _session
    if _session is None:
        retry = Retry(
            total=4,
            backoff_factor=1,  # waits 1s, 2s, 4s, 8s between attempts
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        _session = requests.Session()
        _session.mount("https://", HTTPAdapter(max_retries=retry))
    return _session


def get_json(url, params=None, timeout=DEFAULT_TIMEOUT):
    """GET a URL and return parsed JSON, raising on HTTP errors."""
    response = get_session().get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_schedule(date=None, start_date=None, end_date=None, hydrate=None):
    """
    Calls the MLB schedule endpoint for a single date OR a date range.
    Returns the raw parsed JSON (callers decide what to extract).
    """
    params = {"sportId": 1, "gameType": "R"}
    if date is not None:
        params["date"] = date
    else:
        params["startDate"] = start_date
        params["endDate"] = end_date
    if hydrate:
        params["hydrate"] = hydrate
    return get_json(f"{MLB_API_BASE}/schedule", params=params)


def fetch_boxscore(game_pk):
    """Returns the raw boxscore JSON for one game."""
    return get_json(f"{MLB_API_BASE}/game/{game_pk}/boxscore")


def fetch_live_feed(game_pk):
    """
    Returns the live game feed (note: v1.1 endpoint, not v1).
    Contains gameData.weather with real conditions once they are
    recorded close to game time.
    """
    return get_json(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")
