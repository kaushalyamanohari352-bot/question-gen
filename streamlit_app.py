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
st.set_page_config(page_title="AI Doc Genie (Ultimate)", page_icon="🧬", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "current_model" not in st.session_state:
    st.session_state.current_model = "gemini-pro"

# --- 1. MODEL AUTO-DETECTION (FIX 404 ERROR) ---
def get_working_model(api_key):
    # Try to fetch available models
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Filter models that support generateContent
            available = []
            for m in data.get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    available.append(m['name'].replace('models/', ''))
            
            # Priority Selection
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if "gemini-1.0-pro" in available: return "gemini-1.0-pro"
            if "gemini-pro" in available: return "gemini-pro"
            
            if available: return available[0] # Pick whatever is there
            
    except Exception as e:
        print(f"Model fetch error: {e}")
    
    return "gemini-pro" # Fallback

# --- 2. FILE PROCESSING (FIX GEOMETRY PDF) ---
def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_files(uploaded_files, vision_mode=False):
    content_parts = []
    
    if not uploaded_files:
        return content_parts
        
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            
            # --- PDF HANDLING ---
            if ext == 'pdf':
                if vision_mode:
                    # GEOMETRY FIX: Convert PDF to Images
                    st.toast(f"🖼️ Converting PDF to Images: {file.name}...", icon="🔄")
                    try:
                        images = convert_from_bytes(file.read())
                        # Limit pages to avoid timeout (First 5 pages)
                        for img in images[:10]:
                            content_parts.append({"type": "image", "data": encode_image(img)})
                    except Exception as e:
                        st.error(f"Error converting PDF (Check packages.txt): {e}")
                else:
                    # Text Mode
                    text = pdfminer.high_level.extract_text(file)
                    if not text or len(text.strip()) < 50:
                        st.warning(f"⚠️ {file.name} හි අකුරු නැත. 'Vision Mode' දමා නැවත උත්සාහ කරන්න.")
                    else:
                        content_parts.append({"type": "text", "data": text})
            
            # --- IMAGE HANDLING ---
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                content_parts.append({"type": "image", "data": encode_image(img)})
            
            # --- DOCS ---
            elif ext == 'docx':
                text = docx2txt.process(file)
                content_parts.append({"type": "text", "data": text})
                
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")
            
    return content_parts

# --- 3. API CALL ---
def call_gemini(api_key, model, prompt, content_parts):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    parts = [{"text": prompt}]
    
    for item in content_parts:
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

# --- 4. EXPORT (FONTS & DOWNLOADS) ---
def register_fonts(custom_path=None):
    path = custom_path if custom_path else "sinhala.ttf"
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont('Sinhala', path))
            return True
        except: return False
    return False

def create_pdf(text, font_path=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    has_font = register_fonts(font_path)
    font_name = "Sinhala" if has_font else "Helvetica"
    
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

# --- 5. UI ---
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
    # RESTORED FEATURE: Vision Mode
    vision_mode = st.checkbox("🔮 Vision / Force OCR Mode", help="Use this for Scanned PDFs or Geometry papers.")
    if vision_mode:
        st.caption("✅ Geometry PDF සඳහා මෙය දාන්න.")
        
    st.divider()
    # RESTORED FEATURE: Custom Font
    st.subheader("🅰️ Custom Font")
    uploaded_font = st.file_uploader("Upload .ttf", type="ttf")
    custom_font_path = None
    if uploaded_font:
        with open("custom.ttf", "wb") as f: f.write(uploaded_font.getbuffer())
        custom_font_path = "custom.ttf"
        st.success("Font Loaded!")

st.title(f"🧬 AI Doc Genie ({app_mode})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions")
    user_instr = st.text_area("Instructions:", height=100)
    ref_files = st.file_uploader("Reference Style", accept_multiple_files=True, key="ref")
with col2:
    st.subheader("2️⃣ Source Content")
    src_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

if st.button("Generate", type="primary"):
    if not api_key or not src_files:
        st.error("Please provide API Key and Source Files.")
    else:
        with st.spinner("Detecting AI Model & Processing..."):
            # 1. Auto-Detect Model (Fix 404)
            model = get_working_model(api_key)
            st.session_state.current_model = model
            # st.toast(f"Using Model: {model}") # Uncomment to see which model is used
            
            # 2. Process Files (Fix Geometry)
            content_list = process_files(src_files, vision_mode=vision_mode)
            
            if not content_list:
                st.error("No valid content found. Try turning on Vision Mode.")
            else:
                # 3. Prompt Engineering (Sinhala/Math)
                prompt = f"""
                Role: Sri Lankan Assistant. Mode: {app_mode}.
                Instructions: {user_instr}.
                Reference Style: (User provided reference docs).
                Task: Read the input images/text. Extract Geometry diagrams/text if present.
                Rules:
                1. Output ONLY the final document content.
                2. Use Standard Unicode Sinhala.
                3. Use Linear Math format (e.g. 3/5, x^2 + y^2 = r^2).
                """
                
                # 4. Generate
                res = call_gemini(api_key, model, prompt, content_list)
                
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
