import streamlit as st
import os
import requests
import base64
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
st.set_page_config(page_title="AI Doc Genie (Vision Edition)", page_icon="🔮", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""

# --- FONTS HANDLING ---
def register_fonts(custom_font_path=None):
    # Use custom font if uploaded, else default sinhala.ttf
    font_path = custom_font_path if custom_font_path else "sinhala.ttf"
    
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Sinhala', font_path))
            return True
        except:
            return False
    return False

# --- IMAGE PROCESSING ---
def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- TEXT EXTRACTION ---
def process_files(uploaded_files, use_vision_mode=False):
    combined_content = [] # List to store text or image data
    
    if not uploaded_files:
        return combined_content
    
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            
            # 1. PDF Handling
            if ext == 'pdf':
                if use_vision_mode:
                    st.toast(f"🔮 Vision Mode: Reading {file.name} visually...", icon="👁️")
                    images = convert_from_bytes(file.read())
                    # Limit to first 5 pages to prevent overload
                    for img in images[:5]: 
                        combined_content.append({"type": "image", "data": encode_image(img)})
                else:
                    # Normal Text Mode
                    text = pdfminer.high_level.extract_text(file)
                    if not text or len(text.strip()) < 50:
                        st.error(f"⚠️ '{file.name}' කියවීමට නොහැක. වම් පැත්තේ 'Vision Mode' දමා නැවත උත්සාහ කරන්න.")
                    else:
                        combined_content.append({"type": "text", "data": text})

            # 2. Images
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                combined_content.append({"type": "image", "data": encode_image(img)})
            
            # 3. Text Docs
            elif ext == 'docx':
                text = docx2txt.process(file)
                combined_content.append({"type": "text", "data": text})
            elif ext == 'txt':
                text = file.read().decode('utf-8')
                combined_content.append({"type": "text", "data": text})
                
        except Exception as e:
            st.error(f"Error: {e}")
            
    return combined_content

# --- GEMINI API CALL (Supports Text + Images) ---
def call_gemini_vision(api_key, prompt, content_list):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    # Construct Parts
    parts = [{"text": prompt}]
    
    for item in content_list:
        if item["type"] == "text":
            parts.append({"text": item["data"]})
        elif item["type"] == "image":
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": item["data"]
                }
            })

    data = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.4}
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- EXPORT FUNCTIONS ---
def create_pdf(text, custom_font_path=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    font_loaded = register_fonts(custom_font_path)
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
    st.title("⚙️ Control Panel")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Active")
    else:
        api_key = st.text_input("Gemini API Key:", type="password")
    
    st.divider()
    app_mode = st.radio("Mode:", ["Exam Paper Generator", "Document Digitizer"])
    
    st.divider()
    # 🔥 VISION MODE SWITCH
    use_vision = st.checkbox("🔮 Vision Mode (සංකීර්ණ PDF සඳහා)", help="PDF එකේ අකුරු කැඩෙනවා නම් මේක දාන්න.")
    
    st.divider()
    # 🔥 FONT SELECTOR
    st.subheader("🅰️ Font Settings")
    uploaded_font = st.file_uploader("Upload Custom Font (.ttf)", type="ttf")
    
    custom_font_path = None
    if uploaded_font:
        with open("custom_font.ttf", "wb") as f:
            f.write(uploaded_font.getbuffer())
        custom_font_path = "custom_font.ttf"
        st.success("Custom Font Applied!")

st.title(f"🔮 AI Doc Genie ({app_mode})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions")
    user_instructions = st.text_area("Instructions:", height=100)
    ref_files = st.file_uploader("Reference Style", accept_multiple_files=True, key="ref")
with col2:
    st.subheader("2️⃣ Source Content")
    source_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

if st.button("Generate", type="primary"):
    if not api_key or not source_files:
        st.error("Missing Data")
    else:
        with st.spinner("Processing with Gemini Vision..."):
            # Process files (convert to images if Vision Mode is ON)
            content_list = process_files(source_files, use_vision_mode=use_vision)
            
            if not content_list:
                st.error("No valid content found.")
            else:
                # Add instructions to the prompt
                prompt = f"""
                Role: Sri Lankan Assistant. Mode: {app_mode}.
                Instructions: {user_instructions}.
                Task: Read the provided images/text carefully. Extract content and generate the output.
                Rules: Use Unicode Sinhala. Format math linearly.
                """
                
                # Call API
                res = call_gemini_vision(api_key, prompt, content_list)
                
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
        with b1: st.download_button("PDF", create_pdf(st.session_state.generated_content, custom_font_path), "doc.pdf", "application/pdf")
        with b2: st.download_button("Word", create_docx(st.session_state.generated_content), "doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
