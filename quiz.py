import os
import json
import random
import time
import openai
import streamlit as st
from docx import Document
from io import BytesIO

# -----------------------------
# OpenAI API Key
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
def generate_quiz(paragraphs, categories, questions_total=10):
    quiz = []
    used_categories = set()

    while len(quiz) < questions_total:
        category = random.choice(categories)
        paragraph = random.choice(paragraphs)
        parts = split_paragraph(paragraph, max_length=300)

        for part in parts:
            q = generate_question_gpt(part, category)
            if q:
                quiz.append(q)
                used_categories.add(category)
                if len(quiz) >= questions_total:
                    break
        if len(used_categories) == len(categories) and len(quiz) >= questions_total:
            break
    return quiz

# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Quiz", layout="centered")

    # Style für Dark/Light Mode
    st.markdown("""
        <style>
        .main {
            background-color: var(--background-color);
            color: var(--text-color);
            font-family: 'Helvetica Neue', sans-serif;
        }
        div[data-testid="stRadio"] > div {
            background: rgba(255, 255, 255, 0.05);
            padding: 12px 16px;
            border-radius: 10px;
        }
        .stButton > button {
            width: 100%;
            border-radius: 10px;
            padding: 10px;
            color: white;
            background: linear-gradient(90deg, #3a7bd5, #00d2ff);
            border: none;
            font-weight: bold;
        }
        .stButton > button:hover {
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
        }
        .question-card {
            background-color: rgba(240, 240, 240, 0.1);
            padding: 20px;
            border-radius: 15px;
            margin-top: 15px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("📘 Projektarbeit Quiz")
    st.write("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen!")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (DOCX)", type="docx")
    categories = ["fachwissen", "methoden", "analyse", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        if "quiz" not in st.session_state:
            st.session_state.quiz = []

        if st.button("🔄 Neues Quiz generieren"):
            st.info("Quiz wird generiert, bitte warten...")
            quiz = generate_quiz(paragraphs, categories, questions_total=10)
            st.session_state.quiz = quiz
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.stats = {cat: {"correct": 0, "total": 0} for cat in categories}
            st.success("✅ Quiz erfolgreich generiert!")

        if st.session_state.get("quiz"):
            quiz = st.session_state.quiz
            i = st.session_state.current_index
            q = quiz[i]
            st.markdown(f"<div class='question-card'><h4>Frage {i+1} ({q['category'].capitalize()})</h4><p>{q['question']}</p></div>", unsafe_allow_html=True)
            choice = st.radio("Wähle deine Antwort:", q["choices"], key=f"q{i}")

            if st.button("Antwort bestätigen"):
                cat = q["category"]
                st.session_state.stats[cat]["total"] += 1
                if choice == q["answer"]:
                    st.success("✅ Richtig!")
                    st.session_state.score += 1
                    st.session_state.stats[cat]["correct"] += 1
                else:
                    st.error(f"❌ Falsch! Richtige Antwort: {q['answer']}")

                time.sleep(1)
                if i + 1 < len(quiz):
                    st.session_state.current_index += 1
                    st.rerun()
                else:
                    st.balloons()
                    st.subheader("🏁 Quiz abgeschlossen!")
                    st.write(f"Dein Gesamtscore: **{st.session_state.score}/{len(quiz)}**")

                    st.markdown("### 📊 Kategorie-Statistik:")
                    for cat, stats in st.session_state.stats.items():
                        total = stats["total"]
                        correct = stats["correct"]
                        if total > 0:
                            st.write(f"**{cat.capitalize()}**: {correct}/{total} richtig")

if __name__ == "__main__":
    main()