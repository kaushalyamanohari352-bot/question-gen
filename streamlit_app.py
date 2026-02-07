import streamlit as st
import os
from groq import Groq
import pdfminer.high_level
import docx2txt
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

st.set_page_config(page_title="SL Question Gen", page_icon="📝")

st.title("📝 Sri Lankan Standard Question Generator")
st.write("ලංකාවේ විෂය නිර්දේශයන්ට අනුකූලව නිවැරදි සිංහල පාරිභාෂික ශබ්ද සහිතව ප්‍රශ්න සාදන්න.")

# Sidebar Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Groq API Key:", type="password")

uploaded_file = st.file_uploader("ගොනුව තෝරන්න (Image/PDF/Docs)", type=['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'])

def extract_text(file):
    ext = file.name.split('.')[-1].lower()
    if ext == 'pdf': return pdfminer.high_level.extract_text(file)
    elif ext == 'docx': return docx2txt.process(file)
    elif ext == 'txt': return file.read().decode('utf-8')
    elif ext in ['png', 'jpg', 'jpeg']:
        img = Image.open(file)
        # වඩාත් පැහැදිලි සිංහල OCR සඳහා පින්තූරය සකස් කිරීම
        img = ImageOps.grayscale(img)
        img = ImageEnhance.Contrast(img).enhance(2.5)
        return pytesseract.image_to_string(img, lang='sin+eng', config=r'--oem 3 --psm 6')
    return ""

# AI එකට ලබා දෙන පොදු ලාංකීය අධ්‍යාපන උපදෙස්
SL_CONTEXT_PROMPT = """
You are a highly experienced Sri Lankan educator specialized in creating O/L and A/L examination papers.
Rules for Sinhala Language:
1. Use 'Standard Unicode Sinhala' only.
2. Follow the terminology used by the National Institute of Education (NIE) Sri Lanka.
3. IMPORTANT: If the input text is from an OCR (which might have broken Sinhala characters), use your contextual knowledge of Sri Lankan subjects to fix and interpret the meaning.
4. Avoid literal Google translations. Use formal Sinhala (e.g., instead of 'පොතේ නම' use 'ග්‍රන්ථ නාමය', instead of 'ලකුණු' use 'නිර්ණායක' if applicable).
5. For Mathematical, Scientific, and Legal terms, use the exact Sinhala terms used in Sri Lankan schools.
"""

if uploaded_file and api_key:
    text = extract_text(uploaded_file)
    if len(text.strip()) > 10:
        st.success("ගොනුව කියවා අවසන්!")
        if st.button("ප්‍රශ්න පත්‍රය සාදන්න"):
            client = Groq(api_key=api_key)
            with st.spinner('ලාංකීය ප්‍රමිතීන්ට අනුව ප්‍රශ්න සාදමින් පවතී...'):
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[{
                            "role": "system",
                            "content": SL_CONTEXT_PROMPT
                        }, {
                            "role": "user",
                            "content": f"Generate 10 MCQs in Sinhala based on this text. Provide 4 options and the correct answer for each: \n\n {text[:12000]}"
                        }],
                        model="llama-3.3-70b-versatile",
                    )
                    st.subheader("හදපු ප්‍රශ්න පත්‍රය මෙන්න:")
                    st.write(chat_completion.choices[0].message.content)
                except Exception as e:
                    st.error(f"Error: {e}")
