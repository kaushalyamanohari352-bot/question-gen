import streamlit as st
import os
from groq import Groq
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
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- Page Config ---
st.set_page_config(page_title="AI Smart Doc Pro", page_icon="🚀", layout="wide")

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
                # Advanced Image Pre-processing for Handwritten/Old Docs
                img = ImageOps.grayscale(img)
                img = ImageEnhance.Contrast(img).enhance(2.5)
                img = ImageEnhance.Sharpness(img).enhance(2.0)
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
        if line.startswith("#") or "Paper" in line or "Part" in line or "Subject:" in line:
            clean_line = line.replace("#", "").strip()
            run = p.add_run(clean_line)
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
    
    # 1. API Key
    if "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
        st.success("API Key Connected")
    else:
        api_key = st.text_input("Groq API Key:", type="password")

    st.divider()
    
    # 2. MODE SELECTOR (Requirement Met)
    app_mode = st.radio(
        "තෝරන්න (Select Mode):",
        ["Exam Paper Generator (ප්‍රශ්න පත්‍ර)", "Document Digitizer (ලිපි/ලේඛන)"]
    )
    
    st.info("💡 Digitizer Mode: අතින් ලියපු ලිපි පැහැදිලි සිංහල ලේඛන බවට පත් කරයි.")

# --- Main Interface ---
st.title(f"🤖 AI {app_mode.split('(')[0]}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Instructions & Style")
    
    # Dynamic Placeholder based on Mode
    ph_text = "උදා: මට අමාරු MCQs 10ක් ඕනේ..." if "Exam" in app_mode else "උදා: මේක රාජකාරි ලිපියක් විදිහට සකසන්න..."
    
    user_instructions = st.text_area("ඔබට අවශ්‍ය දේ (Instructions):", placeholder=ph_text, height=100)
    
    st.caption("Reference File (Optional): ආදර්ශයක් හෝ Style එකක් සඳහා.")
    ref_files = st.file_uploader("Reference (Style Guide)", accept_multiple_files=True, key="ref")

with col2:
    st.subheader("2️⃣ Source Content")
    st.caption("ඔබේ සටහන්, පින්තූර හෝ අතින් ලියූ ලිපි මෙතැනට දාන්න.")
    source_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

# --- Logic & Processing ---
if st.button("Generate (සාදන්න)", type="primary"):
    if not api_key:
        st.error("API Key is missing.")
    elif not source_files:
        st.error("Please upload Source Content.")
    else:
        with st.spinner("Analyzing & Generating..."):
            source_text = extract_text_from_files(source_files)
            ref_text = extract_text_from_files(ref_files)
            
            # --- DYNAMIC PROMPTS ---
            if "Exam" in app_mode:
                # EXAM MODE PROMPT
                system_message = f"""
                You are a Sri Lankan Exam Setter.
                TASK: Create an exam paper based on User Instructions and Source Content.
                FORMAT:
                - Use 'Standard Unicode Sinhala'.
                - MATH: Use linear format (e.g., 3/5, x^2, sqrt(x)). No complex LaTeX.
                - Questions should be numbered clearly.
                - Do not repeat words endlessly.
                """
            else:
                # DIGITIZER MODE PROMPT
                system_message = f"""
                You are a Professional Secretary/Typist.
                TASK: Convert the Source Content into a clean, professional document based on User Instructions.
                FORMAT:
                - If the source is handwritten/messy, fix spelling and grammar.
                - Use formal, official Sinhala (රාජකාරි භාෂාව) if it's a letter.
                - Ignore OCR gibberish; interpret the MEANING.
                - Format with clear paragraphs.
                """
            
            user_message = f"""
            USER INSTRUCTIONS: {user_instructions}
            
            STYLE REFERENCE: {ref_text[:3000]}
            
            SOURCE CONTENT: {source_text[:12000]}
            """

            client = Groq(api_key=api_key)
            
            try:
                completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.5,
                    max_tokens=2048
                )
                st.session_state.generated_content = completion.choices[0].message.content
                st.session_state.chat_history = []
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- Output Section ---
if st.session_state.generated_content:
    st.divider()
    
    r_c1, r_c2 = st.columns([2, 1])
    
    with r_c1:
        st.subheader("📄 Preview")
        st.text_area("", value=st.session_state.generated_content, height=600)
        
        # Download Buttons
        b1, b2 = st.columns(2)
        with b1:
            pdf = create_pdf(st.session_state.generated_content)
            st.download_button("Download PDF", pdf, "document.pdf", "application/pdf")
        with b2:
            docx = create_docx(st.session_state.generated_content)
            st.download_button("Download Word", docx, "document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
    with r_c2:
        st.subheader("💬 Modify (Chat)")
        st.write("ප්‍රතිඵලය වෙනස් කිරීමට අවශ්‍ය නම් මෙතන කියන්න.")
        
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        if chat_msg := st.chat_input("Ex: අකුරු වැරදියි, මේක හදන්න..."):
            st.session_state.chat_history.append({"role": "user", "content": chat_msg})
            
            client = Groq(api_key=api_key)
            msgs = [
                {"role": "system", "content": "You are an editor. Modify the text based on user request. Output FULL updated text."},
                {"role": "assistant", "content": st.session_state.generated_content},
                {"role": "user", "content": chat_msg}
            ]
            
            with st.spinner("Updating..."):
                resp = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
                st.session_state.generated_content = resp.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": "Updated!"})
                st.rerun()
