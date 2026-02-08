import streamlit as st
import os
import requests
import json
import pdfminer.high_level
import docx2txt
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import io
from docx import Document
from docx.shared import Pt

# --- Page Config ---
st.set_page_config(page_title="AI Doc Genie Pro", page_icon="🧞‍♂️", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_model" not in st.session_state:
    st.session_state.current_model = "gemini-pro"

# --- Functions ---
def register_fonts():
    if os.path.exists("sinhala.ttf"):
        try:
            pdfmetrics.registerFont(TTFont('Sinhala', 'sinhala.ttf'))
            return True
        except:
            return False
    return False

def extract_text_from_files(uploaded_files):
    combined_text = ""
    if not uploaded_files:
        return ""
    
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            text_chunk = ""
            
            # 1. PDF Handling
            if ext == 'pdf':
                text_chunk = pdfminer.high_level.extract_text(file)
                # Check if PDF is scanned (empty text)
                if not text_chunk or len(text_chunk.strip()) < 50:
                    st.warning(f"⚠️ අවවාදයයි: '{file.name}' ගොනුව කියවීමට නොහැක (Scanned PDF). කරුණාකර එය පින්තූර (Images/Screenshots) ලෙස ඇතුළත් කරන්න.")
                    return "" # Stop to prevent hallucinations
            
            # 2. Docx/Txt Handling
            elif ext == 'docx':
                text_chunk = docx2txt.process(file)
            elif ext == 'txt':
                text_chunk = file.read().decode('utf-8')
            
            # 3. Image Handling (BEST FOR GEOMETRY/SCANNED DOCS)
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                img = ImageOps.grayscale(img)
                img = ImageEnhance.Contrast(img).enhance(2.0)
                # Tesseract OCR for Sinhala + English
                text_chunk = pytesseract.image_to_string(img, lang='sin+eng', config='--oem 3 --psm 6')
            
            combined_text += text_chunk + "\n---\n"
            
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            
    return combined_text

# --- AUTO-DETECT GOOGLE MODEL ---
def get_working_model(api_key):
    # Check which model is available for this key
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            available = [m['name'].replace('models/', '') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            # Priority List
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if "gemini-pro" in available: return "gemini-pro"
            if available: return available[0]
    except:
        pass
    return "gemini-pro" # Fallback

# --- API CALL ---
def call_gemini(api_key, model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4} # Low temperature for accuracy
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

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
                c.drawString(margin, y, line)
                y -= 20
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

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Loaded")
    else:
        api_key = st.text_input("Google Gemini API Key:", type="password")
    
    st.divider()
    app_mode = st.radio("Mode:", ["Exam Paper Generator", "Document Digitizer"])

# --- Main UI ---
st.title(f"🧞‍♂️ AI Doc Genie ({app_mode})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions")
    user_instructions = st.text_area("Instructions:", height=100, placeholder="Ex: MCQ 10ක් ඕනේ...")
    ref_files = st.file_uploader("Reference Style", accept_multiple_files=True, key="ref")
with col2:
    st.subheader("2️⃣ Source Content")
    st.info("Scanned PDF නම් කරුණාකර Images ලෙස දමන්න!")
    source_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

if st.button("Generate", type="primary"):
    if not api_key or not source_files:
        st.error("Please provide API Key and Source Files")
    else:
        with st.spinner("Processing..."):
            # 1. Extract
            source_text = extract_text_from_files(source_files)
            
            # If source text is empty (scanned pdf issue), stop here
            if not source_text.strip():
                st.error("ගොනුවේ අකුරු කියවීමට නොහැක. කරුණාකර පැහැදිලි පින්තූර (Images) භාවිතා කරන්න.")
            else:
                ref_text = extract_text_from_files(ref_files)
                
                # 2. Detect Model
                model = get_working_model(api_key)
                st.session_state.current_model = model
                
                # 3. Prompt
                prompt = f"""
                Role: Sri Lankan Assistant. Mode: {app_mode}
                Instructions: {user_instructions}
                Reference: {ref_text[:3000]}
                Source: {source_text[:15000]}
                Rules: Use Unicode Sinhala. Use linear math (3/5). Output FINAL DOC only.
                """
                
                # 4. Generate
                res = call_gemini(api_key, model, prompt)
                if res.startswith("Error"): st.error(res)
                else:
                    st.session_state.generated_content = res
                    st.session_state.chat_history = []
                    st.rerun()

# --- Output ---
if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        st.text_area("Preview", st.session_state.generated_content, height=600)
        b1, b2 = st.columns(2)
        with b1: st.download_button("PDF", create_pdf(st.session_state.generated_content), "doc.pdf", "application/pdf")
        with b2: st.download_button("Word", create_docx(st.session_state.generated_content), "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with c2:
        if chat := st.chat_input("Modify..."):
            st.session_state.chat_history.append({"role": "user", "content": chat})
            prompt = f"Original: {st.session_state.generated_content}\nRequest: {chat}\nRewrite FULL text."
            with st.spinner("Updating..."):
                res = call_gemini(api_key, st.session_state.current_model, prompt)
                st.session_state.generated_content = res
                st.session_state.chat_history.append({"role": "assistant", "content": "Updated!"})
                st.rerun()
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
