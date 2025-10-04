import os
import json
import random
import time
import openai
import streamlit as st
from docx import Document
from io import BytesIO

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
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            # Nachbearbeitung
            data["question"] = data["question"].replace("...", "").strip()
            data["answer"] = data["answer"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
            random.shuffle(data["choices"])  # zufällige Reihenfolge
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
    st.set_page_config(page_title="📘 Projektarbeit Quiz", layout="centered")

    # CSS: neutrales Design (verhindert weißen Text auf Weiß im Dark Mode)
    st.markdown("""
        <style>
            body, .stApp {
                background-color: #f9f9f9 !important;
                color: #000000 !important;
            }
            .stRadio > div {
                background-color: #ffffff;
                padding: 10px;
                border-radius: 10px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .question-card {
                background: white;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .stButton>button {
                border-radius: 10px;
                background-color: #2b65ec;
                color: white;
                font-weight: 600;
                padding: 8px 20px;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("📘 Projektarbeit Quiz")
    st.caption("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen!")

    uploaded_file = st.file_uploader("📄 Projektarbeit (DOCX) hochladen", type="docx")
    categories = ["fachwissen", "methoden", "analyse", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        if "quiz" not in st.session_state:
            st.session_state.quiz = generate_quiz(paragraphs, categories, questions_total=10)
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.answers = []

        quiz = st.session_state.quiz
        current_index = st.session_state.current_index
        question = quiz[current_index]

        st.markdown(f"#### Frage {current_index+1} von {len(quiz)} ({question['category']})")
        with st.container():
            st.markdown(f"<div class='question-card'><b>{question['question']}</b></div>", unsafe_allow_html=True)

            choice = st.radio("Antwort auswählen:", question["choices"], key=f"choice_{current_index}")

            if st.button("Antwort bestätigen"):
                if choice == question["answer"]:
                    st.success("✅ Richtig!")
                    st.session_state.score += 1
                else:
                    st.error(f"❌ Falsch! Richtige Antwort: {question['answer']}")
                st.session_state.answers.append({"frage": question["question"], "richtig": choice == question["answer"]})
                time.sleep(0.5)
                if st.session_state.current_index < len(quiz) - 1:
                    st.session_state.current_index += 1
                    st.experimental_rerun()
                else:
                    st.session_state.show_results = True
                    st.experimental_rerun()

        # Ergebnisse am Ende anzeigen
        if "show_results" in st.session_state and st.session_state.show_results:
            st.subheader("📊 Ergebnisse")
            st.write(f"Du hast **{st.session_state.score} von {len(quiz)}** Fragen richtig beantwortet.")

            # Kategorienaustellung
            category_scores = {}
            for a, q in zip(st.session_state.answers, quiz):
                cat = q["category"]
                if cat not in category_scores:
                    category_scores[cat] = [0, 0]
                category_scores[cat][1] += 1
                if a["richtig"]:
                    category_scores[cat][0] += 1

            for cat, (richtig, gesamt) in category_scores.items():
                st.write(f"**{cat.capitalize()}**: {richtig}/{gesamt}")

            if st.button("🔁 Neues Quiz starten"):
                for key in ["quiz", "current_index", "score", "answers", "show_results"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()


if __name__ == "__main__":
    main()