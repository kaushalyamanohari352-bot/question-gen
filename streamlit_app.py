import streamlit as st
import os
import google.generativeai as genai
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
st.set_page_config(page_title="AI Doc Genie (Gemini)", page_icon="🧞‍♂️", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

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
            if ext == 'pdf':
                combined_text += pdfminer.high_level.extract_text(file) + "\n---\n"
            elif ext == 'docx':
                combined_text += docx2txt.process(file) + "\n---\n"
            elif ext == 'txt':
                combined_text += file.read().decode('utf-8') + "\n---\n"
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                img = ImageOps.grayscale(img)
                img = ImageEnhance.Contrast(img).enhance(2.5)
                text = pytesseract.image_to_string(img, lang='sin+eng', config='--oem 3 --psm 6')
                combined_text += text + "\n---\n"
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
    return combined_text

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
                if y < 50:
                    c.showPage()
                    c.setFont(font_name, 11)
                    y = 800
        c.drawString(margin, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            c.setFont(font_name, 11)
            y = 800
    c.save()
    buffer.seek(0)
    return buffer

def create_docx(text):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        p = doc.add_paragraph()
        if line.startswith("#") or "Paper" in line or "Part" in line:
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(13)
        else:
            p.add_run(line)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("Gemini Key Connected")
    else:
        api_key = st.text_input("Google Gemini API Key:", type="password")

    st.divider()
    app_mode = st.radio("තෝරන්න:", ["Exam Paper Generator", "Document Digitizer"])

# --- Main Interface ---
st.title(f"🧞‍♂️ AI Doc Genie ({app_mode})")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Instructions")
    ph = "MCQ 10ක් ඕනේ..." if "Exam" in app_mode else "ලිපියක් Type කරන්න..."
    user_instructions = st.text_area("Instructions:", placeholder=ph, height=100)
    ref_files = st.file_uploader("Reference Style", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Source Content")
    source_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

# --- Processing with Gemini ---
if st.button("Generate (සාදන්න)", type="primary"):
    if not api_key:
        st.error("API Key is missing.")
    elif not source_files:
        st.error("Please upload Source Content.")
    else:
        genai.configure(api_key=api_key)
        
        # --- FIXED MODEL NAME HERE ---
        model = genai.GenerativeModel('gemini-pro')

        with st.spinner("Gemini is working..."):
            source_text = extract_text_from_files(source_files)
            ref_text = extract_text_from_files(ref_files)
            
            prompt = f"""
            Role: Sri Lankan Assistant. Mode: {app_mode}
            User Instructions: {user_instructions}
            Reference Style: {ref_text[:5000]}
            Source Content: {source_text[:15000]}
            Requirements:
            1. Use Standard Unicode Sinhala.
            2. If Exam: Use linear math format (e.g. 3/5, x^2).
            3. If Digitizer: Fix grammar.
            4. Output ONLY final text.
            """

            try:
                response = model.generate_content(prompt)
                st.session_state.generated_content = response.text
                st.session_state.chat_history = []
                st.rerun()
            except Exception as e:
                st.error(f"Gemini Error: {e}")

# --- Output ---
if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("📄 Preview")
        st.text_area("", value=st.session_state.generated_content, height=600)
        b1, b2 = st.columns(2)
        with b1:
            st.download_button("Download PDF", create_pdf(st.session_state.generated_content), "doc.pdf", "application/pdf")
        with b2:
            st.download_button("Download Word", create_docx(st.session_state.generated_content), "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with c2:
        st.subheader("💬 Chat (Modify)")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        if chat_msg := st.chat_input("වෙනස්කම් කියන්න..."):
            st.session_state.chat_history.append({"role": "user", "content": chat_msg})
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            chat_prompt = f"""
            Original Text: {st.session_state.generated_content}
            User Request: {chat_msg}
            Task: Rewrite FULL text with changes.
            """
            
            with st.spinner("Updating..."):
                resp = model.generate_content(chat_prompt)
                st.session_state.generated_content = resp.text
                st.session_state.chat_history.append({"role": "assistant", "content": "Updated!"})
                st.rerun()
