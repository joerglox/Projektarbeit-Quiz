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
    st.error("❌ Kein OpenAI API Key gefunden! Bitte setze OPENAI_API_KEY in den Streamlit Secrets oder als Umgebungsvariable.")
    st.stop()

# -----------------------------
# DOCX einlesen
# -----------------------------
def load_paragraphs_from_file(file, min_length=30):
    """Lädt Absätze aus einer DOCX-Datei, filtert leere und zu kurze Passagen."""
    doc = Document(file)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return [p for p in paragraphs if len(p) > min_length]

# -----------------------------
# Absatz splitten
# -----------------------------
def split_paragraph(paragraph, max_length=300):
    """Teilt lange Absätze in mehrere Blöcke."""
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

# -----------------------------
# GPT-Frage generieren (mit Methodenfilter)
# -----------------------------
def generate_question_gpt(paragraph, category, methods_used=None, retries=3):
    """Erstellt eine hochwertige, prüfungsnahe Frage basierend auf einem Absatz."""
    
    methods_used_text = ", ".join(methods_used) if methods_used else "nicht angegeben"

    prompt = f"""
Du bist ein erfahrener Prüfer im Fachgespräch. Erstelle eine anspruchsvolle, realistische Frage aus folgendem Abschnitt einer Projektarbeit.

Kategorie: {category}
Absatz:
{paragraph}

In der Projektarbeit wurden folgende Methoden verwendet oder genannt:
{methods_used_text}

Die Frage darf sich **nur auf diese Methoden oder deren realistische Alternativen** beziehen.
Erfinde keine Methoden, die nicht im Text vorkommen.
Falls es sich anbietet, kannst du **eine (1) Frage pro Quiz** zu alternativen Methoden formulieren
(z. B. „Welche andere Methode hätte statt der FMEA verwendet werden können?“),
aber markiere nie eine tatsächlich genutzte Methode als falsch.

Die Fragen dienen zur Vorbereitung auf das Fachgespräch und sollen prüfen:
- Verständnis der Projektarbeit
- Warum Methoden eingesetzt wurden
- Wie sie funktionieren
- Welche Alternativen es gibt (falls relevant)
- Auswirkungen von Änderungen
- Fach-, Methoden-, Analyse- und strategische Kompetenz

Antworte im JSON-Format:
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
                max_tokens=650
            )
            content = response.choices[0].message.content.strip()

            # JSON-Bereich isolieren
            start, end = content.find("{"), content.rfind("}") + 1
            data = json.loads(content[start:end])

            # Nachbearbeitung
            data["question"] = data["question"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
            data["answer"] = data["answer"].replace("...", "").strip()
            data["category"] = category
            return data

        except Exception:
            time.sleep(1)
    return None

# -----------------------------
# Methoden in der Arbeit erkennen
# -----------------------------
def extract_methods(paragraphs):
    """Identifiziert häufig genannte Methoden aus dem Text."""
    methods = [
        "FMEA", "Nutzwertanalyse", "SWOT", "Ishikawa", "Pareto", "ABC-Analyse", "Risikoanalyse",
        "Prozessanalyse", "Kosten-Nutzen-Analyse", "Fehlerbaum", "5-Why", "Benchmarking"
    ]
    found = []
    text = " ".join(paragraphs).lower()
    for m in methods:
        if m.lower() in text:
            found.append(m)
    return found

# -----------------------------
# Quiz generieren
# -----------------------------
def generate_quiz(paragraphs, categories, methods_used, questions_total=10):
    quiz = []
    alt_question_added = False

    while len(quiz) < questions_total:
        category = random.choice(categories)
        paragraph = random.choice(paragraphs)
        parts = split_paragraph(paragraph, max_length=350)

        for part in parts:
            q = generate_question_gpt(part, category, methods_used)
            if q:
                # Mindestens eine Frage zur Methodenalternaive
                if not alt_question_added and any(word in q["question"].lower() for word in ["alternative", "statt", "andere methode"]):
                    alt_question_added = True
                quiz.append(q)
                if len(quiz) >= questions_total:
                    break
        if len(quiz) >= questions_total:
            break

    # Falls keine Alternativfrage erstellt wurde, gezielt eine hinzufügen
    if not alt_question_added and methods_used:
        m = random.choice(methods_used)
        q_alt = {
            "question": f"Welche alternative Methode hätte anstelle von {m} in der Projektarbeit eingesetzt werden können?",
            "choices": [
                f"Die SWOT-Analyse, um strategische Chancen und Risiken zu bewerten.",
                f"Die ABC-Analyse, um Prioritäten bei Einflussfaktoren zu setzen.",
                f"Die Monte-Carlo-Simulation, um Unsicherheiten quantitativ zu analysieren.",
                f"Die Nutzwertanalyse, um Entscheidungsoptionen zu bewerten."
            ],
            "answer": "Die Nutzwertanalyse, um Entscheidungsoptionen zu bewerten.",
            "category": "methoden"
        }
        quiz[random.randint(0, len(quiz) - 1)] = q_alt
    return quiz

# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Quiz", layout="centered")

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

    st.title("📘 Projektarbeit Quiz")
    st.caption("Lerne, verteidige, überzeuge — dein interaktives Fachgespräch-Training.")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (DOCX)", type="docx")
    categories = ["fachwissen", "methoden", "analyse", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        methods_used = extract_methods(paragraphs)
        st.info(f"🧩 Erkannte Methoden in der Arbeit: {', '.join(methods_used) if methods_used else 'Keine spezifischen Methoden erkannt'}")

        if st.button("🎯 Quiz generieren"):
            st.info("Quiz wird erstellt... bitte warten ⏳")
            quiz = generate_quiz(paragraphs, categories, methods_used, questions_total=10)
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
                st.write(f"**Gesamtscore: {st.session_state.score}/{len(quiz)}**")

                st.markdown("### 📊 Kategorie-Statistik")
                for cat, stats in st.session_state.stats.items():
                    total, correct = stats["total"], stats["correct"]
                    if total > 0:
                        st.write(f"**{cat.capitalize()}**: {correct}/{total} richtig")

if __name__ == "__main__":
    main()