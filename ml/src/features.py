"""
Feature preparation for HealthLens.

Everything here is written as scikit-learn transformers so it can sit inside a
Pipeline. That matters: inside a Pipeline, the median used for imputation and
the mean/std used for scaling are learned from the TRAINING data only, then
applied unchanged to validation/test data and to new patients arriving through
the API. Doing the same steps on the whole dataset before splitting (as the
EDA notebook does) lets information from the test rows leak into training.

The pickled model refers to these classes by module name (`features`), so any
code that loads the model (predict.py, the FastAPI app, notebooks) must have
`ml/src` on sys.path and be able to `import features`.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

TARGET = "Outcome"

# The 8 inputs a user (or the API) provides, in this exact order.
BASE_FEATURES = [
    "Pregnancies",
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
    "DiabetesPedigreeFunction",
    "Age",
]

# In this dataset a 0 in these columns means "not measured", not a real value.
ZERO_AS_MISSING = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]

ENGINEERED_FEATURES = [
    "BMI_Category",
    "Age_Band",
    "Glucose_Insulin_Ratio",
    "BMI_Age_Interaction",
]

# Same cut points as notebooks/01_eda.ipynb.
BMI_BINS = [0, 18.5, 25, 30, np.inf]  # Underweight, Normal, Overweight, Obese
AGE_BINS = [0, 30, 45, 60, np.inf]  # Young, Adult, Middle_Age, Senior


class ZerosToNaN(BaseEstimator, TransformerMixin):
    """Turn physiologically impossible zeros into NaN so the imputer can fill them."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        cols = [c for c in ZERO_AS_MISSING if c in X.columns]
        X[cols] = X[cols].replace(0, np.nan)
        return X

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Add the four engineered features from the EDA notebook.

    Must run AFTER imputation (it divides by Insulin and multiplies BMI * Age).
    The two categories are encoded as ordered integers (0, 1, 2, 3) instead of
    text so linear models, SVM and MLP can use them directly.

    Set add_features=False to get the plain 8-feature baseline.
    """

    def __init__(self, add_features=True):
        self.add_features = add_features

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        if not self.add_features:
            return X

        X["BMI_Category"] = pd.cut(
            X["BMI"], bins=BMI_BINS, labels=False, include_lowest=True
        ).astype(float)
        X["Age_Band"] = pd.cut(
            X["Age"], bins=AGE_BINS, labels=False, include_lowest=True
        ).astype(float)
        # clip(lower=1) guards against division by zero for odd inputs.
        X["Glucose_Insulin_Ratio"] = X["Glucose"] / X["Insulin"].clip(lower=1.0)
        X["BMI_Age_Interaction"] = X["BMI"] * X["Age"]
        return X

    def get_feature_names_out(self, input_features=None):
        names = list(input_features)
        if self.add_features:
            names += ENGINEERED_FEATURES
        return np.asarray(names, dtype=object)
