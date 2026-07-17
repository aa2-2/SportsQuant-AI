def analyze_standings(df):
    print("\n========== MLB ANALYSIS ==========\n")

    print("Top 5 Teams by Win %")
    print(df.sort_values("Win %", ascending=False)[["Team", "Win %"]].head())

    print("\nTop 5 Offenses")
    print(df.sort_values("Runs Scored", ascending=False)[["Team", "Runs Scored"]].head())

    print("\nTop 5 Defenses")
    print(df.sort_values("Runs Allowed")[["Team", "Runs Allowed"]].head())

    print("\nBest Run Differential")
    print(
        df.sort_values(
            "Run Differential",
            ascending=False
        )[["Team", "Run Differential"]].head()
    )