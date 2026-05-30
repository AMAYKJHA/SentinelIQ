# import numpy as np
# import pandas as pd
# from pandas.api import types as ptypes


# def _coerce_attack_flag(series: pd.Series) -> pd.Series:
#     if ptypes.is_bool_dtype(series):
#         return series.fillna(False)
#     if ptypes.is_numeric_dtype(series):
#         return series.fillna(0) != 0

#     normalized = series.astype(str).str.strip().str.lower()
#     return normalized.isin(["1", "true", "yes", "y", "t", "attack"])


# def normalize_attack_column(series: pd.Series) -> pd.Series:
#     """
#     Normalize attack indicators into binary 0/1.
#     Handles: 1/0, True/False, Yes/No, Attack/Normal, etc.
#     """

#     return _coerce_attack_flag(series).astype(int)


# def sample_users_preserve_attacks(
#     df: pd.DataFrame,
#     user_col: str,
#     attack_col: str,
#     time_col: str,
#     target_rows: int,
#     random_state: int = 42
# ) -> pd.DataFrame:

#     rng = np.random.default_rng(random_state)

#     df = df.copy()

#     # Remove missing users
#     df = df.dropna(subset=[user_col])

#     # Standardize user IDs
#     df[user_col] = df[user_col].astype(str)

#     # Parse timestamps
#     df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

#     # Remove invalid timestamps
#     df = df.dropna(subset=[time_col])

#     # Normalize attack column
#     attack_mask = _coerce_attack_flag(df[attack_col])
#     df["_attack_flag"] = attack_mask

#     # Users who ever appear in attack rows
#     attack_users = df.loc[attack_mask, user_col].dropna().unique().tolist()

#     # Keep all attack users
#     attack_df = df[df[user_col].isin(attack_users)].copy()

#     if len(attack_df) >= target_rows:
#         sampled_attack_users = rng.choice(
#             attack_users,
#             size=max(1, len(attack_users) // 2),
#             replace=False
#         )
#         sampled = df[df[user_col].isin(sampled_attack_users)].copy()
#         return sampled.sort_values([user_col, time_col]).reset_index(drop=True)

#     remaining = target_rows - len(attack_df)

#     # Normal users pool
#     normal_users = df.loc[~df[user_col].isin(attack_users), user_col].dropna().unique()

#     # Estimate rows per user to sample enough users
#     rows_per_user = df.groupby(user_col).size()
#     median_rows_per_user = rows_per_user.median()

#     users_needed = int(np.ceil(remaining / max(median_rows_per_user, 1)))
#     users_needed = min(users_needed, len(normal_users))

#     sampled_normal_users = rng.choice(normal_users, size=users_needed, replace=False)
#     normal_df = df[df[user_col].isin(sampled_normal_users)].copy()

#     out = pd.concat([attack_df, normal_df], ignore_index=True)
#     return out.sort_values([user_col, time_col]).reset_index(drop=True)

import numpy as np
import pandas as pd
from pandas.api import types as ptypes


def _coerce_attack_flag(series: pd.Series) -> pd.Series:

    if ptypes.is_bool_dtype(series):
        return series.fillna(False)

    if ptypes.is_numeric_dtype(series):
        return series.fillna(0) != 0

    normalized = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    return normalized.isin(
        ["1", "true", "yes", "y", "t", "attack"]
    )


def normalize_attack_column(series: pd.Series) -> pd.Series:

    return _coerce_attack_flag(series).astype(int)


def sample_users_preserve_attacks(
    df: pd.DataFrame,
    user_col: str,
    attack_col: str,
    time_col: str,
    target_rows: int,
    max_rows_per_user: int = 50,
    random_state: int = 42
) -> pd.DataFrame:

    required_cols = [user_col, attack_col, time_col]

    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    rng = np.random.default_rng(random_state)

    df = df.copy()

    # ------------------------------------
    # CLEANING
    # ------------------------------------

    df = df.dropna(subset=[user_col])

    df[user_col] = df[user_col].astype(str)

    df[time_col] = pd.to_datetime(
        df[time_col],
        errors="coerce"
    )

    df = df.dropna(subset=[time_col])

    # ------------------------------------
    # ATTACK FLAG NORMALIZATION
    # ------------------------------------

    attack_mask = _coerce_attack_flag(
        df[attack_col]
    )

    df["_attack_flag"] = attack_mask

    # ------------------------------------
    # ATTACK USERS
    # ------------------------------------

    attack_users = (
        df.loc[attack_mask, user_col]
        .dropna()
        .unique()
        .tolist()
    )

    attack_df = df[
        df[user_col].isin(attack_users)
    ].copy()

    # ------------------------------------
    # NORMAL USERS
    # ------------------------------------

    remaining = max(
        target_rows - len(attack_df),
        0
    )

    normal_users = (
        df.loc[
            ~df[user_col].isin(attack_users),
            user_col
        ]
        .dropna()
        .unique()
    )

    rows_per_user = df.groupby(user_col).size()

    median_rows_per_user = rows_per_user.median()

    users_needed = int(
        np.ceil(
            remaining / max(median_rows_per_user, 1)
        )
    )

    users_needed = min(
        users_needed,
        len(normal_users)
    )

    sampled_normal_users = rng.choice(
        normal_users,
        size=users_needed,
        replace=False
    )

    normal_df = df[
        df[user_col].isin(sampled_normal_users)
    ].copy()

    # ------------------------------------
    # COMBINE
    # ------------------------------------

    out = pd.concat(
        [attack_df, normal_df],
        ignore_index=True
    )

    # ------------------------------------
    # LIMIT POWER USERS
    # ------------------------------------

    out = (
        out
        .sort_values([user_col, time_col])
        .groupby(user_col)
        .head(max_rows_per_user)
    )

    # ------------------------------------
    # FINAL SORT
    # ------------------------------------

    out = (
        out
        .sort_values(time_col)
        .reset_index(drop=True)
    )

    # Prevent leakage
    out = out.drop(columns=["_attack_flag"])

    return out
