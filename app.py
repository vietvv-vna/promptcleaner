import io
import re
from typing import List

import streamlit as st
from docx import Document

# langdetect là tùy chọn
try:
    from langdetect import detect
    LANGDETECT_AVAILABLE = True
except Exception:
    LANGDETECT_AVAILABLE = False

st.set_page_config(page_title="DOCX → English Prompts TXT", layout="wide")

# ----------------- Tiện ích -----------------
EN_STOPWORDS_SAMPLE = {
    "the","and","to","of","a","in","is","that","for","on","with","as","by","from",
    "this","be","are","at","or","it","an","into","over","under","about","into","can",
    "scene","character","dialogue","objective","environment","camera","lighting","transition","audio","vfx"
}

VN_DIACRITIC_REGEX = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    r"ùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄ"
    r"ÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
)

DEFAULT_KEYWORDS = [
    "objective","environment","characters","props","dialogue",
    "teamwork","camera","lighting","vfx","audio","rhythm","transition","cta"
]

def ascii_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(1 for ch in s if ord(ch) < 128) / len(s)

def normalize_ws(s: str) -> str:
    return " ".join((s or "").split()).strip()

def is_english_heuristic(text: str) -> bool:
    # 1) Không có dấu tiếng Việt
    if VN_DIACRITIC_REGEX.search(text):
        return False
    # 2) Tỷ lệ ASCII cao
    if ascii_ratio(text) < 0.85:
        return False
    # 3) Chứa nhiều từ chức năng/từ khóa tiếng Anh
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in EN_STOPWORDS_SAMPLE)
    return hits >= 8  # ngưỡng tương đối chặt

def is_english_langdetect(text: str) -> bool:
    if not LANGDETECT_AVAILABLE:
        return False
    try:
        return detect(text) == "en"
    except Exception:
        return False

def is_english(text: str, strict: bool) -> bool:
    if strict and LANGDETECT_AVAILABLE:
        return is_english_langdetect(text)
    # fallback: heuristic nhanh
    return is_english_heuristic(text)

def extract_paragraphs_from_docx(file_bytes: bytes) -> List[str]:
    doc = Document(io.BytesIO(file_bytes))
    paras = []
    for p in doc.paragraphs:
        t = normalize_ws(p.text)
        if t:
            paras.append(t)
    return paras

def looks_like_prompt(text: str, min_len: int, require_english: bool, strict_lang: bool, keywords: List[str], min_keyword_hits: int) -> bool:
    # Điều kiện độ dài tối thiểu
    if len(text) < min_len:
        return False
    # Chỉ giữ tiếng Anh
    if require_english and not is_english(text, strict_lang):
        return False
    # (tùy chọn) yêu cầu khớp một số keyword cấu trúc prompt
    if min_keyword_hits > 0 and keywords:
        hits = sum(1 for k in keywords if k and k.lower() in text.lower())
        if hits < min_keyword_hits:
            return False
    return True

def filter_prompts(paragraphs: List[str], min_len: int, require_english: bool, strict_lang: bool, keywords: List[str], min_keyword_hits: int) -> List[str]:
    prompts = [
        p for p in paragraphs
        if looks_like_prompt(p, min_len, require_english, strict_lang, keywords, min_keyword_hits)
    ]
    # Không có fallback nới lỏng độ dài: yêu cầu người dùng > = 1000 ký tự
    return prompts

# ----------------- UI -----------------
st.title("DOCX → English Prompts TXT")
st.caption("Tải .docx, lọc **chỉ các prompt tiếng Anh** và **bỏ đoạn < 1000 ký tự**.")

with st.sidebar:
    st.header("Thiết lập lọc")
    min_len = st.slider("Độ dài tối thiểu (ký tự)", min_value=1000, max_value=4000, value=1000, step=100)
    require_english = st.checkbox("Chỉ giữ prompt tiếng Anh", value=True)
    strict_lang = st.checkbox("Dò tiếng Anh nghiêm ngặt (langdetect)", value=False,
                              help="Cần gói langdetect. Nếu chưa cài, app tự dùng heuristic nhanh.")
    min_hits = st.slider("Số keyword cấu trúc tối thiểu", 0, 10, 2, 1)
    kw_input = st.text_area("Keywords (phân tách dấu phẩy)", value=", ".join(DEFAULT_KEYWORDS), height=90)
    user_keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    st.markdown("---")
    if require_english and strict_lang and not LANGDETECT_AVAILABLE:
        st.warning("langdetect chưa sẵn có. Vui lòng cài trong requirements hoặc tắt chế độ nghiêm ngặt.")

uploaded = st.file_uploader("Chọn file .docx", type=["docx"])

if uploaded is not None:
    try:
        file_bytes = uploaded.read()
        paragraphs = extract_paragraphs_from_docx(file_bytes)
        st.success(f"Đọc được {len(paragraphs)} đoạn.")

        prompts = filter_prompts(
            paragraphs=paragraphs,
            min_len=min_len,
            require_english=require_english,
            strict_lang=strict_lang,
            keywords=user_keywords,
            min_keyword_hits=min_hits
        )

        st.subheader(f"Kết quả: {len(prompts)} prompt (English-only, ≥ {min_len} ký tự)")
        if len(prompts) == 0:
            st.warning("Không có prompt nào thỏa điều kiện. Hãy kiểm tra lại đầu vào hoặc nới tiêu chí keyword.")
        else:
            # Xem nhanh
            with st.expander("Xem nhanh 3 prompt đầu"):
                for i, pr in enumerate(prompts[:3], 1):
                    st.markdown(f"**Prompt #{i}**")
                    st.write(pr)

            txt_content = "\n\n".join(p.strip() for p in prompts)
            base = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{base}_EN_prompts_min{min_len}.txt"
            st.download_button("Tải TXT", data=txt_content.encode("utf-8"), file_name=out_name, mime="text/plain")

    except Exception as e:
        st.error(f"Lỗi xử lý: {e}")
else:
    st.info("Hãy tải lên một file .docx để bắt đầu.")
