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
from docx.oxml.ns import qn

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Exam Biz Master", page_icon="💎", layout="wide")

# --- 2. SESSION STATE MANAGEMENT ---
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "typst_code" not in st.session_state:
    st.session_state.typst_code = ""

# --- 3. INTELLIGENT MODEL SELECTOR (FIXES 404 ERROR) ---
def get_working_model(api_key):
    """Checks which Gemini models are available for the key and picks the best one."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Filter models that support content generation
            available = [
                m['name'].replace('models/', '') 
                for m in data.get('models', []) 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            # Priority: Pro (Best for logic) > Flash (Fast) > Standard
            if "gemini-1.5-pro" in available: return "gemini-1.5-pro"
            if "gemini-1.5-flash" in available: return "gemini-1.5-flash"
            if "gemini-1.0-pro" in available: return "gemini-1.0-pro"
            if "gemini-pro" in available: return "gemini-pro"
            if available: return available[0]
    except Exception as e:
        pass
    return "gemini-pro" # Fallback

# --- 4. API CALL HANDLER ---
def call_gemini(api_key, model, prompt, content_parts):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    parts = [{"text": prompt}]
    
    # Add Images/Text to payload
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
        "generationConfig": {"temperature": 0.3} # Low temp for strict following of rules
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error ({model}): {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- 5. FILE PROCESSING (VISION MODE + PAGE RANGE) ---
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
            
            # PDF Handling
            if ext == 'pdf':
                if vision_mode:
                    # Extracts IMAGES from PDF (Best for Geometry/Diagrams)
                    st.toast(f"📸 Scanning {file.name} (Pages {start_page}-{end_page})...", icon="⏳")
                    try:
                        images = convert_from_bytes(file.read(), first_page=start_page, last_page=end_page)
                        for img in images:
                            content_parts.append({"type": "image", "data": encode_image(img)})
                    except Exception as e:
                        st.error(f"PDF Vision Error: {e}. Ensure 'packages.txt' has poppler-utils.")
                else:
                    # Extracts TEXT from PDF (Fast, but no diagrams)
                    text = pdfminer.high_level.extract_text(file)
                    content_parts.append({"type": "text", "data": text})
            
            # Image Handling
            elif ext in ['png', 'jpg', 'jpeg']:
                img = Image.open(file)
                content_parts.append({"type": "image", "data": encode_image(img)})
            
            # Word Doc Handling
            elif ext == 'docx':
                text = docx2txt.process(file)
                content_parts.append({"type": "text", "data": text})
                
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
            
    return content_parts

# --- 6. ADVANCED WORD GENERATOR (TABLES, DIAGRAMS, SPACING) ---
def create_docx(text):
    doc = Document()
    
    # Style Config: Arial (Safe for Unicode Sinhala)
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

        # --- TABLE DETECTOR (Markdown to Word) ---
        if "|" in line and len(line.split("|")) > 2:
            table_mode = True
            row_data = [cell.strip() for cell in line.split("|") if cell.strip()]
            # Filter out divider lines (---|---)
            if "---" not in line:
                table_data.append(row_data)
            continue
        
        # --- TABLE BUILDER ---
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

        # --- HEADINGS (Questions) ---
        if line.startswith("#") or "Paper" in line or "Part" in line:
            p = doc.add_paragraph()
            run = p.add_run(line.replace("#", "").strip())
            run.bold = True
            run.font.size = Pt(12)
            p.paragraph_format.space_before = Pt(12)
        
        # --- DIAGRAM PLACEHOLDER (The Blue Text Fix) ---
        elif "[DIAGRAM" in line or "[රූප සටහන" in line:
            p = doc.add_paragraph()
            run = p.add_run(line)
            run.italic = True
            try:
                run.font.color.rgb = RGBColor(0, 0, 255) # Blue Color
            except: pass
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Add Blank Space for Drawing
            doc.add_paragraph().paragraph_format.space_after = Pt(72) # ~1 Inch space

        # --- NORMAL TEXT ---
        else:
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 7. UI LAYOUT (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Exam Biz Settings")
    
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API Key Active ✅")
    else:
        api_key = st.text_input("Gemini API Key:", type="password")
        
    st.divider()
    language = st.radio("Paper Language:", ["Sinhala", "English"])
    
    st.divider()
    st.subheader("📚 Book Processing")
    vision_mode = st.checkbox("🔮 Vision Mode", value=True, help="Must be ON for Geometry & Scanned Books")
    
    st.caption("Page Range (To handle large books):")
    c1, c2 = st.columns(2)
    with c1: start_p = st.number_input("Start Page:", min_value=1, value=1)
    with c2: end_p = st.number_input("End Page:", min_value=1, value=50)

# --- 8. MAIN UI ---
st.title(f"💎 Master Exam Generator ({language})")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Instructions & Reference")
    user_instr = st.text_area("Instructions:", height=100, placeholder="Ex: Create 5 Essay Questions matching the reference style...")
    ref_files = st.file_uploader("Reference Paper (For Structure)", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Source Books")
    src_files = st.file_uploader("Textbooks (Grade 10/11)", accept_multiple_files=True, key="src")

# --- 9. GENERATION LOGIC ---
if st.button("Generate Paper + Typst Code", type="primary"):
    if not api_key or not src_files:
        st.error("⚠️ Missing Data: Please check API Key and Source Files.")
    else:
        with st.spinner("🚀 Analyzing Content, Structure & Generating Code..."):
            
            # A. Select Best Model
            model = get_working_model(api_key)
            
            # B. Extract Content
            content_list = process_files(src_files, vision_mode, start_p, end_p)
            ref_content = process_files(ref_files, False) # Text mode for Ref is fine usually
            ref_text = ref_content[0]['data'] if ref_content and ref_content[0]['type'] == 'text' else ""

            if not content_list:
                st.error("No content extracted! Check Page Range or Vision Mode.")
            else:
                # C. THE ULTIMATE PROMPT
                prompt = f"""
                Role: Expert Exam Setter & Technical Coder.
                Language: {language}.
                
                --- TASK 1: WORD DOCUMENT CONTENT ---
                1. Create an Exam Paper based on User Instructions & Source Content.
                2. **STRUCTURE:** You MUST follow the Reference Paper's structure exactly (Number of questions, Question types).
                3. **CRITICAL RULES:**
                   - Language: 100% Unicode Sinhala (if Sinhala selected). NO legacy/gibberish fonts.
                   - Spelling: Strict check (e.g., "ත්‍රිකෝණය", "වර්ගඵලය").
                   - Math: Linear format (e.g. 3/5, x^2).
                4. **DIAGRAMS IN TEXT:** Do not draw. Write placeholder: 
                   "[DIAGRAM Q{{num}}: Description of diagram...]"
                5. **TABLES:** Use Markdown tables (| Col | Col |).
                
                --- TASK 2: TYPST CODE (VECTOR DIAGRAMS) ---
                1. After the paper text, add separator: "### TYPST START ###".
                2. Write a COMPLETE, VALID 'Typst' file using the 'cetz' package.
                3. Header: `#import "@preview/cetz:0.2.2": canvas, draw`
                4. For every diagram mentioned in Task 1, write the code to draw it.
                5. Use comments to label questions (e.g., `// Q1`).
                
                USER INSTRUCTIONS: {user_instr}
                REFERENCE STRUCTURE: {ref_text[:2500]}
                
                Generate now.
                """
                
                # D. API Call
                res = call_gemini(api_key, model, prompt, content_list)
                
                # E. Split Output (Word Text / Typst Code)
                if "### TYPST START ###" in res:
                    parts = res.split("### TYPST START ###")
                    st.session_state.generated_content = parts[0].strip()
                    st.session_state.typst_code = parts[1].strip()
                else:
                    st.session_state.generated_content = res
                    st.session_state.typst_code = "// No diagram code generated."
                
                st.rerun()

# --- 10. OUTPUT SECTION ---
if st.session_state.generated_content:
    st.divider()
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📄 Exam Paper (Word)")
        st.caption("Contains Questions, Tables, and Diagram Placeholders.")
        st.text_area("Preview", st.session_state.generated_content, height=400)
        
        # Word Download
        st.download_button(
            label="Download Word Doc (Official)",
            data=create_docx(st.session_state.generated_content),
            file_name=f"Paper_{language}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    with c2:
        st.subheader("📐 Diagrams (Typst Code)")
        st.caption("Upload this file to **typst.app** to get high-quality images.")
        st.code(st.session_state.typst_code, language="rust")
        
        # Typst Download
        st.download_button(
            label="Download Typst File",
            data=st.session_state.typst_code,
            file_name="diagrams.typ",
            mime="text/plain"
        )
