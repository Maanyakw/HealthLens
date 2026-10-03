import pandas as pd
from sklearn.impute import SimpleImputer

from load_data import load_dataset


# Columns where 0 represents a missing/implausible measurement
ZERO_AS_MISSING = [
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
]


def clean_data(df):
    """
    Replace physiologically implausible zero values with NaN
    and impute them using the median.
    """

    df = df.copy()

    # Replace invalid zeros with NaN
    df[ZERO_AS_MISSING] = df[ZERO_AS_MISSING].replace(0, float("nan"))

    # Median imputation
    imputer = SimpleImputer(strategy="median")

    df[ZERO_AS_MISSING] = imputer.fit_transform(
        df[ZERO_AS_MISSING]
    )

    return df


if __name__ == "__main__":
    df = load_dataset()

    print("Before preprocessing:")
    print((df[ZERO_AS_MISSING] == 0).sum())

    cleaned_df = clean_data(df)

    print("\nAfter preprocessing:")
    print(cleaned_df[ZERO_AS_MISSING].isna().sum())

    print("\nCleaned dataset shape:")
    print(cleaned_df.shape)