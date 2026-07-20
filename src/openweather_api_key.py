"""
API key handling for OpenWeatherMap.

The key is read from an environment variable instead of being written
in this file, so it can never be committed to git or shared by
accident when the code is zipped up or pushed to GitHub.

Set it once per terminal session:
  PowerShell:  $env:OPENWEATHER_API_KEY = "your-key-here"
  macOS/Linux: export OPENWEATHER_API_KEY="your-key-here"
"""
import os


def get_openweather_api_key():
    key = os.environ.get("OPENWEATHER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENWEATHER_API_KEY environment variable is not set. "
            "Set it before running this script (see src/api_key.py for how)."
        )
    return key