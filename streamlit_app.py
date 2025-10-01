import io
import zipfile
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List
import streamlit as st


st.set_page_config(page_title="DOCX → Prompts .TXT", page_icon="📝", layout="centered")


# -------- Core: DOCX parsing (no external deps) --------
def extract_paragraphs_from_docx_bytes(file_bytes: bytes) -> List[str]:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        xml_content = z.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ET.fromstring(xml_content)
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        texts = []
        for t in p.findall(".//w:t", ns):
            texts.append(t.text or "")
        para_text = "".join(texts)
        # normalize whitespace
        para_text = re.sub(r"\s+", " ", para_text).strip()
        if para_text:
            paragraphs.append(para_text)
    return paragraphs


# -------- Heuristic filter for "prompt-like" paragraphs --------
def looks_like_prompt(
    text: str,
    min_len: int,
    min_ascii_ratio: float,
    keywords: List[str],
    min_keyword_hits: int,
    max_puncts: int,
) -> bool:
    if len(text) < min_len:
        return False

    ascii_ratio = (sum(1 for ch in text if ord(ch) < 128) / max(1, len(text)))
    kcount = sum(1 for k in keywords if k and k.lower().strip() in text.lower())

    # Punctuation count as a proxy for long, single-block prompt vs. many short sentences
    puncts = len(re.findall(r"[.!?]", text))

    return ascii_ratio >= min_ascii_ratio and kcount >= min_keyword_hits and puncts <= max_puncts


def filter_prompts(
    paragraphs: List[str],
    min_len: int = 400,
    min_ascii_ratio: float = 0.75,
    keywords: List[str] = None,
    min_keyword_hits: int = 3,
    max_puncts: int = 40,
    relax_if_empty: bool = True,
) -> List[str]:
    if keywords is None:
        keywords = [
            "objective", "environment", "characters", "props", "dialogue",
            "teamwork", "camera", "lighting", "VFX", "Audio", "Rhythm",
            "Transition", "Interactive CTA"
        ]
    prompts = [
        p for p in paragraphs
        if looks_like_prompt(p, min_len, min_ascii_ratio, keywords, min_keyword_hits, max_puncts)
    ]

    if relax_if_empty and len(prompts) == 0:
        # fallback nhẹ nếu quá khắt khe
        prompts = [
            p for p in paragraphs
            if len(p) >= max(300, int(min_len * 0.75))
            and (sum(1 for ch in p if ord(ch) < 128) / max(1, len(p))) >= min(min_ascii_ratio, 0.7)
        ]
    return prompts


def to_download_filename(orig_name: str) -> str:
    base = orig_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = re.sub(r"\.docx$", "", base, flags=re.IGNORECASE)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base or 'prompts'}_{ts}.txt"


# -------- UI --------
st.title("DOCX → TXT (Prompts Only)")
st.caption("Tải lên file Word (.docx) chứa kịch bản + prompt. Ứng dụng sẽ lọc và trả về file .txt chỉ chứa các prompt.")

uploaded = st.file_uploader("Chọn file .docx", type=["docx"])

with st.expander("Tùy chọn lọc nâng cao", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        min_len = st.number_input("Độ dài tối thiểu của đoạn (ký tự)", min_value=100, max_value=5000, value=400, step=50)
        min_ascii_ratio = st.slider("Ngưỡng tỷ lệ ASCII (0–1)", min_value=0.0, max_value=1.0, value=0.75, step=0.05)
    with col2:
        min_keyword_hits = st.number_input("Số từ khóa khớp tối thiểu", min_value=0, max_value=10, value=3, step=1)
        max_puncts = st.number_input("Giới hạn số dấu câu (.!?)", min_value=1, max_value=200, value=40, step=1)
    default_keywords = "objective, environment, characters, props, dialogue, teamwork, camera, lighting, VFX, Audio, Rhythm, Transition, Interactive CTA"
    keywords_str = st.text_area("Từ khóa (phân tách bằng dấu phẩy)", value=default_keywords)
    relax_if_empty = st.checkbox("Nới lỏng nếu không tìm thấy prompt nào", value=True)

process_btn = st.button("Xử lý & Xuất TXT", use_container_width=True, type="primary")

if process_btn:
    if not uploaded:
        st.error("Vui lòng chọn file .docx trước.")
    else:
        try:
            paragraphs = extract_paragraphs_from_docx_bytes(uploaded.read())
            kw_list = [k.strip() for k in keywords_str.split(",") if k.strip()]
            prompts = filter_prompts(
                paragraphs,
                min_len=min_len,
                min_ascii_ratio=min_ascii_ratio,
                keywords=kw_list,
                min_keyword_hits=min_keyword_hits,
                max_puncts=max_puncts
