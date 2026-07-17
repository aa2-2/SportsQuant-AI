import pandas as pd

def load_standings():
    return pd.read_csv("data/standings.csv")