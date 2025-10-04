import os
import json
import random
import time
import openai
import streamlit as st
from docx import Document

# -----------------------------
# OPENAI API Key
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("Bitte setze deinen OpenAI API Key als Umgebungsvariable OPENAI_API_KEY")
    st.stop()

# -----------------------------
# DOCX einlesen
# -----------------------------
def load_paragraphs(docx_path, min_length=30):
    if not os.path.exists(docx_path):
        st.error(f"Datei {docx_path} nicht gefunden!")
        st.stop()
    doc = Document(docx_path)
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
            # Nachbearbeitung: "..." entfernen
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
def generate_quiz(paragraphs, categories, questions_total=5):
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
    st.title("📘 Projektarbeit Quiz")
    st.write("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen!")

    docx_path = "Projektarbeit.docx"
    paragraphs = load_paragraphs(docx_path)
    categories = ["fachwissen","methoden","analyse","kritik","transfer"]

    if "quiz" not in st.session_state:
        st.session_state.quiz = []

    if st.button("🔄 Neues Quiz generieren"):
        st.info("Quiz wird generiert, bitte warten...")
        quiz = generate_quiz(paragraphs, categories, questions_total=5)
        st.session_state.quiz = quiz
        st.success("Quiz generiert!")

    if st.session_state.quiz:
        quiz = st.session_state.quiz
        score = 0
        for i, q in enumerate(quiz, 1):
            st.subheader(f"Frage {i} ({q['category']})")
            st.write(q["question"])
            choice = st.radio("Antwort auswählen:", q["choices"], key=f"q{i}")
            if st.button(f"Antwort bestätigen {i}", key=f"btn{i}"):
                if choice == q["answer"]:
                    st.success("✅ Richtig!")
                    score += 1
                else:
                    st.error(f"❌ Falsch! Richtige Antwort: {q['answer']}")

        st.info(f"Dein aktueller Score: {score}/{len(quiz)}")

if __name__ == "__main__":
    main()
