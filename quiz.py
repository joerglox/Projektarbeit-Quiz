import os
import json
import random
import time
import openai
import streamlit as st
from docx import Document
from io import BytesIO

# -------------------------------------------------
# 🔑 OPENAI API Key
# -------------------------------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("❌ Kein OpenAI API Key gefunden! Bitte setze OPENAI_API_KEY als Umgebungsvariable oder in Streamlit Secrets.")
    st.stop()

# -------------------------------------------------
# 📄 DOCX einlesen
# -------------------------------------------------
def load_paragraphs_from_file(file, min_length=50):
    """Lädt Absätze aus einer DOCX-Datei, filtert leere und zu kurze Passagen."""
    doc = Document(file)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return [p for p in paragraphs if len(p) > min_length]

# -------------------------------------------------
# ✂️ Absatz splitten
# -------------------------------------------------
def split_paragraph(paragraph, max_length=400):
    words = paragraph.split()
    parts, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_length:
            current += (" " + word) if current else word
        else:
            parts.append(current)
            current = word
    if current:
        parts.append(current)
    return parts

# -------------------------------------------------
# 🧭 Themen aus der Arbeit
# -------------------------------------------------
topics = [
    "Prozessflussanalyse",
    "FMEA",
    "Know-how- und Technologieerhalt",
    "Make-or-Buy Kostenvergleich",
    "Szenarioanalyse",
    "Nutzwertanalyse",
    "SWOT-Analyse",
    "Abbildung",
    "Tabelle",
    "Anhang"
]

# -------------------------------------------------
# 🔀 Antworten mischen
# -------------------------------------------------
def shuffle_choices(q):
    """Mische die Antwortmöglichkeiten und erhalte die richtige Antwort korrekt."""
    choices = q["choices"]
    correct = q["answer"]
    random.shuffle(choices)
    q["choices"] = choices
    q["answer"] = correct
    return q

# -------------------------------------------------
# 🧠 GPT-Frage für Navigationswissen generieren
# -------------------------------------------------
def generate_navigation_question(paragraph, category, topics, retries=3):
    """Erstellt eine Navigationsfrage: Wo in der Arbeit steht etwas (Kapitel, Seite, Anhang, Abbildung, Tabelle)?"""
    prompt = f"""
Erstelle eine Navigationsfrage, die prüft, ob jemand weiß, wo sich ein bestimmtes Thema
in seiner Projektarbeit befindet (Kapitel, Seite, Anhang, Abbildung oder Tabelle).

Die Frage soll **nicht** den Inhalt abfragen, sondern nur das **Auffinden im Dokument**.
Die Themen stammen aus einer Projektarbeit über Make-or-Buy-Entscheidungen
in der biopharmazeutischen Produktion.

Textausschnitt:
{paragraph}

Wähle zufällig einen Fragetyp:
1) Kapitel + Seite
2) Kapitel + Anhang
3) Kapitel + Abbildung
4) Kapitel + Tabelle
5) Abbildung + Kapitel

Erstelle die Frage abwechslungsreich, mit vier Antwortmöglichkeiten (A–D),
von denen genau eine korrekt ist. Gib die Antwort im folgenden JSON-Format zurück:

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
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
            )
            content = response.choices[0].message.content.strip()
            start, end = content.find("{"), content.rfind("}") + 1
            data = json.loads(content[start:end])
            data["question"] = data["question"].strip()
            data["choices"] = [c.strip() for c in data["choices"]]
            data["answer"] = data["answer"].strip()
            data["category"] = category
            return shuffle_choices(data)
        except Exception:
            time.sleep(1)
    return None

# -------------------------------------------------
# 🧩 Quiz generieren
# -------------------------------------------------
def generate_quiz(paragraphs, categories, topics, questions_total=10):
    quiz = []
    while len(quiz) < questions_total:
        category = random.choice(categories)
        paragraph = random.choice(paragraphs)
        parts = split_paragraph(paragraph, max_length=400)

        for part in parts:
            q = generate_navigation_question(part, category, topics)
            if q:
                quiz.append(q)
                if len(quiz) >= questions_total:
                    break
        if len(quiz) >= questions_total:
            break
    return quiz

# -------------------------------------------------
# 🎮 Streamlit App
# -------------------------------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Navigationsquiz", layout="centered")

    st.markdown("""
    <style>
    body, .main {
        background-color: #0e1117;
        color: #f0f2f6;
        font-family: 'Inter', sans-serif;
    }
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        padding: 12px;
        color: white;
        background: linear-gradient(90deg, #007AFF, #00C6FF);
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        background: linear-gradient(90deg, #00C6FF, #007AFF);
    }
    .question-card {
        background: rgba(255,255,255,0.05);
        padding: 20px;
        border-radius: 15px;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🧭 Navigationsquiz zur Projektarbeit")
    st.caption("Teste, ob du dich in deiner Arbeit perfekt zurechtfindest – Kapitel, Seiten, Abbildungen & Anhänge.")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (DOCX)", type="docx")
    categories = ["strukturwissen", "verortung", "abbildungen", "tabellen", "anhang"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        st.info(f"📚 Themen in der Arbeit: {', '.join(topics)}")

        if st.button("🎯 Quiz starten"):
            st.info("Quiz wird erstellt... bitte warten ⏳")
            quiz = generate_quiz(paragraphs, categories, topics, questions_total=10)
            st.session_state.quiz = quiz
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.stats = {cat: {"correct": 0, "total": 0} for cat in categories}
            st.success("✅ Quiz erfolgreich erstellt!")

    if st.session_state.get("quiz"):
        quiz = st.session_state.quiz
        i = st.session_state.current_index
        q = quiz[i]

        st.markdown(f"<div class='question-card'><h4>Frage {i+1} ({q['category'].capitalize()})</h4><p>{q['question']}</p></div>", unsafe_allow_html=True)
        choice = st.radio("Antwort auswählen:", q["choices"], key=f"q{i}")

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
                st.write(f"**Gesamtscore: {st.session_state.score}/{len(quiz)} ({round((st.session_state.score/len(quiz))*100)}%)**")

                st.markdown("### 📊 Kategorie-Statistik")
                for cat, stats in st.session_state.stats.items():
                    total, correct = stats["total"], stats["correct"]
                    if total > 0:
                        st.write(f"**{cat.capitalize()}**: {correct}/{total} richtig")

if __name__ == "__main__":
    main()
