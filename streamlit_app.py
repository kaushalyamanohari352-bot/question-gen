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

# --- Page Config ---
st.set_page_config(page_title="AI Pro Assistant", page_icon="🧠", layout="wide")

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
                img = ImageEnhance.Contrast(img).enhance(2.0)
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
    
    # Simple formatting logic for PDF
    for paragraph in text.split('\n'):
        words = paragraph.split()
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
    for line in text.split('\n'):
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    
    if "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
        st.success("API Key Connected")
    else:
        api_key = st.text_input("Groq API Key:", type="password")
        
    st.info("Remember to rename your font file in GitHub to 'sinhala.ttf'")

# --- Main Interface ---
st.title("🧠 AI Super Document Generator")
st.write("Reference (Style) files සහ Source (Content) files වෙන වෙනම ලබා දී ඔබට අවශ්‍ය දේ නිශ්චිතව සාදාගන්න.")

col1, col2 = st.columns(2)

# 1. Custom Instructions
with col1:
    st.subheader("1️⃣ Instructions (උපදෙස්)")
    user_instructions = st.text_area(
        "AI එකට කළ යුතු දේ කියන්න:",
        placeholder="Eg: මට අමාරු මට්ටමේ MCQs 20ක් ඕනේ. හෝ මේක රාජකාරි ලිපියක් විදිහට සකසන්න.",
        height=150
    )

    st.subheader("2️⃣ Reference / Style (ආදර්ශ)")
    st.caption("AI එකට අදහසක් ගන්න පරණ Papers හෝ Format upload කරන්න (Optional)")
    ref_files = st.file_uploader("Reference Files", accept_multiple_files=True, key="ref")

# 2. Source Content
with col2:
    st.subheader("3️⃣ Source Content (පාඩම/කරුණු)")
    st.caption("ප්‍රශ්න හැදීමට අවශ්‍ය පාඩම්, සටහන් හෝ පින්තූර මෙතැනට දාන්න.")
    source_files = st.file_uploader("Source Files", accept_multiple_files=True, key="src")

# --- Processing ---
if st.button("Generate Output (සාදන්න)", type="primary"):
    if not api_key:
        st.error("Please provide an API Key.")
    elif not source_files:
        st.error("Please upload Source Files (පාඩම/කරුණු).")
    else:
        # Extract Texts
        with st.spinner("ගොනු කියවමින් (Reading Files)..."):
            source_text = extract_text_from_files(source_files)
            ref_text = extract_text_from_files(ref_files) if ref_files else "No references provided."
            
        # Build the Ultimate Prompt
        system_message = f"""
        You are an expert Sri Lankan Assistant.
        
        YOUR GOAL:
        Follow the user's specific INSTRUCTIONS below perfectly.
        
        USER INSTRUCTIONS:
        "{user_instructions}"
        
        REFERENCE MATERIAL (Use this for STYLE/FORMAT only):
        {ref_text[:5000]} 
        (Ignore the content of reference, just look at how it is written/structured).
        
        OUTPUT FORMAT:
        Use Standard Unicode Sinhala. 
        Ensure professional formatting.
        """
        
        user_message = f"""
        SOURCE CONTENT (Use this data to generate the output):
        {source_text[:15000]}
        """

        client = Groq(api_key=api_key)
        
        with st.spinner("AI සිතමින් පවතී (Thinking)..."):
            try:
                completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7
                )
                st.session_state.generated_content = completion.choices[0].message.content
                st.session_state.chat_history = [] # Reset chat
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- Results Area ---
if st.session_state.generated_content:
    st.divider()
    r_col1, r_col2 = st.columns([2, 1])
    
    with r_col1:
        st.subheader("📄 ප්‍රතිඵලය (Result)")
        st.text_area("Preview", value=st.session_state.generated_content, height=600)
        
        # Download Buttons
        d1, d2 = st.columns(2)
        with d1:
            pdf_bytes = create_pdf(st.session_state.generated_content)
            st.download_button("Download PDF", pdf_bytes, "generated_doc.pdf", "application/pdf")
        with d2:
            docx_bytes = create_docx(st.session_state.generated_content)
            st.download_button("Download Word", docx_bytes, "generated_doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # --- Chat to Modify ---
    with r_col2:
        st.subheader("💬 වෙනස්කම් කරන්න (Modify)")
        
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if chat_input := st.chat_input("Ex: තව ප්‍රශ්න 5ක් එකතු කරන්න..."):
            st.session_state.chat_history.append({"role": "user", "content": chat_input})
            
            # Contextual Update
            mod_client = Groq(api_key=api_key)
            mod_messages = [
                {"role": "system", "content": "You are a helpful assistant. The user wants to modify the text. Output the FULL updated text."},
                {"role": "assistant", "content": st.session_state.generated_content},
                {"role": "user", "content": chat_input}
            ]
            
            with st.spinner("Updating..."):
                resp = mod_client.chat.completions.create(messages=mod_messages, model="llama-3.3-70b-versatile")
                st.session_state.generated_content = resp.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": "Done!"})
                st.rerun()
