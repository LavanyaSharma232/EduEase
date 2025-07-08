import streamlit as st
from PIL import Image
import os
import re
import json
import requests
import google.generativeai as genai
from faster_whisper import WhisperModel
from gtts import gTTS
import yt_dlp

st.set_page_config(
    page_title="EduEase",
    page_icon="📑",
    layout="wide"
)

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("Google AI API key not found. Please add it to your Streamlit secrets.", icon="🚨")
    st.stop()

def parse_quiz_from_json(notes_text: str) -> list:
    """Finds and parses the JSON quiz block from the notes text."""
    match = re.search(r"```json\s*([\s\S]+?)\s*```", notes_text)
    if not match:
        return []
    json_string = match.group(1)
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        st.warning("Could not parse quiz data from the AI's response.", icon="⚠️")
        return []

def generate_summary_image(summary_text: str):
    """Generates a single image based on the summary text using Stability AI."""
    api_key = st.secrets.get("STABILITY_API_KEY")
    if not api_key:
        return None
    try:
        response = requests.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            json={"text_prompts": [{"text": f"A clear, simple, educational diagram illustrating: {summary_text}. Minimalist, clean lines, white background."}], "samples": 1},
            timeout=45
        )
        response.raise_for_status()
        return response.json()["artifacts"][0]["base64"]
    except Exception:
        return None


def video_to_audio(video_URL: str) -> str:
    try:
        FFMPEG_PATH = "C:/ffmpeg/bin"
        if os.path.exists("Target_audio.mp3"):
            os.remove("Target_audio.mp3")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'Target_audio',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'ffmpeg_location': FFMPEG_PATH,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_URL, download=True)
            return info_dict.get('title', "Unknown Video Title")
    except Exception as e:
        st.error(f"Error downloading video: {e}", icon="🚫")
        st.stop()

def audio_to_text(audio_path: str) -> str:
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, beam_size=5)
        return "".join(segment.text for segment in segments)
    except Exception as e:
        st.error(f"Error during local transcription: {e}", icon="🎤")
        st.stop()

def generate_notes(text: str) -> str:
    """Generates notes using Google Gemini, asking for a quiz in JSON format."""
    system_prompt = """You are an expert educator for students with learning disabilities. Your task is to transform a video transcript into clear, simple study notes.

The notes must ALWAYS include these sections, formatted in Markdown with `##` for headings:
1.  ## Title: A creative and relevant title.
2.  ## Summary & Flowchart: A simple summary, followed by a text-based flowchart in a markdown code block.
3.  ## Key Takeaways: A bulleted list of the most important points.
4.  ## Mnemonics: A clever memory aid for a key fact.
5.  ## Quiz Yourself!: A short quiz. Format THIS SECTION ONLY as a valid JSON array of objects inside a json code block. Each object must have "question" and "answer" keys.
"""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    try:
        response = model.generate_content(system_prompt + "\n\nHere is the transcript:\n" + text)
        return response.text
    except Exception as e:
        st.error(f"Error generating notes with Google AI: {e}", icon="🤖")
        st.stop()

def text_to_audio(text: str, output_filename: str):
    """Converts text to an MP3 audio file."""
    try:
        cleaned_text = re.sub(r'[#*`]', '', text)
        tts = gTTS(text=cleaned_text, lang='en')
        tts.save(output_filename)
    except Exception as e:
        st.error(f"Error converting text to speech: {e}", icon="🔊")
        st.stop()

def app():
    with st.sidebar:
        image = Image.open("assets/images/EduEase-no-bg.png")
        st.image(image, use_column_width=True)
        st.header("Making Learning Accessible")
        st.markdown("Welcome to **Noteezy.AI**! Paste a YouTube link to get simple, multimodal study notes.")
        st.info("Created with ❤️ for a hackathon.", icon="🚀")

    st.title("Noteezy.AI 📑")
    st.write("Transform any educational YouTube video into simple notes with text, audio, visuals, and flashcards.")

    if "notes" not in st.session_state:
        st.session_state.notes = ""
    if "video_url" not in st.session_state:
        st.session_state.video_url = ""
    if "flashcards" not in st.session_state:
        st.session_state.flashcards = []
    if "current_card_index" not in st.session_state:
        st.session_state.current_card_index = 0

    video_URL = st.text_input("Paste the YouTube video URL here")

    if st.button("✨ Generate My Notes ✨", use_container_width=True):
        if video_URL:
            if video_URL != st.session_state.video_url:
                st.session_state.notes = ""
                st.session_state.flashcards = []
                st.session_state.current_card_index = 0
                st.session_state.video_url = video_URL
            
            with st.spinner('Hang tight! Our AI is working its magic... 🧙‍♂️'):
                video_to_audio(video_URL)
                transcript = audio_to_text("Target_audio.mp3")
                st.session_state.notes = generate_notes(transcript)
                st.session_state.flashcards = parse_quiz_from_json(st.session_state.notes)
                os.remove("Target_audio.mp3")
        else:
            st.warning("Oops! You forgot to paste a YouTube URL.", icon="🤔")

    if st.session_state.notes:
        notes = st.session_state.notes
        
        st.success("Notes generated successfully!", icon="✅")
        st.markdown("---")
        
        st.subheader("1. Video & Audio Notes")
        st.video(st.session_state.video_url)
        with st.spinner("Preparing audio..."):
            text_to_audio(notes, "notes_audio.mp3")
            st.audio("notes_audio.mp3")
            os.remove("notes_audio.mp3")

        st.subheader("2. Visual Summary")
        summary_text_match = re.search(r'##\s*Summary\s*&?\s*Flowchart\s*\n(.*?)\n', notes, re.DOTALL)
        if summary_text_match:
            with st.spinner("🎨 Creating a visual summary..."):
                image_data = generate_summary_image(summary_text_match.group(1))
            if image_data:
                st.image(image_data, caption="A visual for the main concept.", use_column_width=True)

        st.subheader("3. Your Study Notes")
        
        notes_without_quiz = notes.split("## Quiz Yourself!")[0]
        st.markdown(notes_without_quiz)
        
        if st.session_state.flashcards:
            flashcards = st.session_state.flashcards
            card_index = st.session_state.current_card_index
            
            st.markdown("---")
            st.subheader("🧠 Quiz Yourself!")
            st.markdown(f"**Flashcard {card_index + 1} of {len(flashcards)}**")
            
            question_data = flashcards[card_index]
            st.markdown(question_data['question'].replace('\\n', '\n\n'))
            
            with st.expander("🤔 Reveal Answer"):
                st.success(f"**Answer:** {question_data['answer']}")

            col1, col2, _ = st.columns([1, 1, 4])
            if col1.button("⬅️ Previous", use_container_width=True, disabled=(card_index <= 0)):
                st.session_state.current_card_index -= 1
                st.rerun()
            if col2.button("Next ➡️", use_container_width=True, disabled=(card_index >= len(flashcards) - 1)):
                st.session_state.current_card_index += 1
                st.rerun()

if __name__ == '__main__':
    app()