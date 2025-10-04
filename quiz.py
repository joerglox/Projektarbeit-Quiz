import os
import json
import random
import time
import openai
import streamlit as st
from docx import Document
from io import BytesIO
from pathlib import Path

# -----------------------------
# OPENAI API Key
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("Bitte setze deinen OpenAI API Key als Umgebungsvariable OPENAI_API_KEY")
    st.stop()

# -----------------------------
# Ordner für gespeicherte DOCX
# -----------------------------
STORAGE_DIR = Path(".streamlit_data")
STORAGE_DIR.mkdir(exist_ok=True)
SAVED_DOCX_PATH = STORAGE_DIR / "saved_projektarbeit.docx"

# -----------------------------
# DOCX einlesen
# -----------------------------
def load_paragraphs_from_file(file, min_length=30):
    doc = Document(file)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return [p for p in paragraphs if len(p) > min_length]

# -----------------------------
# Absatz splitten
# -----------------------------
def split_paragraph(paragraph, max_length=300):
    words = paragraph.split()
    parts = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_length:
            current += " " + word if current else word
        else:
            parts.append(current)
            current = word
    if current:
        parts.append(current)
    return parts

# -----------------------------
# GPT-Frage generieren
# -----------------------------
def generate_question_gpt(paragraph, category, retries=3):
    prompt = f"""
Du bist ein Quiz-Generator. Erstelle eine kritische Prüfungsfrage der Kategorie '{category}' aus folgendem Absatz:

{paragraph}

Die Frage soll prüfen:
- Verständnis der Projektarbeit
- Warum diese Methode eingesetzt wurde
- Funktionsweise der Methode
- Alternativen und deren Funktionsweise
- Auswirkungen von Rahmenbedingungsänderungen
- Szenarien, die zu anderen Empfehlungen führen könnten
- Fach-, Methoden-, Analyse- und strategische Kompetenz

Antwort im JSON-Format mit:
{{
"question": "Frage als vollständiger Satz",
"choices": ["Antwort A","Antwort B","Antwort C","Antwort D"],
"answer": "Antwort A",
"category": "{category}"
}}
"""
    for _ in range(retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":prompt}],
                max_tokens=600
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            data["question"] = data["question"].replace("...", "").strip()
            data["answer"] = data["answer"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
            data["category"] = category
            return data
        except Exception:
            time.sleep(1)
    return None

# -----------------------------
# Quiz generieren
# -----------------------------
def generate_quiz(paragraphs, categories, questions_total=10):
    quiz = []
    while len(quiz) < questions_total:
        paragraph = random.choice(paragraphs)
        category = random.choice(categories)
        parts = split_paragraph(paragraph, max_length=300)
        for part in parts:
            q = generate_question_gpt(part, category)
            if q:
                quiz.append(q)
            if len(quiz) >= questions_total:
                break
    return quiz

# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Quiz", page_icon="📘", layout="centered")
    st.title("📘 Projektarbeit Quiz")
    st.markdown("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen!")
    st.markdown("---")

    categories = ["fachwissen","methoden","analyse","kritik","transfer"]

    # -----------------------------
    # Hochgeladene Datei speichern und wiederverwenden
    # -----------------------------
    if "uploaded_docx" not in st.session_state:
        if SAVED_DOCX_PATH.exists():
            st.session_state.uploaded_docx = open(SAVED_DOCX_PATH, "rb").read()
        else:
            st.session_state.uploaded_docx = None

    uploaded_file = st.file_uploader("Projektarbeit (DOCX) hochladen", type="docx")
    if uploaded_file:
        with open(SAVED_DOCX_PATH, "wb") as f:
            f.write(uploaded_file.read())
        st.session_state.uploaded_docx = open(SAVED_DOCX_PATH, "rb").read()
        st.success("📄 Datei hochgeladen und gespeichert!")

    # -----------------------------
    # Quiz generieren
    # -----------------------------
    if st.session_state.uploaded_docx:
        paragraphs = load_paragraphs_from_file(BytesIO(st.session_state.uploaded_docx))
        if "quiz" not in st.session_state:
            st.session_state.quiz = []

        if st.button("🔄 Neues Quiz generieren"):
            st.info("⏳ Quiz wird generiert, bitte warten...")
            quiz = generate_quiz(paragraphs, categories, questions_total=10)
            st.session_state.quiz = quiz
            st.success("✅ Quiz generiert!")

        if st.session_state.quiz:
            quiz = st.session_state.quiz
            score = 0

            # Fortschrittsbalken oben
            progress_bar = st.progress(0)

            for i, q in enumerate(quiz, 1):
                with st.container():
                    st.markdown(f"### Frage {i} ({q['category']})")
                    st.markdown(f"<div style='background-color:#f9f9f9;padding:10px;border-radius:10px'>{q['question']}</div>", unsafe_allow_html=True)

                    choice = st.radio("Antwort auswählen:", q["choices"], key=f"q{i}")

                    if st.button(f"Antwort bestätigen {i}", key=f"btn{i}"):
                        if choice == q["answer"]:
                            st.success("✅ Richtig!")
                            score += 1
                        else:
                            st.error(f"❌ Falsch! Richtige Antwort: {q['answer']}")

                    progress_bar.progress(i / len(quiz))
                    st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("---")
            st.metric(label="Gesamt-Score", value=f"{score}/{len(quiz)}")

if __name__ == "__main__":
    main()