"""
API key handling.

The key is read from an environment variable instead of being written
in this file, so it can never be committed to git or shared by
accident when the code is zipped up or pushed to GitHub.

Set it once per terminal session:
  PowerShell:  $env:ODDS_API_KEY = "your-key-here"
  macOS/Linux: export ODDS_API_KEY="your-key-here"
"""
import os


def get_odds_api_key():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY environment variable is not set. "
            "Set it before running this script (see src/api_key.py for how)."
        )
    return key
