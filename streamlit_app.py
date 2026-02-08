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

# Page Configuration
st.set_page_config(page_title="AI Smart Assistant", page_icon="🤖", layout="wide")

# Session State
if "generated_content" not in st.session_state:
    st.session_state.generated_content = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ සැකසුම් (Settings)")
    
    # API Key එක Secrets වලින් හෝ User Input එකෙන්
    if "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
        st.success("API Key Loaded securely!")
    else:
        api_key = st.text_input("Groq API Key:", type="password")
    
    mode = st.radio("ඔබට අවශ්‍ය සේවාව:", 
                    ["Paper Generator (ප්‍රශ්න පත්‍ර)", "Digitizer (ලියුම්/ලේඛන Type කිරීම)"])
    
    language = st.selectbox("භාෂාව:", ["Sinhala", "English"])
    
    st.info("💡 PDF සඳහා 'sinhala.ttf' ෆයිල් එක GitHub හි තිබිය යුතුය.")

# --- Functions ---

def register_fonts():
    # sinhala.ttf ෆයිල් එක තිබේදැයි බලයි
    if os.path.exists("sinhala.ttf"):
        try:
            pdfmetrics.registerFont(TTFont('Sinhala', 'sinhala.ttf'))
            return True
        except:
            return False
    return False

def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    font_loaded = register_fonts()
    
    if font_loaded:
        c.setFont("Sinhala", 12)
    else:
        c.setFont("Helvetica", 12)
        c.drawString(100, 800, "Warning: sinhala.ttf not found.")
    
    y = 750
    margin = 50
    width = 500
    
    for line in text.split('\n'):
        # සරල සිංහල Text Wrapping
        words = line.split()
        current_line = ""
        for word in words:
            if c.stringWidth(current_line + " " + word, "Sinhala" if font_loaded else "Helvetica") < width:
                current_line += " " + word
            else:
                c.drawString(margin, y, current_line)
                y -= 20
                current_line = word
                if y < 50:
                    c.showPage()
                    if font_loaded: c.setFont("Sinhala", 12)
                    y = 750
        c.drawString(margin, y, current_line)
        y -= 20
        if y < 50:
            c.showPage()
            if font_loaded: c.setFont("Sinhala", 12)
            y = 750
            
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

def extract_text_from_files(uploaded_files):
    combined_text = ""
    for file in uploaded_files:
        ext = file.name.split('.')[-1].lower()
        if ext == 'pdf':
            combined_text += pdfminer.high_level.extract_text(file) + "\n"
        elif ext == 'docx':
            combined_text += docx2txt.process(file) + "\n"
        elif ext == 'txt':
            combined_text += file.read().decode('utf-8') + "\n"
        elif ext in ['png', 'jpg', 'jpeg']:
            img = Image.open(file)
            img = ImageOps.grayscale(img)
            img = ImageEnhance.Contrast(img).enhance(2.5)
            text = pytesseract.image_to_string(img, lang='sin+eng', config='--oem 3 --psm 6')
            combined_text += text + "\n"
    return combined_text

# --- Main UI ---
st.title("🤖 AI Smart Office Assistant")

uploaded_files = st.file_uploader("ගොනු අප්ලෝඩ් කරන්න (PDF, Image, Docx)", 
                                accept_multiple_files=True, 
                                type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'])

if uploaded_files and api_key:
    if st.button("Proceed (ක්‍රියාත්මක කරන්න)"):
        with st.spinner("ගොනු කියවමින් පවතී..."):
            raw_text = extract_text_from_files(uploaded_files)
        
        system_prompt = ""
        if mode == "Paper Generator (ප්‍රශ්න පත්‍ර)":
            system_prompt = f"""
            You are an expert Sri Lankan exam setter. Language: {language}.
            Task: Create 10 MCQs. Fix any broken Sinhala characters from input.
            Use 'Standard Unicode Sinhala' only.
            """
        else: # Digitizer Mode
            system_prompt = f"""
            You are a professional secretary. Language: {language}.
            Task: Convert the messy input text into a clean, formatted document.
            Fix spelling/grammar. Make it look official.
            """

        client = Groq(api_key=api_key)
        
        with st.spinner("AI සිතමින් පවතී..."):
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": raw_text[:15000]}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                st.session_state.generated_content = chat_completion.choices[0].message.content
                st.session_state.chat_history = [] 
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- Result & Chat ---
if st.session_state.generated_content:
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📄 ප්‍රතිඵලය")
        st.text_area("Preview", value=st.session_state.generated_content, height=600)
        
        c1, c2 = st.columns(2)
        with c1:
            pdf_data = create_pdf(st.session_state.generated_content)
            st.download_button("Download PDF", data=pdf_data, file_name="output.pdf", mime="application/pdf")
        with c2:
            docx_data = create_docx(st.session_state.generated_content)
            st.download_button("Download Word Doc", data=docx_data, file_name="output.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with col2:
        st.subheader("💬 Chat to Modify")
        
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if user_input := st.chat_input("වෙනස්කම් කියන්න (Ex: තව ප්‍රශ්න 5ක් ඕනේ)..."):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            client = Groq(api_key=api_key)
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Update the content based on user request. Output ONLY the new content."},
                {"role": "assistant", "content": st.session_state.generated_content},
                {"role": "user", "content": user_input}
            ]
            
            with st.spinner("වෙනස් කරමින්..."):
                resp = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
                new_text = resp.choices[0].message.content
                st.session_state.generated_content = new_text
                st.session_state.chat_history.append({"role": "assistant", "content": "Done! Updated the content."})
                st.rerun()
