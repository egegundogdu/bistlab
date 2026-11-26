"""Modüller arasında paylaşılan küçük yardımcılar."""

from __future__ import annotations

import numpy as np
import pandas as pd


def column(df: pd.DataFrame, name: str) -> pd.Series[float]:
    """Kalem varsa sütununu, yoksa NaN dolu bir seri döner."""
    if name in df.columns:
        return df[name].astype(float)
    return pd.Series(np.nan, index=df.index, dtype=float)
