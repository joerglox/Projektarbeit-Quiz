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
    st.error("❌ Kein OpenAI API Key gefunden! Bitte setze OPENAI_API_KEY als Umgebungsvariable oder in Streamlit Secrets.")
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
# Methoden-Liste
# -----------------------------
methods_used = [
    "Prozessflussanalyse",
    "FMEA",
    "Know-how- und Technologieerhalt",
    "Make-or-Buy Kostenvergleich",
    "Szenarioanalyse",
    "Nutzwertanalyse",
    "SWOT-Analyse"
]

# -----------------------------
# Antworten mischen
# -----------------------------
def shuffle_choices(q):
    choices = q["choices"]
    correct = q["answer"]
    random.shuffle(choices)
    q["choices"] = choices
    q["answer"] = correct
    return q

# -----------------------------
# GPT-Frage generieren
# -----------------------------
def generate_question_gpt(paragraph, category, methods_used, retries=3):
    prompt = f"""
Du bist ein erfahrener Prüfer. Erstelle eine hochwertige Prüfungsfrage auf Basis des Absatzes:

Kategorie: {category}
Absatz:
{paragraph}

Verwendete Methoden in der Arbeit: {', '.join(methods_used)}

Die Frage soll prüfen:
- Verständnis der Projektarbeit
- Warum Methoden eingesetzt wurden
- Funktionsweise der Methoden
- Alternative Methoden
- Auswirkungen von Änderungen
- Fach-, Methoden-, Analyse- und strategische Kompetenz

Antwort im JSON-Format:
{{
  "question": "Frage als vollständiger Satz",
  "choices": ["Antwort A","Antwort B","Antwort C","Antwort D"],
  "answer": "Antwort A",
  "category": "{category}"
}}
Jede Antwortmöglichkeit muss ein vollständiger, klarer Satz sein.
"""
    for _ in range(retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=650
            )
            content = response.choices[0].message.content.strip()
            start, end = content.find("{"), content.rfind("}") + 1
            data = json.loads(content[start:end])
            data["question"] = data["question"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
            data["answer"] = data["answer"].replace("...", "").strip()
            data["category"] = category
            return shuffle_choices(data)
        except Exception:
            time.sleep(1)
    return None

# -----------------------------
# Quiz generieren mit 6/3/1-Verteilung und 1 Frage Alternativmethoden
# -----------------------------
def generate_quiz(paragraphs, categories, methods_used):
    quiz = []

    # Kapitel 4: Methoden → 6 Fragen
    method_paragraphs = [p for p in paragraphs if p.startswith("4.")]
    for _ in range(6):
        if not method_paragraphs: break
        para = random.choice(method_paragraphs)
        category = "methoden"
        q = generate_question_gpt(para, category, methods_used)
        if q: quiz.append(q)

    # Kapitel 5-6: Zusammenfassung/Empfehlung → 3 Fragen
    summary_paragraphs = [p for p in paragraphs if p.startswith("5.") or p.startswith("6.")]
    for _ in range(3):
        if not summary_paragraphs: break
        para = random.choice(summary_paragraphs)
        category = random.choice(["analyse","kritik","transfer"])
        q = generate_question_gpt(para, category, methods_used)
        if q: quiz.append(q)

    # Restliche Kapitel → 1 Frage
    other_paragraphs = [p for p in paragraphs if p not in method_paragraphs + summary_paragraphs]
    if other_paragraphs:
        para = random.choice(other_paragraphs)
        category = random.choice(categories)
        q = generate_question_gpt(para, category, methods_used)
        if q: quiz.append(q)

    # Sicherstellen: mindestens 1 Frage zu Alternativmethoden
    alt_indices = list(range(len(quiz)))
    random.shuffle(alt_indices)
    alt_inserted = False
    for idx in alt_indices:
        q = quiz[idx]
        if "alternative" not in q["question"].lower():
            m = random.choice(methods_used)
            alt_question = {
                "question": f"Welche alternative Methode hätte anstelle von {m} verwendet werden können?",
                "choices": [
                    f"SWOT-Analyse",
                    f"ABC-Analyse",
                    f"Monte-Carlo-Simulation",
                    f"Nutzwertanalyse"
                ],
                "answer": "Nutzwertanalyse",
                "category": "methoden"
            }
            quiz[idx] = shuffle_choices(alt_question)
            alt_inserted = True
            break
    if not alt_inserted:
        # Wenn zufällig keine ersetzt wurde, setze letzte Frage auf Alternativmethoden
        m = random.choice(methods_used)
        quiz[-1] = shuffle_choices({
            "question": f"Welche alternative Methode hätte anstelle von {m} verwendet werden können?",
            "choices": [
                f"SWOT-Analyse",
                f"ABC-Analyse",
                f"Monte-Carlo-Simulation",
                f"Nutzwertanalyse"
            ],
            "answer": "Nutzwertanalyse",
            "category": "methoden"
        })

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
    st.caption("Interaktives Fachgespräch-Training.")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (DOCX)", type="docx")
    categories = ["fachwissen", "methoden", "analyse", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        st.info(f"🧩 Methoden in der Arbeit: {', '.join(methods_used)}")

        if st.button("🎯 Quiz generieren"):
            st.info("Quiz wird erstellt... bitte warten ⏳")
            quiz = generate_quiz(paragraphs, categories, methods_used)
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