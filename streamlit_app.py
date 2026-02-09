import streamlit as st
import os
import requests
import base64
import pdfminer.high_level
import docx2txt
from PIL import Image
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import io
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- Page Config ---
st.set_page_config(page_title="Exam Biz Pro (Hybrid)", page_icon="🎓", layout="wide")

# --- Session State ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "typst_code" not in st.session_state:
    st.session_state.typst_code = ""

# --- 1. MODEL AUTO-DETECTION ---
def get_working_model(api_key):
    # Always try to use the best model for Coding + Text
    return "gemini-1.5-pro"

# --- 2. API CALL FUNCTION ---
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
        "generationConfig": {"temperature": 0.3}
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- 3. FILE PROCESSING (VISION & PAGE RANGE) ---
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
                    # Vision Mode: Converts PDF to Images
                    st.toast(f"📸 Scanning {file.name} (Pages {start_page}-{end_page})...", icon="⏳")
                    try:
                        images = convert_from_bytes(file.read(), first_page=start_page, last_page=end_page)
                        for img in images:
                            content_parts.append({"type": "image", "data": encode_image(img)})
                    except Exception as e:
                        st.error(f"PDF Error (Check packages.txt): {e}")
                else:
                    # Text Mode
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

# --- 4. ADVANCED WORD CREATOR (TABLES, DIAGRAMS, FORMATTING) ---
def create_docx(text):
    doc = Document()
    
    # Set Font (Arial is safe for Sinhala Unicode)
    style = doc.styles['Normal']
    style.font.name = 'Arial'
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

        # --- Table Detection (Markdown to Word Table) ---
        if "|" in line and len(line.split("|")) > 2:
            table_mode = True
            row_data = [cell.strip() for cell in line.split("|") if cell.strip()]
            if "---" not in line:
                table_data.append(row_data)
            continue
        
        # --- End of Table ---
        if table_mode and ("|" not in line):
            table_mode = False
            if table_data:
                try:
                    cols = len(table_data[0])
                    table = doc.add_table(rows=len(table_data), cols=cols)
                    table.style = 'Table Grid'
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            if j < cols:
                                table.cell(i, j).text = cell
                    doc.add_paragraph() # Spacer
                except: pass
                table_data = []

        # --- Headings/Questions ---
        if line.startswith("#") or "Paper" in line or "Part" in line:
            p = doc.add_paragraph()
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(12)
            p.paragraph_format.space_before = Pt(12)
        
        # --- Diagram Placeholder (Blue Text) ---
        elif "[DIAGRAM" in line or "[රූප සටහන" in line:
            p = doc.add_paragraph()
            run = p.add_run(line)
            run.italic = True
            try:
                run.font.color.rgb = RGBColor(0, 0, 255) # Blue Color
            except: pass
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Leave space for drawing
            doc.add_paragraph().paragraph_format.space_after = Pt(72) # ~1 Inch space

        # --- Normal Text ---
        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 5. UI LAYOUT ---
with st.sidebar:
    st.title("⚙️ Exam Biz Settings")
    
    # API Key
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Active")
    else:
        api_key = st.text_input("Gemini API Key:", type="password")
        
    st.divider()
    
    # Language
    language = st.radio("Paper Language (මාධ්‍යය):", ["Sinhala", "English"])
    
    st.divider()
    
    # Vision & Page Range
    st.subheader("📚 Book Processing")
    vision_mode = st.checkbox("🔮 Vision Mode (Diagrams/Scanned)", value=True, help="ජ්‍යාමිතිය සහ Scanned PDF සඳහා මෙය ON කරන්න.")
    
    st.caption("Page Range (Vision Mode සඳහා):")
    c1, c2 = st.columns(2)
    with c1: start_p = st.number_input("Start Page:", min_value=1, value=1)
    with c2: end_p = st.number_input("End Page:", min_value=1, value=50)

# --- MAIN INTERFACE ---
st.title(f"🎓 Hybrid Paper Generator ({language})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions & Structure")
    user_instr = st.text_area("Instructions:", height=100, placeholder="Ex: Create 5 Essay Questions from Geometry...")
    ref_files = st.file_uploader("Reference Paper (Structure)", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Source Content")
    src_files = st.file_uploader("Upload Textbooks (Grade 10/11)", accept_multiple_files=True, key="src")

# --- GENERATION LOGIC ---
if st.button("Generate Paper + Typst Code", type="primary"):
    if not api_key or not src_files:
        st.error("Please provide API Key and Source Files.")
    else:
        with st.spinner("Analyzing Content & Generating Code..."):
            # 1. Get Model
            model = get_working_model(api_key)
            
            # 2. Process Files
            content_list = process_files(src_files, vision_mode, start_p, end_p)
            ref_content = process_files(ref_files, False)
            ref_text = ref_content[0]['data'] if ref_content and ref_content[0]['type'] == 'text' else ""

            if not content_list:
                st.error("No content found! Check Page Range or Vision Mode.")
            else:
                # 3. STRICT HYBRID PROMPT
                prompt = f"""
                Role: Expert Exam Setter & Typst Coder.
                Language: {language}.
                
                --- TASK 1: EXAM PAPER TEXT (WORD DOC) ---
                1. Create the exam paper based on User Instructions & Source Content.
                2. **STRUCTURE:** Strictly follow the Reference Paper (Number of questions, Types).
                3. **CRITICAL RULES:**
                   - Use 100% Unicode Sinhala (e.g. "ශ්‍රේණිය", NOT "fYa%Ksh").
                   - Check spelling strictly.
                   - NO Legacy fonts.
                4. **DIAGRAMS:** In the text, write ONLY a placeholder: 
                   "[DIAGRAM Q{{num}}: Description of diagram...]"
                5. **TABLES:** Use Markdown tables (| Col 1 | Col 2 |).
                
                --- TASK 2: TYPST CODE (FOR DIAGRAMS) ---
                1. After the paper, add separator: "### TYPST START ###".
                2. Write a VALID 'Typst' file using 'cetz' package to draw diagrams for Task 1.
                3. Header: `#import "@preview/cetz:0.2.2": canvas, draw`
                4. Label each diagram using comments (e.g. `// Question 1`).
                
                USER INSTRUCTIONS: {user_instr}
                REFERENCE STRUCTURE: {ref_text[:2500]}
                
                Generate response now.
                """
                
                # 4. Call API
                res = call_gemini(api_key, model, prompt, content_list)
                
                # 5. Split Output
                if "### TYPST START ###" in res:
                    parts = res.split("### TYPST START ###")
                    st.session_state.generated_content = parts[0].strip()
                    st.session_state.typst_code = parts[1].strip()
                else:
                    st.session_state.generated_content = res
                    st.session_state.typst_code = "// No diagram code generated by AI"
                
                st.rerun()

# --- OUTPUT DISPLAY ---
if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📄 Paper (Word)")
        st.text_area("Preview Text", st.session_state.generated_content, height=400)
        st.download_button(
            label="Download Word Doc (Official)",
            data=create_docx(st.session_state.generated_content),
            file_name=f"Paper_{language}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    with c2:
        st.subheader("📐 Diagrams (Typst)")
        st.code(st.session_state.typst_code, language="rust")
        st.download_button(
            label="Download Typst File",
            data=st.session_state.typst_code,
            file_name="diagrams.typ",
            mime="text/plain"
        )
        st.info("Upload .typ file to **typst.app** to generate Vector Diagrams.")
