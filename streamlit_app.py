import streamlit as st
import os
import google.generativeai as genai
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

# --- Page Config ---
st.set_page_config(page_title="AI Doc Genie (Gemini)", page_icon="🧞‍♂️", layout="wide")

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
                img = ImageOps.grayscale(img)
                img = ImageEnhance.Contrast(img).enhance(2.5)
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
        if line.startswith("#") or "
