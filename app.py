import io
import re
import unicodedata
from typing import List

import streamlit as st
from docx import Document

st.set_page_config(page_title="DOCX → Prompts TXT", page_icon="📝", layout="wide")

# ---------- Heuristics ----------
DEFAULT_KEYWORDS = [
    "objective", "environment", "characters", "props", "dialogue",
    "teamwork", "camera", "lighting", "vfx", "audio", "rhythm",
    "transition", "cta"
]

def ascii_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(1 for ch in s if ord(ch) < 128) / len(s)

def normalize_ws(s: str) -> str:
    # Ghép các run trong Word, loại bỏ xuống dòng thừa
    s = " ".join(s.split())
    return s.strip()

def looks_like_prompt(
    text: str,
    min_len: int,
    min_ascii_ratio: float,
    min_keyword_hits: int,
    user_keywords: List[str]
) -> bool:
    if len(text) < min_len:
        return False

    # Tỷ lệ ASCII (nhiều prompt tiếng Anh dài)
    if ascii_ratio(text) < min_ascii_ratio:
        return False

    # Đếm keyword
    keys = [k.strip().lower() for k in user_keywords if k.strip()]
    hits = sum(1 for k in keys if k in text.lower())
    if hits < min_keyword_hits:
        return False

    # Prompt thường là 1 block dài, ít dấu câu tương ứng số câu hạn chế
    # (nhưng vẫn linh hoạt để không bỏ sót)
    # Có thể tùy biến nếu cần:
    return True

def extract_paragraphs_from_docx(file_bytes: bytes) -> List[str]:
    doc = Document(io.BytesIO(file_bytes))
    paras = []
    for p in doc.paragraphs:
        t = normalize_ws(p.text or "")
        if t:
            paras.append(t)
    return paras

def filter_prompts(
    paragraphs: List[str],
    min_len: int,
    min_ascii_ratio: float,
    min_keyword_hits: int,
    user_keywords: List[str]
) -> List[str]:
    prompts = [
        p for p in paragraphs
        if looks_like_prompt(p, min_len, min_ascii_ratio, min_keyword_hits, user_keywords)
    ]
    # Fallback nhẹ nếu không bắt được gì
    if len(prompts) == 0:
        prompts = [
            p for p in paragraphs
            if len(p) >= max(600, min_len) and ascii_ratio(p) >= max(0.7, min_ascii_ratio - 0.1)
        ]
    return prompts

# ---------- UI ----------
st.title("📝 DOCX → Prompts TXT")
st.caption("Tải file Word (.docx) có kịch bản/prompt, app sẽ lọc và xuất TXT chỉ chứa các prompt.")

with st.sidebar:
    st.header("Bộ lọc (tùy chỉnh)")
    min_len = st.slider("Độ dài tối thiểu của 1 prompt (ký tự)", 100, 3000, 500, 50)
    min_ascii = st.slider("Tỷ lệ ASCII tối thiểu", 0.0, 1.0, 0.75, 0.01)
    min_hits = st.slider("Số lượng keyword tối thiểu khớp", 0, 10, 2, 1)
    kw_input = st.text_area(
        "Keywords (phân tách bằng dấu phẩy)",
        value=", ".join(DEFAULT_KEYWORDS),
        height=100
    )
    user_keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    st.markdown("---")
    st.caption("Gợi ý: Nếu prompt của bạn luôn có các lớp như 'objective, environment, camera, lighting, VFX, transition, CTA…', hãy giữ từ khóa này để lọc chính xác.")

uploaded = st.file_uploader("Chọn file .docx", type=["docx"])

if uploaded is not None:
    try:
        paragraphs = extract_paragraphs_from_docx(uploaded.read())
        st.success(f"Đã đọc {len(paragraphs)} đoạn văn từ tài liệu.")
        prompts = filter_prompts(paragraphs, min_len, min_ascii, min_hits, user_keywords)

        st.subheader(f"Kết quả: {len(prompts)} prompt")
        if len(prompts) == 0:
            st.warning("Không phát hiện prompt theo tiêu chí hiện tại. Vui lòng nới tiêu chí lọc trong sidebar.")
        else:
            # Xem nhanh 3 prompt đầu
            with st.expander("Xem nhanh (tối đa 3 prompt đầu)"):
                for i, pr in enumerate(prompts[:3], 1):
                    st.markdown(f"**Prompt #{i}**")
                    st.write(pr)

            # Xuất TXT
            sep = "\n\n"
            txt_content = sep.join(p.strip() for p in prompts)
            file_name_stem = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{file_name_stem}_prompts_only.txt"
            st.download_button(
                label="⬇️ Tải TXT chứa prompts",
                data=txt_content.encode("utf-8"),
                file_name=out_name,
                mime="text/plain"
            )

            # Tuỳ chọn dọn nhiễu (optional)
            st.markdown("---")
            st.subheader("Tùy chọn làm sạch thêm (Optional)")
            rm_numbers = st.checkbox("Loại bỏ số heading/prefix dạng 'Scene 01:', 'Video 12 – ' ở đầu dòng")
            rm_quotes = st.checkbox("Loại bỏ ngoặc kép đầu/cuối toàn prompt")
            if st.button("Áp dụng làm sạch & tạo lại TXT"):
                cleaned = []
                for pr in prompts:
                    s = pr
                    if rm_numbers:
                        s = re.sub(r"^\s*(scene|video)\s*[:\-#]?\s*\d+\s*[\-\–:]\s*", "", s, flags=re.I)
                    if rm_quotes:
                        s = s.strip()
                        s = re.sub(r'^["“”]+', '', s)
                        s = re.sub(r'["“”]+$', '', s)
                    cleaned.append(s.strip())
                txt_content2 = "\n\n".join(cleaned)
                st.download_button(
                    label="⬇️ Tải TXT đã làm sạch",
                    data=txt_content2.encode("utf-8"),
                    file_name=f"{file_name_stem}_prompts_only_clean.txt",
                    mime="text/plain",
                    key="clean_download"
                )

    except Exception as e:
        st.error(f"Lỗi xử lý: {e}")
else:
    st.info("Hãy tải lên một file .docx để bắt đầu.")
