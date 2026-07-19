import pandas as pd
import os

print("Current working directory:", os.getcwd())
print("Files in data directory:")
print(os.listdir("data"))

# Try to read just the 2024 file
print("\nTrying to read statcast_2024.csv...")
try:
    df = pd.read_csv("data/statcast_2024.csv")
    print(f"Success! Shape: {df.shape}")
    print("Columns:", list(df.columns))
except Exception as e:
    print(f"Error: {e}")