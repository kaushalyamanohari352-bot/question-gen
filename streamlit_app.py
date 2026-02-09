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
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- Page Config ---
st.set_page_config(page_title="Pro Exam Biz", page_icon="🎓", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""

# --- 1. MODEL AUTO-DETECTION ---
def get_working_model(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            available = [m['name'].replace('models/', '') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-pro" in available: return "gemini-pro"
            if available: return available[0]
    except: pass
    return "gemini-pro"

# --- 2. FILE PROCESSING ---
def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_files(uploaded_files, vision_mode=False, start_page=1, end_page=None):
    content_parts = []
    if not uploaded_files: return content_parts
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            if ext == 'pdf':
                if vision_mode:
                    st.toast(f"📸 Scanning {file.name}...", icon="⏳")
                    try:
                        images = convert_from_bytes(file.read(), first_page=start_page, last_page=end_page)
                        for img in images: content_parts.append({"type": "image", "data": encode_image(img)})
                    except: st.error("PDF Error. Check packages.txt")
                else:
                    text = pdfminer.high_level.extract_text(file)
                    content_parts.append({"type": "text", "data": text})
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                content_parts.append({"type": "image", "data": encode_image(img)})
            elif ext == 'docx':
                text = docx2txt.process(file)
                content_parts.append({"type": "text", "data": text})
        except Exception as e: st.error(f"Error: {e}")
    return content_parts

# --- 3. API CALL ---
def call_gemini(api_key, model, prompt, content_parts):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    parts = [{"text": prompt}]
    for item in content_parts:
        if item["type"] == "text": parts.append({"text": item["data"]})
        elif item["type"] == "image": parts.append({"inline_data": {"mime_type": "image/jpeg", "data": item["data"]}})
    data = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.3}}
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200: return response.json()['candidates'][0]['content']['parts'][0]['text']
        else: return f"Error: {response.text}"
    except Exception as e: return f"Connection Error: {e}"

# --- 4. ADVANCED WORD DOCUMENT CREATOR (TABLES & SPACING) ---
def create_docx(text):
    doc = Document()
    
    # Set Default Font
    style = doc.styles['Normal']
    style.font.name = 'Arial' # Works better for Mixed Sinhala/English
    style.font.size = Pt(11)
    
    # Title
    heading = doc.add_heading('Generated Exam Paper', 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    lines = text.split('\n')
    table_mode = False
    table_data = []

    for line in lines:
        line = line.strip()
        if not line: continue

        # --- Table Detection (Starts with |) ---
        if "|" in line and len(line.split("|")) > 2:
            table_mode = True
            # Clean formatting bars
            row_data = [cell.strip() for cell in line.split("|") if cell.strip()]
            # Skip separator lines (e.g., ---|---|---)
            if "---" not in line:
                table_data.append(row_data)
            continue
        
        # --- End of Table ---
        if table_mode and ("|" not in line):
            table_mode = False
            if table_data:
                # Create Table in Word
                cols = len(table_data[0])
                table = doc.add_table(rows=len(table_data), cols=cols)
                table.style = 'Table Grid'
                for i, row in enumerate(table_data):
                    for j, cell in enumerate(row):
                        if j < cols:
                            table.cell(i, j).text = cell
                doc.add_paragraph() # Spacer after table
                table_data = []

        # --- Headings/Questions ---
        if line.startswith("#") or "Paper" in line or "Part" in line:
            p = doc.add_paragraph()
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(12)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
        
        # --- Diagram Placeholders ---
        elif "[DIAGRAM" in line or "[රූප සටහන" in line:
            p = doc.add_paragraph()
            run = p.add_run(line)
            run.italic = True
            run.font.color.rgb = (255, 0, 0) # Red color for attention
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph() # Extra space for drawing
            doc.add_paragraph()
            doc.add_paragraph()

        # --- Normal Text ---
        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6) # Nice spacing between lines

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def create_pdf(text, custom_font=None):
    # Simplified PDF for preview (Word is recommended)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 800
    for line in text.split('\n'):
        c.drawString(40, y, line[:90])
        y -= 15
        if y < 50: c.showPage(); y = 800
    c.save()
    buffer.seek(0)
    return buffer

# --- 5. UI ---
with st.sidebar:
    st.title("⚙️ Exam Biz Pro")
    if "GEMINI_API_KEY" in st.secrets: api_key = st.secrets["GEMINI_API_KEY"]
    else: api_key = st.text_input("API Key:", type="password")
    
    st.divider()
    language = st.radio("Language:", ["Sinhala", "English"])
    
    st.divider()
    st.subheader("📚 Book Settings")
    vision_mode = st.checkbox("🔮 Vision Mode", value=True)
    c1, c2 = st.columns(2)
    with c1: start_p = st.number_input("Start Page", 1, value=1)
    with c2: end_p = st.number_input("End Page", 1, value=50)

st.title(f"🎓 Paper Generator ({language})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions")
    user_instr = st.text_area("Instructions:", height=100, placeholder="Ex: Create 5 Essay Questions...")
    ref_files = st.file_uploader("Reference Paper (Structure)", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Source Books")
    src_files = st.file_uploader("Upload Textbooks", accept_multiple_files=True, key="src")

if st.button("Generate Professional Paper", type="primary"):
    if not api_key or not src_files: st.error("Missing Data")
    else:
        with st.spinner("Analyzing Structure & Content..."):
            model = get_working_model(api_key)
            content = process_files(src_files, vision_mode, start_p, end_p)
            ref_content = process_files(ref_files, False)
            ref_text = ref_content[0]['data'] if ref_content and ref_content[0]['type'] == 'text' else ""

            prompt = f"""
            Role: Expert Exam Setter. Language: {language}.
            
            USER INSTRUCTIONS: {user_instr}
            
            REFERENCE STRUCTURE (FOLLOW STRICTLY):
            1. Analyze the Reference text below.
            2. Match the EXACT number of questions (e.g. if Part A has 20 Qs, generate 20 Qs).
            3. Match the Question Types (MCQ, Structured, Essay).
            Reference Text: {ref_text[:3000]}
            
            FORMATTING RULES:
            1. TABLES: If a question needs a table, output it using Markdown format (e.g. | Col 1 | Col 2 |).
            2. DIAGRAMS: You cannot draw. Instead, write a detailed description in brackets like:
               "[DIAGRAM: Draw a right-angled triangle ABC where AB=5cm...]"
               (User will draw this manually in Word).
            3. SPACING: Leave space for answers.
            4. FONT: Use Standard Unicode Sinhala. NO Legacy fonts.
            
            Generate the paper now.
            """
            
            res = call_gemini(api_key, model, prompt, content)
            if res.startswith("Error"): st.error(res)
            else:
                st.session_state.generated_content = res
                st.rerun()

if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        st.text_area("Preview", st.session_state.generated_content, height=600)
        st.caption("⚠️ පෙනුම සම්පූර්ණ නැත. නියම පෙනුම සඳහා 'Download Word' භාවිතා කරන්න.")
        b1, b2 = st.columns(2)
        with b1: st.download_button("Download PDF", create_pdf(st.session_state.generated_content), "Paper.pdf", "application/pdf")
        with b2: st.download_button("Download Word (Recommended)", create_docx(st.session_state.generated_content), "Paper.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
