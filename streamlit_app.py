import streamlit as st
import os
from groq import Groq
import pdfminer.high_level
import docx2txt
from PIL import Image
import pytesseract

# Page Config
st.set_page_config(page_title="O/L Question Generator", page_icon="📝")

st.title("📝 O/L Question Generator")
st.write("PDF, Word හෝ පින්තූර (Notes) අප්ලෝඩ් කර ප්‍රශ්න පත්‍ර සාදාගන්න.")

# Sidebar - API Key එක ලබා ගැනීම
with st.sidebar:
    st.header("Settings")
    # .env එකේ Key එක තියෙනවා නම් ඒක පාවිච්චි කරයි, නැත්නම් අතින් ගහන්න පුළුවන්
    default_key = "" 
    api_key = st.text_input("Enter Groq API Key (gsk_...):", value=default_key, type="password")
    
    if not api_key:
        st.warning("කරුණාකර Groq API Key එක ඇතුළත් කරන්න.")

# ෆයිල් එක අප්ලෝඩ් කිරීම
uploaded_file = st.file_uploader("ගොනුව තෝරන්න (PDF, DOCX, Image, TXT)", type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'])

def extract_text(file):
    try:
        ext = file.name.split('.')[-1].lower()
        if ext == 'pdf':
            return pdfminer.high_level.extract_text(file)
        elif ext == 'docx':
            return docx2txt.process(file)
        elif ext == 'txt':
            return file.read().decode('utf-8')
        elif ext in ['png', 'jpg', 'jpeg']:
            img = Image.open(file)
            # සිංහල සහ ඉංග්‍රීසි දෙකම කියවීමට උත්සාහ කරයි
            return pytesseract.image_to_string(img, lang='sin+eng')
    except Exception as e:
        st.error(f"ගොනුව කියවීමේදී දෝෂයක් ඇති විය: {e}")
    return ""

if uploaded_file and api_key:
    with st.spinner('ගොනුව කියවමින් පවතී...'):
        text = extract_text(uploaded_file)
        
    if text:
        st.success("ගොනුව කියවා අවසන්!")
        
        if st.button("ප්‍රශ්න පත්‍රය සාදන්න"):
            client = Groq(api_key=api_key)
            with st.spinner('AI මගින් ප්‍රශ්න සාදමින් පවතී...'):
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[{
                            "role": "system",
                            "content": "You are a professional teacher. Based on the text, generate 10 multiple choice questions (MCQs) in Sinhala. Each question should have 4 options and the correct answer."
                        }, {
                            "role": "user",
                            "content": text[:12000] # අකුරු සීමාව
                        }],
                        model="llama-3.3-70b-versatile",
                    )
                    st.subheader("හදපු ප්‍රශ්න පත්‍රය මෙන්න:")
                    st.write(chat_completion.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI දෝෂයක්: {e}")