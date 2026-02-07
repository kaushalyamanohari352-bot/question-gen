import streamlit as st
import os
from groq import Groq
import pdfminer.high_level
import docx2txt
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

# Page Config
st.set_page_config(page_title="O/L Question Generator", page_icon="📝")

st.title("📝 O/L Question Generator (Improved)")
st.write("PDF, Word හෝ පින්තූර අප්ලෝඩ් කර පැහැදිලි සිංහල ප්‍රශ්න පත්‍ර සාදාගන්න.")

# Sidebar Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Groq API Key:", type="password")
    if not api_key:
        st.warning("කරුණාකර API Key එක ඇතුළත් කරන්න.")

uploaded_file = st.file_uploader("ගොනුව තෝරන්න", type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'])

def process_image(img):
    # පින්තූරය කළු-සුදු කර contrast වැඩි කිරීම (OCR වලට පහසු වීමට)
    img = ImageOps.grayscale(img)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img

def extract_text(file):
    ext = file.name.split('.')[-1].lower()
    if ext == 'pdf':
        return pdfminer.high_level.extract_text(file)
    elif ext == 'docx':
        return docx2txt.process(file)
    elif ext == 'txt':
        return file.read().decode('utf-8')
    elif ext in ['png', 'jpg', 'jpeg']:
        img = Image.open(file)
        img = process_image(img) # Image Pre-processing
        # Tesseract configuration for better Sinhala recognition
        custom_config = r'--oem 3 --psm 6'
        return pytesseract.image_to_string(img, lang='sin+eng', config=custom_config)
    return ""

if uploaded_file and api_key:
    with st.spinner('ගොනුව කියවමින් පවතී...'):
        text = extract_text(uploaded_file)
        
    if len(text.strip()) < 20:
        st.error("පින්තූරයේ අකුරු හඳුනාගැනීම අපහසුයි. කරුණාකර වඩාත් පැහැදිලි පින්තූරයක් ලබාදෙන්න.")
    else:
        st.success("ගොනුව සාර්ථකව කියවා අවසන්!")
        
        if st.button("ප්‍රශ්න පත්‍රය සාදන්න"):
            client = Groq(api_key=api_key)
            with st.spinner('AI මගින් සිංහල ප්‍රශ්න සාදමින් පවතී...'):
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[{
                            "role": "system",
                            "content": "You are a professional Sri Lankan teacher. Fix any OCR typos in the provided text. Generate 10 high-quality MCQs in clear Standard Unicode Sinhala. Provide 4 options and the correct answer for each."
                        }, {
                            "role": "user",
                            "content": text[:12000]
                        }],
                        model="llama-3.3-70b-versatile",
                    )
                    st.subheader("හදපු ප්‍රශ්න පත්‍රය මෙන්න:")
                    st.write(chat_completion.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI Error: {e}")
