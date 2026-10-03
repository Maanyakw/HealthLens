from load_data import load_dataset


def inspect_dataset():
    df = load_dataset()

    print("\n===== DATASET INFO =====")
    print(f"Shape: {df.shape}")

    print("\n===== DATA TYPES =====")
    print(df.dtypes)

    print("\n===== MISSING VALUES =====")
    print(df.isnull().sum())

    print("\n===== ZERO VALUES =====")
    print((df == 0).sum())

    print("\n===== CLASS DISTRIBUTION =====")
    print(df["Outcome"].value_counts())

    print("\n===== CLASS DISTRIBUTION (%) =====")
    print(df["Outcome"].value_counts(normalize=True) * 100)

    print("\n===== SUMMARY STATISTICS =====")
    print(df.describe())


if __name__ == "__main__":
    inspect_dataset()