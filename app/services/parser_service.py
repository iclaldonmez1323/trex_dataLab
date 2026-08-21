import io
import re
import csv
import warnings
import pandas as pd
from typing import Tuple, Optional
from app.core.config import ENCODINGS, DELIMITERS
from app.core.state import make_report, short_exc


def parse_csv_content(content_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, dict]:
    last_error: Optional[Exception] = None
    diagnostics: list = []

    # UTF-16 BOM detection
    if content_bytes.startswith(b"\xff\xfe") or content_bytes.startswith(b"\xfe\xff"):
        enc_list = ["utf-16", "utf-16-le", "utf-16-be"] + [e for e in ENCODINGS if not e.startswith("utf-16")]
    else:
        enc_list = ENCODINGS

    def _looks_merged(df: pd.DataFrame) -> bool:
        if len(df.columns) != 1:
            return False
        col_name = str(df.columns[0])
        if "," in col_name or ";" in col_name or "\t" in col_name or "|" in col_name:
            return True
        if len(df) == 0:
            return False
        sample_vals = df.iloc[:, 0].astype(str).head(20)
        for v in sample_vals:
            if "," in v or ";" in v or "\t" in v or "|" in v:
                return True
        return False

    def _read(enc: str, sep):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            df = pd.read_csv(
                io.BytesIO(content_bytes),
                encoding=enc,
                sep=sep,
                engine="python",
                on_bad_lines="warn",
            )
        skipped_lines = []
        for w in caught:
            if isinstance(w.message, pd.errors.ParserWarning):
                m = re.search(r"line (\d+)", str(w.message))
                if m:
                    skipped_lines.append(int(m.group(1)))

        seen = {}
        new_cols = []
        for c in df.columns:
            c_str = str(c).strip() if c is not None else ""
            if not c_str:
                c_str = "unnamed"
            if c_str in seen:
                seen[c_str] += 1
                new_cols.append(f"{c_str}_{seen[c_str]}")
            else:
                seen[c_str] = 0
                new_cols.append(c_str)
        df.columns = new_cols

        return df, sorted(set(skipped_lines))

    # Phase 1: Auto-detection with Sniffer
    for enc in enc_list:
        try:
            detected_sep = None
            sample_text = content_bytes[:8192].decode(enc, errors="ignore")
            try:
                detected_sep = csv.Sniffer().sniff(sample_text, delimiters="".join(DELIMITERS)).delimiter
            except Exception:
                pass

            if detected_sep is not None:
                df, skipped = _read(enc, detected_sep)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, make_report(enc, detected_sep, len(skipped))
            elif any(d in sample_text for d in DELIMITERS):
                df, skipped = _read(enc, None)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, make_report(enc, None, len(skipped))
        except Exception as e:
            last_error = e
            diagnostics.append(f"kodlama={enc}, ayraç=auto → {short_exc(e)}")
            continue

    # Phase 2: Explicit delimiters
    for enc in enc_list:
        for sep in DELIMITERS:
            try:
                df, skipped = _read(enc, sep)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, make_report(enc, sep, len(skipped))
            except Exception as e:
                last_error = e
                diagnostics.append(f"kodlama={enc}, ayraç={sep} → {short_exc(e)}")
                continue

    # Phase 3: Single-column fallback
    for enc in enc_list:
        for sep_cand in [",", None]:
            try:
                df, skipped = _read(enc, sep_cand)
                if len(df.columns) == 1 and not _looks_merged(df) and len(df) > 0:
                    return df, make_report(enc, None, len(skipped))
            except Exception as e:
                last_error = e
                continue

    detail = (
        "Dosya okunamadı. Denenen kodlamalar: "
        + ", ".join(enc_list)
        + " | Denenen ayraçlar: "
        + ", ".join([("\\t" if d == "\t" else d) for d in DELIMITERS])
    )
    if last_error is not None:
        detail += " | Son hata: " + short_exc(last_error)
    if diagnostics:
        detail += " | Ayrıntı: " + " ; ".join(diagnostics[-5:])
    raise ValueError(detail)
