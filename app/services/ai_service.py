import json
import uuid
import numpy as np
import pandas as pd
import google.generativeai as genai
from app.core.config import GEMINI_MODEL, _MAX_HISTORY_TURNS
from app.core.state import state
from app.services.visualization_service import pretty_label


def build_ai_context(page: str) -> dict:
    df = state.get_current_df()
    active_cols = state.get_active_columns()
    context = {
        "page": page,
        "dataset_loaded": df is not None,
        "dataset": None,
    }
    if df is not None:
        try:
            sub = df[active_cols]
            dtypes = {str(c): str(sub[c].dtype) for c in active_cols}
            missing = {str(c): int(sub[c].isna().sum()) for c in active_cols if sub[c].isna().sum() > 0}

            preview_serializable = []
            for _, r in sub.head(3).iterrows():
                row_vals = []
                for c in active_cols:
                    val = r[c]
                    if pd.isna(val) or val is None:
                        row_vals.append(None)
                    elif isinstance(val, (float, np.floating)):
                        row_vals.append(None if (np.isnan(val) or np.isinf(val)) else round(float(val), 4))
                    elif isinstance(val, (int, np.integer)):
                        row_vals.append(int(val))
                    else:
                        row_vals.append(str(val))
                preview_serializable.append(row_vals)

            corr_pairs = []
            numeric = sub.select_dtypes(include=["number"])
            if numeric.shape[1] >= 2 and len(numeric) >= 2:
                corr = numeric.corr()
                for i, c1 in enumerate(corr.columns):
                    for c2 in corr.columns[i + 1:]:
                        v = corr.loc[c1, c2]
                        if pd.notna(v) and not np.isnan(v) and not np.isinf(v):
                            corr_pairs.append((str(c1), str(c2), round(float(v), 3)))
                corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                corr_pairs = corr_pairs[:10]

            context["dataset"] = {
                "filename": state.active_dataset.get("filename", "bilinmiyor"),
                "rows": int(len(df)),
                "columns": [str(c) for c in active_cols],
                "col_count": len(active_cols),
                "dtypes": dtypes,
                "missing_counts": missing,
                "preview_first_3_rows": {
                    "columns": [str(c) for c in active_cols],
                    "rows": preview_serializable
                },
                "top_correlations": corr_pairs,
            }
        except Exception as e:
            print("[AI] Veri bağlamı oluşturulamadı:", e)
            context["dataset"] = {
                "filename": state.active_dataset.get("filename", "bilinmiyor"),
                "rows": int(len(df)),
                "columns": [str(c) for c in active_cols],
                "col_count": len(active_cols),
            }
    return context


def rule_based_reply(question: str, context: dict) -> str:
    q = question.lower()
    ds = context.get("dataset")

    if not context.get("dataset_loaded") or ds is None:
        return ("Henüz bir veri seti yüklenmemiş. 'Yeni Veri Yükle' butonundan bir CSV dosyası "
                "yükleyin; ardından veri kalitesi, görselleştirme ve model analizi sorularınızı yanıtlayabilirim.")

    rows, cols = ds["rows"], ds["col_count"]

    if "kalite" in q or "özet" in q or "quality" in q:
        return (f"Şu an '{ds['filename']}' veri seti yüklü ({rows} satır, {cols} sütun). "
                "Veri kalitesi detayları için Data Quality sayfasını inceleyebilirsiniz; "
                "kalite skoru ve eksik veri oranları orada listelenir.")
    if "değişken" in q or "önemli" in q or "sütun" in q or "variable" in q:
        col_sample = ', '.join(ds['columns'][:12])
        return (f"Veri setinde şu sütunlar var: {col_sample}"
                + (" ..." if cols > 12 else "")
                + ". En önemli değişkenleri belirlemek için Visualization sayfasındaki korelasyon "
                  "matrisi ve model metriklerine bakabilirsiniz.")
    if "aykırı" in q or "outlier" in q:
        return "Aykırı değer analizi için Data Quality sayfasındaki 'Aykırı Değer Analizi (IQR)' bölümüne ve Visualization'daki kutu grafiklerine bakabilirsiniz."
    if "model" in q or "başarı" in q or "f1" in q or "accuracy" in q:
        return ("Model sonuçları için Portfolio sayfasındaki 'Model Sonuçları (AI4I 2020)' tablosuna "
                "bakabilirsiniz. En iyi performans Random Forest modelinde görülmektedir.")
    if "sayfa" in q or "nerede" in q:
        return f"Şu an '{context.get('page')}' sayfasındasınız. Veri kalitesi için Data Quality, ön işleme için Preprocessing, grafikler için Visualization sekmelerini kullanabilirsiniz."
    return (f"Bu soruya veri bağlamından kural tabanlı yanıt verebildim: şu an '{ds['filename']}' "
            f"yüklü ({rows} satır, {cols} sütun). Daha akıllı yanıtlar için Ayarlar sayfasından Gemini API anahtarı girebilirsiniz.")


