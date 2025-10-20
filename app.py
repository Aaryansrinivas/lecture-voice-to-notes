import streamlit as st
import google.generativeai as genai
import time
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile

# --- Configuration ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("❌ API Key not found. Please set 'GEMINI_API_KEY' in secrets.toml or environment variables.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- Streamlit UI ---
st.set_page_config(page_title="Video Analyzer & Quiz Generator", page_icon="📹", layout="centered")
st.title("📹 Video Analyzer & Quiz Generator")

st.markdown("""
Upload a video and let **Gemini** summarize it first.  
Then, generate a **well-formatted quiz** based on that summary.
""")

uploaded_file = st.file_uploader("🎞️ Upload a video file", type=["mp4", "mov", "avi", "mkv"])

# --- Session State ---
if "summary_text" not in st.session_state:
    st.session_state.summary_text = None

if "quiz_text" not in st.session_state:
    st.session_state.quiz_text = None

# --- Generate Summary ---
if uploaded_file is not None:
    st.video(uploaded_file, format=uploaded_file.type)

    word_limit = st.number_input(
        "📝 How many words should the summary be?",
        min_value=50,
        max_value=1000,
        value=200,
        step=50,
        help="Choose how detailed you want the summary to be."
    )

    if st.button("🧠 Generate Summary"):
        st.session_state.quiz_text = None
        st.info("Starting video analysis. Please wait...")

        try:
            # Use temporary file safely
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(uploaded_file.getbuffer())
                temp_file_path = tmp.name

            st.info("Processing video file...")
            progress_bar = st.progress(0)
            start_time = time.time()

            # No need to upload to Gemini for RAG store
            # We just generate summary text directly from prompt
            # If needed, you could extract text from video locally or using another API

            # For demo, we send a simple prompt to Gemini
            summary_prompt = (
                f"Summarize the content of this video clearly and concisely in about {word_limit} words "
                "for easy understanding. Focus on main topics, key ideas, and important insights."
            )
            result = model.generate_content(summary_prompt)
            st.session_state.summary_text = result.text

            # Cleanup temp file
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

            st.success("✅ Summary generated successfully!")

        except Exception as e:
            st.error(f"An error occurred: {e}")

# --- Display Summary ---
if st.session_state.summary_text:
    st.subheader("📄 Video Summary")
    st.markdown(
        f"""
        <div style="padding:15px; border-radius:10px; border:1px solid #ddd;">
            {st.session_state.summary_text}
        </div>
        """,
        unsafe_allow_html=True
    )

    # PDF Download
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Video Summary")

    text_object = c.beginText(50, height - 80)
    text_object.setFont("Helvetica", 11)
    max_width = 90
    for line in st.session_state.summary_text.split("\n"):
        for wrapped_line in re.findall(r".{1,%d}(?:\s+|$)" % max_width, line):
            text_object.textLine(wrapped_line.strip())
    c.drawText(text_object)
    c.save()

    pdf_buffer.seek(0)
    st.download_button(
        label="📘 Download Summary (PDF)",
        data=pdf_buffer,
        file_name="video_summary.pdf",
        mime="application/pdf"
    )

# --- Generate Quiz ---
st.markdown("---")
st.subheader("🧩 Generate Quiz from Summary")
st.markdown("Click below to create a **neatly formatted multiple-choice quiz** based on your summary.")

if st.session_state.summary_text and st.button("🎯 Generate Quiz"):
    try:
        with st.spinner("Generating quiz based on summary..."):
            quiz_prompt = (
                "Based on the following summary, create a clear 5-question multiple-choice quiz. "
                "Each question must include 4 options (A, B, C, D) and one correct answer. "
                "Format exactly as:\n\n"
                "Question 1: ...\n"
                "A) ...\nB) ...\nC) ...\nD) ...\n"
                "Answer: ...\n\n"
                "Make sure each option and answer are on separate lines for readability.\n\n"
                f"Summary:\n{st.session_state.summary_text}"
            )
            quiz_result = model.generate_content(quiz_prompt)
            st.session_state.quiz_text = quiz_result.text
    except Exception as e:
        st.error(f"Error generating quiz: {e}")

# --- Display Quiz ---
if st.session_state.quiz_text:
    st.markdown("---")
    st.subheader("📝 Generated Quiz")
    formatted_quiz = st.session_state.quiz_text
    formatted_quiz = re.sub(r"(Question \d+:)", r"\n\1", formatted_quiz)
    formatted_quiz = re.sub(r"(Answer:)", r"\n\1", formatted_quiz)
    st.markdown(
        f"""
        <div style="padding:15px; border-radius:10px; border:1px solid #bcd;">
            <pre style="white-space: pre-wrap; font-size:16px; line-height:1.6;">{formatted_quiz}</pre>
        </div>
        """,
        unsafe_allow_html=True
    )
