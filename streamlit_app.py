import streamlit as st
import os
import requests
import base64
import pdfminer.high_level
import docx2txt
from PIL import Image
from pdf2image import convert_from_bytes
import io
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Exam & Biz Master", page_icon="💼", layout="wide")

# --- 2. SESSION STATE ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "typst_code" not in st.session_state:
    st.session_state.typst_code = ""

# --- 3. MODEL SELECTOR ---
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

# --- 4. API CALL ---
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

# --- 5. FILE PROCESSING ---
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
                    st.toast(f"Processing {file.name}...", icon="⏳")
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
        except: pass
    return content_parts

# --- 6. WORD GENERATOR ---
def create_docx(text, doc_type="Paper"):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    
    title = "Generated Document" if doc_type == "Business" else "Generated Exam Paper"
    heading = doc.add_heading(title, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    lines = text.split('\n')
    table_mode = False
    table_data = []

    for line in lines:
        line = line.strip()
        if not line: continue

        if "|" in line and len(line.split("|")) > 2:
            table_mode = True
            row_data = [cell.strip() for cell in line.split("|") if cell.strip()]
            if "---" not in line: table_data.append(row_data)
            continue
        
        if table_mode and ("|" not in line):
            table_mode = False
            if table_data:
                try:
                    cols = len(table_data[0])
                    table = doc.add_table(rows=len(table_data), cols=cols)
                    table.style = 'Table Grid'
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            if j < cols: table.cell(i, j).text = cell
                    doc.add_paragraph()
                except: pass
                table_data = []

        if (line.startswith("#") or "Paper" in line or "Part" in line) and doc_type == "Paper":
            p = doc.add_paragraph()
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(12)
            p.paragraph_format.space_before = Pt(12)
        
        elif ("[DIAGRAM" in line or "[රූප සටහන" in line) and doc_type == "Paper":
            p = doc.add_paragraph()
            run = p.add_run(line)
            run.italic = True
            try: run.font.color.rgb = RGBColor(0, 0, 255)
            except: pass
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph().paragraph_format.space_after = Pt(72)

        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 7. SIDEBAR & MODES ---
with st.sidebar:
    st.title("⚙️ Business Tools")
    if "GEMINI_API_KEY" in st.secrets: api_key = st.secrets["GEMINI_API_KEY"]
    else: api_key = st.text_input("API Key:", type="password")
    
    st.divider()
    
    # --- MODE SELECTOR (THIS FIXES YOUR ISSUE) ---
    app_mode = st.radio("Select Mode:", ["Exam Paper Generator", "Letters & Tutes (Business)"])
    
    st.divider()
    language = st.radio("Language:", ["Sinhala", "English"])
    
    if app_mode == "Exam Paper Generator":
        st.subheader("📚 Book Settings")
        vision_mode = st.checkbox("🔮 Vision Mode", value=True)
        c1, c2 = st.columns(2)
        with c1: start_p = st.number_input("Start Page", 1, value=1)
        with c2: end_p = st.number_input("End Page", 1, value=50)
    else:
        vision_mode = False # Usually not needed for letters, but can enable if typing from image
        start_p, end_p = 1, 5

# --- 8. MAIN UI LOGIC ---
st.title(f"💼 {app_mode}")

if app_mode == "Exam Paper Generator":
    # --- EXAM MODE UI ---
    col1, col2 = st.columns(2)
    with col1:
        user_instr = st.text_area("Instructions:", height=100, placeholder="Ex: Create 5 Essay Questions...")
        ref_files = st.file_uploader("Reference Paper", accept_multiple_files=True, key="ref")
    with col2:
        src_files = st.file_uploader("Textbooks", accept_multiple_files=True, key="src")
        
    if st.button("Generate Paper", type="primary"):
        if not api_key: st.error("No API Key")
        else:
            with st.spinner("Generating Paper..."):
                model = get_working_model(api_key)
                content = process_files(src_files, vision_mode, start_p, end_p)
                ref_content = process_files(ref_files, False)
                ref_text = ref_content[0]['data'] if ref_content and ref_content[0]['type'] == 'text' else ""
                
                prompt = f"""
                Role: Expert Exam Setter. Language: {language}.
                Task 1: Create Exam Paper (Word). Follow Reference Structure exactly.
                Rules: Unicode Sinhala Only. Strict Spelling. Math: Linear format.
                Diagrams: Write "[DIAGRAM: Description]" only.
                Task 2: Typst Code. Add separator "### TYPST START ###" then write valid cetz code.
                User Inst: {user_instr}
                Reference: {ref_text[:2000]}
                """
                res = call_gemini(api_key, model, prompt, content)
                
                if "### TYPST START ###" in res:
                    parts = res.split("### TYPST START ###")
                    st.session_state.generated_content = parts[0].strip()
                    st.session_state.typst_code = parts[1].strip()
                else:
                    st.session_state.generated_content = res
                    st.session_state.typst_code = "// No code"
                st.rerun()

    if st.session_state.generated_content:
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📄 Word Paper")
            st.text_area("Preview", st.session_state.generated_content, height=300)
            st.download_button("Download Word", create_docx(st.session_state.generated_content, "Paper"), "Paper.docx")
        with c2:
            st.subheader("📐 Typst Code")
            st.code(st.session_state.typst_code)
            st.download_button("Download Typst", st.session_state.typst_code, "diagrams.typ")

else:
    # --- BUSINESS MODE UI (Letters/Tutes) ---
    col1, col2 = st.columns(2)
    with col1:
        doc_type = st.selectbox("Document Type:", ["Letter", "Tute / Note", "Report", "Assignment"])
        user_instr = st.text_area("Details (Content/Topic):", height=150, placeholder="Ex: Write a leave letter... or Create a Tute about Photosynthesis...")
    with col2:
        src_files = st.file_uploader("Source Material (Optional images/docs)", accept_multiple_files=True, key="biz_src")
    
    if st.button("Create Document", type="primary"):
        if not api_key: st.error("No API Key")
        else:
            with st.spinner("Writing Document..."):
                model = get_working_model(api_key)
                content = process_files(src_files, False) # Vision off for speed usually
                
                prompt = f"""
                Role: Professional Secretary & Academic Writer.
                Task: Write a {doc_type}.
                Language: {language} (Strict Unicode Sinhala if selected).
                Details: {user_instr}
                Formatting: Professional, Clear structure. Use Markdown tables if needed.
                """
                res = call_gemini(api_key, model, prompt, content)
                st.session_state.generated_content = res
                st.session_state.typst_code = "" # Clear typst
                st.rerun()

    if st.session_state.generated_content:
        st.divider()
        st.subheader(f"📄 Generated {doc_type}")
        st.text_area("Preview", st.session_state.generated_content, height=500)
        st.download_button("Download Document (Word)", create_docx(st.session_state.generated_content, "Business"), "Document.docx")
