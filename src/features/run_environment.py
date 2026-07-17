"""
Run-environment features — built for the TOTALS model, which needs
"how many runs happen in this game" signals rather than the win
model's differential signals (who's better than whom).

All features follow the project's leakage-safe pattern: every value is
computed from strictly earlier games via shift(1), so a game's own
score never influences its own pregame features.

  - team rolling runs scored / allowed (last N games)
  - park run factor: how run-friendly this home park has been,
    relative to the league, using only games before this one
    (the feature that knows about Coors Field)
"""
import pandas as pd


def _team_long(games_df):
    """One row per (team, game) with runs scored/allowed and date order."""
    games = games_df.sort_values(["date", "game_pk"]).reset_index(drop=True)
    sides = []
    for side, opp in [("home", "away"), ("away", "home")]:
        view = games[["game_pk", "date", f"{side}_team", f"{side}_score", f"{opp}_score"]].rename(
            columns={f"{side}_team": "team",
                     f"{side}_score": "runs_scored",
                     f"{opp}_score": "runs_allowed"}
        )
        view["side"] = side
        sides.append(view)
    return pd.concat(sides, ignore_index=True).sort_values(["date", "game_pk"]).reset_index(drop=True)


def add_run_environment(games_df, last_n=15, min_games=3):
    """
    Adds home_/away_team_runs_scored_avg and _runs_allowed_avg:
    each team's average runs scored and allowed over its previous
    `last_n` games (shift(1) — current game excluded). Early-season
    gaps are filled with the league's expanding pregame average, also
    shifted, so no value ever sees its own game.
    """
    games_df = games_df.sort_values(["date", "game_pk"]).reset_index(drop=True)
    long = _team_long(games_df)

    for stat in ["runs_scored", "runs_allowed"]:
        long[f"{stat}_avg"] = (
            long.groupby("team")[stat]
            .transform(lambda s: s.shift(1).rolling(last_n, min_periods=min_games).mean())
        )

    # League expanding pregame average of runs-per-team-per-game (shifted)
    league_avg = long["runs_scored"].expanding().mean().shift(1)
    for stat in ["runs_scored", "runs_allowed"]:
        long[f"{stat}_avg"] = long[f"{stat}_avg"].fillna(league_avg).fillna(4.5)

    for side in ["home", "away"]:
        side_view = long[long["side"] == side][["game_pk", "runs_scored_avg", "runs_allowed_avg"]]
        side_view = side_view.rename(columns={
            "runs_scored_avg": f"{side}_team_runs_scored_avg",
            "runs_allowed_avg": f"{side}_team_runs_allowed_avg",
        })
        games_df = games_df.merge(side_view, on="game_pk", how="left")

    return games_df


def add_park_run_factor(games_df):
    """
    Adds park_run_factor: expanding average of TOTAL runs in games at
    this home park, divided by the league's expanding average — both
    shifted so the current game is excluded. >1 run-friendly park,
    <1 pitcher's park, 1.0 until enough history exists.
    """
    games_df = games_df.sort_values(["date", "game_pk"]).reset_index(drop=True)
    total = games_df["home_score"] + games_df["away_score"]

    park_avg = total.groupby(games_df["home_team"]).transform(
        lambda s: s.expanding().mean().shift(1)
    )
    league_avg = total.expanding().mean().shift(1)

    games_df["park_run_factor"] = (park_avg / league_avg).fillna(1.0)
    return games_df
