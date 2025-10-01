# DOCX → Prompts TXT (Streamlit)

Ứng dụng Streamlit cho phép tải lên file Word (.docx) chứa kịch bản/prompt và xuất ra file .txt chỉ gồm các prompt, phục vụ tool tạo video từ prompt.

## Chạy cục bộ
```bash
python -m venv .venv
. .venv/bin/activate  # hoặc .venv\Scripts\activate trên Windows
pip install -r requirements.txt
streamlit run app.py
