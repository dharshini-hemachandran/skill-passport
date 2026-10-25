import pandas as pd
import os

files = os.listdir("data")

print("Files inside data folder:")
for file in files:
    print(file)

csv_files = [f for f in files if f.endswith(".csv")]

if not csv_files:
    print("No CSV file found.")
else:
    file_path = os.path.join("data", csv_files[0])

    df = pd.read_csv(file_path)

    print("\nShape:")
    print(df.shape)

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nFirst 5 rows:")
    print(df.head())