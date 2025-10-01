import io
import os
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

st.set_page_config(page_title="DOCX → English Prompts TXT (Batch)", layout="wide")

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
    # Gom các run, bỏ line break thừa → 1 khoảng trắng
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
    return hits >= 8

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
    return is_english_heuristic(text)

def extract_paragraphs_from_docx(file_bytes: bytes) -> List[str]:
    doc = Document(io.BytesIO(file_bytes))
    paras = []
    for p in doc.paragraphs:
        t = normalize_ws(p.text)
        if t:
            paras.append(t)
    return paras

def looks_like_prompt(
    text: str,
    min_len: int,
    require_english: bool,
    strict_lang: bool,
    keywords: List[str],
    min_keyword_hits: int
) -> bool:
    # 1) Độ dài tối thiểu (≥ 1000 theo yêu cầu)
    if len(text) < min_len:
        return False
    # 2) Chỉ giữ tiếng Anh
    if require_english and not is_english(text, strict_lang):
        return False
    # 3) (tuỳ chọn) phải khớp số lượng keyword
    if min_keyword_hits > 0 and keywords:
        hits = sum(1 for k in keywords if k and k.lower() in text.lower())
        if hits < min_keyword_hits:
            return False
    return True

def filter_prompts(
    paragraphs: List[str],
    min_len: int,
    require_english: bool,
    strict_lang: bool,
    keywords: List[str],
    min_keyword_hits: int
) -> List[str]:
    # Không có fallback nới lỏng: tuân thủ chặt chẽ ≥ min_len và English-only
    return [
        p for p in paragraphs
        if looks_like_prompt(p, min_len, require_english, strict_lang, keywords, min_keyword_hits)
    ]

# ----------------- UI -----------------
st.title("DOCX → English Prompts TXT (Batch)")
st.caption("Tải nhiều file .docx, app sẽ lọc **chỉ các prompt tiếng Anh** và **bỏ đoạn < 1000 ký tự**, xuất .txt trùng tên.")

with st.sidebar:
    st.header("Thiết lập lọc")
    min_len = st.slider("Độ dài tối thiểu (ký tự)", min_value=1000, max_value=4000, value=1000, step=100)
    require_english = st.checkbox("Chỉ giữ prompt tiếng Anh", value=True)
    strict_lang = st.checkbox(
        "Dò tiếng Anh nghiêm ngặt (langdetect)",
        value=False,
        help="Cần gói langdetect. Nếu chưa cài, app dùng heuristic nhanh."
    )
    min_hits = st.slider("Số keyword cấu trúc tối thiểu", 0, 10, 2, 1)
    kw_input = st.text_area("Keywords (phân tách dấu phẩy)", value=", ".join(DEFAULT_KEYWORDS), height=90)
    user_keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    st.markdown("---")
    if require_english and strict_lang and not LANGDETECT_AVAILABLE:
        st.warning("langdetect chưa sẵn có. Vui lòng thêm vào requirements hoặc tắt chế độ nghiêm ngặt.")

uploaded_files = st.file_uploader("Chọn 1 hoặc nhiều file .docx", type=["docx"], accept_multiple_files=True)

if uploaded_files:
    results = []  # danh sách (file_name, prompts_list, txt_bytes)
    total_paras = 0
    total_prompts = 0

    for up in uploaded_files:
        try:
            file_bytes = up.read()
            paragraphs = extract_paragraphs_from_docx(file_bytes)
            total_paras += len(paragraphs)

            prompts = filter_prompts(
                paragraphs=paragraphs,
                min_len=min_len,
                require_english=require_english,
                strict_lang=strict_lang,
                keywords=user_keywords,
                min_keyword_hits=min_hits
            )

            total_prompts += len(prompts)

            # Xóa dòng trắng giữa các prompt: nối bằng '\n' (không có khoảng trống thừa)
            # Mỗi prompt đã normalize_ws → vốn 1 dòng
            # Nếu lo ngại prompt có xuống dòng bên trong, ta vẫn loại bỏ blank-line thừa:
            lines = []
            for p in prompts:
                # loại các dòng trống nội bộ nếu có
                p_no_blank = "\n".join([ln for ln in p.splitlines() if ln.strip() != ""]).strip()
                lines.append(p_no_blank)
            txt_content = "\n".join(lines)  # KHÔNG có dòng trắng ngăn cách

            # Tên file .txt trùng tên .docx
            base, _ = os.path.splitext(up.name)
            out_name = f"{base}.txt"
            results.append((out_name, prompts, txt_content.encode("utf-8")))

        except Exception as e:
            st.error(f"Lỗi xử lý '{up.name}': {e}")

    st.success(f"Đã đọc {total_paras} đoạn, lọc được tổng {total_prompts} prompt từ {len(uploaded_files)} file.")

    # Hiển thị kết quả theo từng file + nút tải
    for out_name, prompts, txt_bytes in results:
        st.subheader(f"{out_name} — {len(prompts)} prompt")
        if len(prompts) == 0:
            st.warning("Không có prompt thỏa điều kiện.")
        else:
            with st.expander("Xem nhanh 3 prompt đầu"):
                for i, pr in enumerate(prompts[:3], 1):
                    st.markdown(f"**Prompt #{i}**")
                    st.write(pr)
        st.download_button(
            label=f"⬇️ Tải {out_name}",
            data=txt_bytes,
            file_name=out_name,
            mime="text/plain",
            key=f"dl-{out_name}"
        )

    # (Tuỳ chọn) Gộp tất cả .txt vào 1 ZIP để tải một lần
    import zipfile
    import io as _io
    if len(results) > 1:
        zip_buf = _io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for out_name, _, txt_bytes in results:
                zf.writestr(out_name, txt_bytes)
        st.download_button(
            label="⬇️ Tải tất cả .txt dưới dạng ZIP",
            data=zip_buf.getvalue(),
            file_name="prompts_batch.zip",
            mime="application/zip",
            key="dl-zip-all"
        )
else:
    st.info("Hãy tải lên một hoặc nhiều file .docx để bắt đầu.")
