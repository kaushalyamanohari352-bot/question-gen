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
st.set_page_config(page_title="Exam Paper Biz Pro", page_icon="🎓", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "current_model" not in st.session_state:
    st.session_state.current_model = "gemini-pro"

# --- 1. MODEL AUTO-DETECTION ---
def get_working_model(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            available = []
            for m in data.get('models', []):
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    available.append(m['name'].replace('models/', ''))
            
            # Priority: Pro (Big Context) > Flash (Fast)
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-pro" in available: return "gemini-pro"
            if available: return available[0]
    except Exception:
        pass
    return "gemini-pro"

# --- 2. FILE PROCESSING ---
def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_files(uploaded_files, vision_mode=False, start_page=1, end_page=None):
    content_parts = []
    
    if not uploaded_files:
        return content_parts
        
    for file in uploaded_files:
        try:
            ext = file.name.split('.')[-1].lower()
            
            # --- PDF HANDLING ---
            if ext == 'pdf':
                if vision_mode:
                    # Vision Mode: Converts PDF to Images (Best for Geometry/Diagrams)
                    # Note: Processing 400 pages with Vision will timeout, so use Range!
                    st.toast(f"📸 Scanning {file.name} (Pages {start_page}-{end_page})...", icon="⏳")
                    try:
                        images = convert_from_bytes(file.read(), first_page=start_page, last_page=end_page)
                        
                        # Warning for large batches
                        if len(images) > 30:
                            st.warning(f"⚠️ {file.name}: ඔබ පිටු {len(images)}ක් තෝරා ඇත. Vision Mode එකේදී මෙය ප්‍රමාද විය හැක.")
                        
                        for img in images:
                            content_parts.append({"type": "image", "data": encode_image(img)})
                    except Exception as e:
                        st.error(f"PDF Error: {e}")
                else:
                    # Text Mode: Reads whole text (Fast, Good for Theory, No Diagrams)
                    st.toast(f"📖 Reading Text from {file.name}...", icon="📄")
                    text = pdfminer.high_level.extract_text(file)
                    content_parts.append({"type": "text", "data": text})
            
            # --- IMAGES ---
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

# --- 4. EXPORT ---
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
    st.title("⚙️ Business Tools")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Active")
    else:
        api_key = st.text_input("Gemini API Key:", type="password")
        
    st.divider()
    
    # 🌍 LANGUAGE SELECTOR (New Feature)
    language = st.radio("Paper Language (මාධ්‍යය):", ["Sinhala", "English"])
    
    st.divider()
    
    # 🔮 VISION MODE & RANGE
    st.subheader("📚 Book Processing")
    vision_mode = st.checkbox("🔮 Vision Mode (Diagrams/Scanned)", value=True, help="ජ්‍යාමිතිය වැනි පාඩම් සඳහා මෙය ON කරන්න.")
    
    st.caption("Page Range (Vision Mode සඳහා වඩාත් සුදුසුයි):")
    c1, c2 = st.columns(2)
    with c1: start_p = st.number_input("Start Page:", min_value=1, value=1)
    with c2: end_p = st.number_input("End Page:", min_value=1, value=50)
    
    st.info("Tip: Vision Mode OFF කළොත් මුළු පොතම (Text Only) ඉක්මනින් කියවන්න පුළුවන්.")

    st.divider()
    st.subheader("🅰️ Formatting")
    uploaded_font = st.file_uploader("Custom Font (.ttf)", type="ttf")
    custom_font_path = None
    if uploaded_font:
        with open("custom.ttf", "wb") as f: f.write(uploaded_font.getbuffer())
        custom_font_path = "custom.ttf"

st.title(f"🎓 Exam Paper Biz ({language})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Requirements")
    user_instr = st.text_area("Instructions:", height=150, placeholder="Ex: Create 5 hard essay questions from Geometry...")
    ref_files = st.file_uploader("Reference Paper (Style Guide)", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Textbooks / Notes")
    src_files = st.file_uploader("Upload Textbooks (Grade 10/11)", accept_multiple_files=True, key="src")

if st.button("Generate Paper", type="primary"):
    if not api_key or not src_files:
        st.error("Please provide API Key and Source Files.")
    else:
        with st.spinner(f"Analyzing content in {language}..."):
            # 1. Detect Model
            model = get_working_model(api_key)
            st.session_state.current_model = model
            
            # 2. Process Files
            # If Vision Mode is ON, we use the Page Range.
            # If OFF, we try to extract text from the whole file.
            content_list = process_files(src_files, vision_mode=vision_mode, start_page=start_p, end_page=end_p)
            
            # Process Reference
            ref_content = process_files(ref_files, vision_mode=False)
            ref_text = ref_content[0]['data'] if ref_content and ref_content[0]['type'] == 'text' else "Standard Exam Format"
            
            if not content_list:
                st.error("No content extracted. Please check your settings.")
            else:
                # 3. Prompt with Language
                prompt = f"""
                Role: Professional Exam Setter.
                Target Audience: Sri Lankan O/L Students.
                Output Language: {language}.
                
                Instructions: {user_instr}
                Reference Style: {ref_text[:3000]}
                
                Task:
                Create a high-quality exam paper based on the provided source content.
                If the content contains diagrams (Geometry), analyze them and create relevant questions.
                
                Formatting Rules:
                1. Use {language} language strictly.
                2. If Sinhala: Use Unicode Sinhala.
                3. Use Linear Math format (e.g. 3/5, x^2).
                4. Output ONLY the final paper content.
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
        with b1: st.download_button("Download PDF", create_pdf(st.session_state.generated_content, custom_font_path), f"Paper_{language}.pdf", "application/pdf")
        with b2: st.download_button("Download Word", create_docx(st.session_state.generated_content), f"Paper_{language}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
