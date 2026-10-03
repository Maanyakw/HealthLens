import pandas as pd
from pathlib import Path


# Dataset columns
COLUMNS = [
    "Pregnancies",
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
    "DiabetesPedigreeFunction",
    "Age",
    "Outcome",
]


def load_dataset():
    """Load the raw Pima Indians Diabetes dataset."""

    project_root = Path(__file__).resolve().parents[2]
    file_path = project_root / "ml" / "data" / "pima-indians-diabetes.csv"

    df = pd.read_csv(
        file_path,
        header=None,
        names=COLUMNS
    )

    return df


if __name__ == "__main__":
    df = load_dataset()

    print("Dataset loaded successfully!")
    print(f"Shape: {df.shape}")
    print("\nColumns:")
    print(df.columns.tolist())
    print("\nFirst 5 rows:")
    print(df.head())