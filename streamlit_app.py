import streamlit as st
import os
import requests
import pdfminer.high_level
import docx2txt
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import io
from docx import Document
from docx.shared import Pt

# --- Page Config ---
st.set_page_config(page_title="AI Doc Genie (Force OCR)", page_icon="👁️", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""

# --- Functions ---
def register_fonts():
    if os.path.exists("sinhala.ttf"):
        try:
            pdfmetrics.registerFont(TTFont('Sinhala', 'sinhala.ttf'))
            return True
        except:
            return False
    return False

# --- TEXT EXTRACTION (WITH FORCE OCR) ---
def extract_text_from_files(uploaded_files, force_ocr=False):
    combined_text = ""
    if not uploaded_files:
        return ""
    
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            text_chunk = ""
            
            # 1. PDF Handling
            if ext == 'pdf':
                # IF FORCE OCR IS ON: Skip normal reading, go straight to Image conversion
                if force_ocr:
                    st.toast(f"Force OCR Active: Scanning {file.name} as images...", icon="📸")
                    images = convert_from_bytes(file.read())
                    ocr_text = ""
                    for i, img in enumerate(images):
                        # Image Pre-processing
                        img = ImageOps.grayscale(img)
                        img = ImageEnhance.Contrast(img).enhance(2.0)
                        # Extract Sinhala + English
                        page_text = pytesseract.image_to_string(img, lang='sin+eng', config='--oem 3 --psm 6')
                        ocr_text += f"\n--- Page {i+1} ---\n{page_text}"
                    text_chunk = ocr_text
                
                else:
                    # Normal Mode
                    raw_text = pdfminer.high_level.extract_text(file)
                    if not raw_text or len(raw_text.strip()) < 50:
                        st.warning(f"⚠️ '{file.name}' හි අකුරු පැහැදිලි නැත. කරුණාකර වම් පැත්තේ ඇති 'Force OCR' බොත්තම දමා නැවත උත්සාහ කරන්න.")
                        return ""
                    text_chunk = raw_text

            # 2. Images (Always OCR)
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                img = ImageOps.grayscale(img)
                img = ImageEnhance.Contrast(img).enhance(2.0)
                text_chunk = pytesseract.image_to_string(img, lang='sin+eng', config='--oem 3 --psm 6')
            
            # 3. Docs
            elif ext == 'docx':
                text_chunk = docx2txt.process(file)
            elif ext == 'txt':
                text_chunk = file.read().decode('utf-8')
            
            combined_text += text_chunk + "\n---\n"
            
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            
    return combined_text

# --- MODEL SELECTION ---
def get_working_model(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            available = [m['name'].replace('models/', '') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if available: return available[0]
    except:
        pass
    return "gemini-pro"

# --- API CALL ---
def call_gemini(api_key, model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3} # Low temp for precision
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- EXPORT ---
def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    font_loaded = register_fonts()
    font_name = "Sinhala" if font_loaded else "Helvetica"
    c.setFont(font_name, 11)
    y = 800
    margin = 40
    for paragraph in text.split('\n'):
        clean_line = paragraph.replace("*", "").strip()
        if not clean_line: continue
        words = clean_line.split()
        line = ""
        for word in words:
            if c.stringWidth(line + " " + word, font_name) < 500:
                line += " " + word
            else:
                c.drawString(margin, y, line); y -= 20
                line = word
                if y < 50: c.showPage(); c.setFont(font_name, 11); y = 800
        c.drawString(margin, y, line); y -= 20
        if y < 50: c.showPage(); c.setFont(font_name, 11); y = 800
    c.save()
    buffer.seek(0)
    return buffer

def create_docx(text):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    for line in text.split('\n'):
        if not line.strip(): continue
        p = doc.add_paragraph()
        if line.startswith("#") or "Paper" in line:
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(13)
        else:
            p.add_run(line.strip())
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- UI ---
with st.sidebar:
    st.title("⚙️ Settings")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Active")
    else:
        api_key = st.text_input("Gemini API Key:", type="password")
    
    st.divider()
    app_mode = st.radio("Mode:", ["Exam Paper Generator", "Document Digitizer"])
    
    st.divider()
    # 🔥 THE IMPORTANT SWITCH 🔥
    force_ocr = st.checkbox("Force OCR (සම්පූර්ණ ස්කෑන්)", help="PDF එකේ අකුරු කියවන්නේ නැත්නම් මෙය දාන්න.")
    st.caption("Scanned PDF සඳහා මෙය අනිවාර්යයෙන් දාන්න.")

st.title(f"👁️ AI Doc Genie ({app_mode})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions")
    user_instructions = st.text_area("Instructions:", height=100)
    ref_files = st.file_uploader("Reference Style", accept_multiple_files=True, key="ref")
with col2:
    st.subheader("2️⃣ Source Content")
    source_files = st.file_uploader("Source PDF/Images", accept_multiple_files=True, key="src")

if st.button("Generate", type="primary"):
    if not api_key or not source_files:
        st.error("Missing Data")
    else:
        with st.spinner("Processing..."):
            # Pass the Force OCR setting
            source_text = extract_text_from_files(source_files, force_ocr=force_ocr)
            
            if not source_text.strip():
                st.error("කිසිවක් කියවීමට නොහැක. කරුණාකර 'Force OCR' දමා උත්සාහ කරන්න.")
            else:
                ref_text = extract_text_from_files(ref_files)
                model = get_working_model(api_key)
                prompt = f"""
                Role: Sri Lankan Assistant. Mode: {app_mode}
                Instructions: {user_instructions}
                Source Content (EXTRACTED): {source_text[:20000]}
                Rules: Use Unicode Sinhala. Linear Math.
                """
                res = call_gemini(api_key, model, prompt)
                if res.startswith("Error"): st.error(res)
                else:
                    st.session_state.generated_content = res
                    st.rerun()

if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        st.text_area("Preview", st.session_state.generated_content, height=600)
        b1, b2 = st.columns(2)
        with b1: st.download_button("PDF", create_pdf(st.session_state.generated_content), "doc.pdf", "application/pdf")
        with b2: st.download_button("Word", create_docx(st.session_state.generated_content), "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