def chat_with_ai(payload: dict) -> dict:
    question = (payload.get("message") or "").strip()
    page = (payload.get("page") or "index.html").strip()
    session_id = (payload.get("session_id") or "").strip() or uuid.uuid4().hex

    if not question:
        return {"error": "Soru boş olamaz.", "status_code": 400}

    context = build_ai_context(page)
    request_api_key = (payload.get("api_key") or "").strip()
    api_key = request_api_key or state.user_gemini_api_key

    if not api_key:
        fallback_reply = rule_based_reply(question, context)
        fallback_history = state.ai_sessions.get(session_id, [])
        fallback_history.append({"role": "user", "content": question})
        fallback_history.append({"role": "assistant", "content": fallback_reply})
        state.ai_sessions[session_id] = fallback_history[-_MAX_HISTORY_TURNS * 2:]
        return {
            "reply": fallback_reply,
            "source": "fallback",
            "context": context,
            "session_id": session_id,
        }

    system_prompt = (
        "Sen trex DataLab platformunun kıdemli Veri Bilimi ve İstatistik uzmanı yapay zeka asistanısın. "
        "Kullanıcının soracağı genel istatistik, makine öğrenmesi, kodlama veya günlük her türlü soruya "
        "Türkçe, son derece akıllı, eğitici, samimi ve detaylı yanıtlar verirsin.\n\n"
        "Aşağıda kullanıcının şu an yüklediği veri setinin özeti ve aktif sayfa bilgisi var. "
        "Veriyle ilgili sorularda bu bağlamı doğrudan kullan (sütun adlarına göre cevap ver, örneğin "
        "'Regionname ne anlama gelir?' gibi sorularda gerçek sütun değerlerine atıfta bulun). "
        "Veri dışı veya genel bir soru sorulduğunda kendi geniş bilgi dağarcığınla eksiksiz yanıtla. "
        "Veri seti yüklü değilse, kullanıcıya önce 'Yeni Veri Yükle' ile CSV yüklemesi gerektiğini söyle.\n\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=800,
            ),
        )

        history = state.ai_sessions.get(session_id, [])
        gemini_history = []
        for turn in history[-_MAX_HISTORY_TURNS:]:
            gemini_history.append({
                "role": "user" if turn["role"] == "user" else "model",
                "parts": [turn["content"]],
            })

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(question)
        reply = (response.text or "").strip() or "Yanıt üretilemedi."

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})
        state.ai_sessions[session_id] = history[-_MAX_HISTORY_TURNS * 2:]

        return {
            "reply": reply,
            "source": "gemini",
            "context": context,
            "session_id": session_id,
        }
    except Exception as e:
        error_msg = f"Gemini API hatası: {str(e)}"
        print("[AI]", error_msg)
        return {
            "reply": error_msg,
            "source": "error",
            "context": context,
            "session_id": session_id,
        }


def reset_ai_session(session_id: str) -> bool:
    if session_id and session_id in state.ai_sessions:
        state.ai_sessions.pop(session_id, None)
    return True
