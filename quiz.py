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
# GPT-Frage generieren
# -----------------------------
def generate_question_gpt(paragraph, category, retries=3, method_focus=False):
    # Grundgerüst des Prüfungsstils
    guidelines = """
Ziel der Fragen:
Die Fragen dienen der Vorbereitung auf das Fachgespräch und die Verteidigung der Projektarbeit.

Jede Frage soll prüfen:
- Das Verständnis der Inhalte und Zusammenhänge der eigenen Projektarbeit
- Die Begründung für die Auswahl und Anwendung der verwendeten Methoden
- Das Verständnis der Funktionsweise dieser Methoden
- Das Wissen über alternative Methoden (falls relevant)
- Die Fähigkeit, Auswirkungen veränderter Rahmenbedingungen oder Zahlen auf das Ergebnis zu beurteilen
- Das Erkennen alternativer Szenarien und deren Einfluss auf die getroffene Empfehlung
- Fachkompetenz, Methodenkompetenz, Analysefähigkeit und strategisches Denken
"""

    if method_focus:
        # Nur für die 1 spezielle Methodenfrage pro Quiz
        focus_text = """
Erstelle **eine einzige methodenkritische Frage**, die sich darauf konzentriert:
- Welche alternativen Methoden zur im Absatz genannten Methode existieren könnten,
- wie diese funktionieren,
- und wie sich ihre Anwendung auf das Projektergebnis ausgewirkt hätte.
"""
    else:
        # Standardfragen unverändert
        focus_text = """
Erstelle eine **kritische, komplexe und prüfungsnahe Frage**, die Verständnis, Analyse oder Transfer prüft.
"""

    prompt = f"""
Du bist ein erfahrener Prüfer der IHK, der anspruchsvolle Fragen zur Projektarbeit stellt.

Kategorie: {category}
Absatz:
{paragraph}

{guidelines}
{focus_text}

Gib die Antwort ausschließlich im gültigen JSON-Format zurück:
{{
  "question": "Frage als vollständiger Satz",
  "choices": [
    "Antwort A als vollständiger Satz",
    "Antwort B als vollständiger Satz",
    "Antwort C als vollständiger Satz",
    "Antwort D als vollständiger Satz"
  ],
  "answer": "Eine der vier Antworten exakt wiederholt",
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
            # JSON-Parsing robust
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}") + 1
                data = json.loads(content[start:end])
            # Nachbearbeitung
            data["question"] = data["question"].strip()
            data["choices"] = [c.strip() for c in data["choices"]]
            data["answer"] = data["answer"].strip()
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

    # 1 garantierte methodenkritische Frage
    method_paragraphs = [
        p for p in paragraphs if any(x in p.lower() for x in ["methode", "analyse", "fmea", "swot", "bewertung"])
    ]
    if method_paragraphs:
        paragraph = random.choice(method_paragraphs)
        parts = split_paragraph(paragraph, max_length=300)
        q = generate_question_gpt(random.choice(parts), random.choice(categories), method_focus=True)
        if q:
            quiz.append(q)

    # Rest unverändert (Standardfragen)
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

    return quiz[:questions_total]

# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Quiz", layout="centered")
    st.title("📘 Projektarbeit Quiz")
    st.write("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen — wie im echten Fachgespräch!")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (DOCX)", type="docx")
    categories = ["fachwissen", "methoden", "analyse", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        if st.button("🔄 Neues Quiz generieren"):
            st.info("Quiz wird generiert, bitte warten...")
            quiz = generate_quiz(paragraphs, categories, questions_total=10)
            st.session_state.quiz = quiz
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.stats = {cat: {"correct": 0, "total": 0} for cat in categories}
            st.success("✅ Quiz erfolgreich generiert!")

    if "quiz" in st.session_state and st.session_state.quiz:
        quiz = st.session_state.quiz
        i = st.session_state.current_index
        q = quiz[i]
        st.subheader(f"Frage {i+1} ({q['category'].capitalize()})")
        st.write(q["question"])
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