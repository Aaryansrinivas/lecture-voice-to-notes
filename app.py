import streamlit as st
import google.generativeai as genai
import time
import os
from io import BytesIO
import re
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- Configuration ---

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("API Key not found. Please set the 'GEMINI_API_KEY' in st.secrets or as an environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- Streamlit UI ---

st.set_page_config(page_title="Video Analyzer & Quiz Generator", page_icon="📹", layout="centered")

st.title("📹 Video Analyzer & Quiz Generator")
st.markdown(
    """
    Upload your video 
    """
)

uploaded_file = st.file_uploader("🎞️ Upload a video file", type=["mp4", "mov", "avi", "mkv"])

# --- Session State Setup ---
if "summary_text" not in st.session_state:
    st.session_state.summary_text = None
if "quiz_text" not in st.session_state:
    st.session_state.quiz_text = None

# --- Generate Summary ---
if uploaded_file is not None:
    st.video(uploaded_file, format=uploaded_file.type)

    # Ask user for desired word count
    word_limit = st.number_input(
        "📝 How many words should the summary be?", 
        min_value=50, 
        max_value=1000, 
        value=200, 
        step=50,
        help="Choose how detailed you want the summary to be."
    )

    if st.button("🧠 Generate Summary"):
        st.session_state.quiz_text = None  # Reset quiz if new summary generated
        st.info("Starting video analysis. Please wait...")

        try:
            temp_file_path = f"temp_upload_{uploaded_file.name}"
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner("📤 Uploading video to Gemini..."):
                myfile = genai.upload_file(path=temp_file_path)
                st.success(f"✅ File uploaded successfully: `{myfile.name}`")

            st.info("Processing video file...")
            progress_bar = st.progress(0)
            start_time = time.time()

            while myfile.state.name == "PROCESSING":
                time.sleep(5)
                myfile = genai.get_file(myfile.name)
                elapsed = time.time() - start_time
                progress = min(int(elapsed / 300 * 100), 99)
                progress_bar.progress(progress, text="Processing video...")
                if elapsed > 300:
                    st.error("⏱️ Processing timed out. Try a smaller video.")
                    genai.delete_file(myfile.name)
                    os.remove(temp_file_path)
                    st.stop()

            progress_bar.progress(100, text="✅ Processing complete!")

            if myfile.state.name == "FAILED":
                st.error("❌ Video processing failed.")
                genai.delete_file(myfile.name)
                os.remove(temp_file_path)
                st.stop()

            # Generate Summary with word limit
            with st.spinner(f"🧩 Generating summary (~{word_limit} words)..."):
                summary_prompt = (
                    f"Summarize the content of this video clearly and concisely in about {word_limit} words "
                    f"for easy understanding. Focus on main topics, key ideas, and important insights."
                )
                result = model.generate_content([myfile, summary_prompt])
                st.session_state.summary_text = result.text

            genai.delete_file(myfile.name)
            os.remove(temp_file_path)
            st.success("✅ Summary generated successfully!")

        except Exception as e:
            st.error(f"An error occurred: {e}")
            try:
                if 'myfile' in locals():
                    genai.delete_file(myfile.name)
            except Exception:
                pass
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

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

    # --- PDF Download Option Only ---
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Video Summary")

    # Body text (auto-wrap long lines)
    text_object = c.beginText(50, height - 80)
    text_object.setFont("Helvetica", 11)
    max_width = 90  # wrap lines to fit the page width
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

    # --- Generate Quiz Button ---
    st.markdown("---")
    st.subheader("🧩 Generate Quiz from Summary")
    st.markdown("Click below to create a **neatly formatted multiple-choice quiz** based on your summary.")

    if st.button("🎯 Generate Quiz"):
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

    # Clean & format quiz for better spacing
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

    
