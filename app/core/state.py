import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from app.core.config import GEMINI_API_KEY


class StateManager:
    """Central in-memory state manager for the active dataset and session."""

    def __init__(self):
        self.active_dataset: Dict[str, Any] = {}
        self.active_df_cache: Optional[pd.DataFrame] = None
        self.original_df_cache: Optional[pd.DataFrame] = None
        self.processed_df_cache: Optional[pd.DataFrame] = None
        self.dropped_columns: set = set()
        self.preprocessing_history_stack: list = []
        self.user_gemini_api_key: str = GEMINI_API_KEY
        self.ai_sessions: dict = {}

    def reset_all(self):
        """Resets all dataset state and AI sessions."""
        self.active_dataset = {}
        self.active_df_cache = None
        self.original_df_cache = None
        self.processed_df_cache = None
        self.dropped_columns = set()
        self.preprocessing_history_stack = []
        self.ai_sessions = {}

    def get_current_df(self) -> Optional[pd.DataFrame]:
        """Returns the active processed DataFrame, or active_df_cache if processed is None."""
        return self.processed_df_cache if self.processed_df_cache is not None else self.active_df_cache

    def get_active_columns(self) -> list:
        """Returns non-dropped column names from current dataframe."""
        df = self.get_current_df()
        if df is None:
            return []
        return [c for c in df.columns if c not in self.dropped_columns]


# Global singleton instance
state = StateManager()


def clean_val_for_json(val: Any) -> Any:
    """JSON serialization helper for NaN / Inf / numpy values."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if pd.isna(val):
        return None
    return str(val)


def make_report(enc: str, sep: str, skipped: int = 0) -> dict:
    """Returns parse report structure."""
    return {
        "encoding_used": enc,
        "delimiter_used": sep,
        "skipped_rows": skipped
    }


def short_exc(exc: Exception) -> str:
    """Returns a short single-line exception description."""
    return f"{type(exc).__name__}: {str(exc)[:120]}"
