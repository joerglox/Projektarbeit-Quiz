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
def generate_question_gpt(paragraph, category, retries=3):
    guidelines = """
Ziel der Fragen:
Die Fragen dienen der Vorbereitung auf das Fachgespräch und die Verteidigung der Projektarbeit.

Jede Frage soll prüfen:
- Verständnis der Projektarbeit
- Warum die verwendeten Methoden eingesetzt wurden
- Funktionsweise der Methoden
- Alternative Methoden und deren Funktionsweise
- Auswirkungen von Änderungen der Rahmenbedingungen oder Zahlen
- Szenarien, die zu anderen Empfehlungen führen
- Fachkompetenz, Methodenkompetenz, Analysefähigkeit, strategisches Denken
- Verständnis komplexer Sachverhalte
"""

    prompt = f"""
Du bist ein Prüfer, der hochwertige Prüfungsfragen erstellt.
Kategorie: {category}
Absatz:
{paragraph}

{guidelines}

Antwort im JSON-Format:
{{
"question": "Frage als vollständiger Satz",
"choices": ["Antwort A","Antwort B","Antwort C","Antwort D"],
"answer": "Antwort A",
"category": "{category}"
}}
Jede Antwortmöglichkeit muss ein vollständiger Satz sein.
"""

    for _ in range(retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600
            )
            content = response.choices[0].message.content.strip()
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}") + 1
                data = json.loads(content[start:end])
            # Nachbearbeitung
            data["question"] = data["question"].replace("...", "").strip()
            data["answer"] = data["answer"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
            data["category"] = category
            return data
        except Exception:
            time.sleep(1)
    return None

# -----------------------------
# Absätze nach Kapiteln sortieren
# -----------------------------
chapter_keywords = {
    "methoden": ["Kapitel 4", "Methodik", "Verfahren"],
    "empfehlung": ["Kapitel 5", "Kapitel 6", "Empfehlung", "Zusammenfassung"]
}

def categorize_paragraphs(paragraphs):
    categorized = {"methoden": [], "empfehlung": [], "other": []}
    for p in paragraphs:
        lower_p = p.lower()
        if any(k.lower() in lower_p for k in chapter_keywords["methoden"]):
            categorized["methoden"].append(p)
        elif any(k.lower() in lower_p for k in chapter_keywords["empfehlung"]):
            categorized["empfehlung"].append(p)
        else:
            categorized["other"].append(p)
    return categorized

# -----------------------------
# Quiz generieren mit Kapitelverteilung
# -----------------------------
def generate_quiz_per_chapter(paragraphs):
    categorized = categorize_paragraphs(paragraphs)
    quiz = []

    # 6 Fragen Methoden
    for _ in range(6):
        p = random.choice(categorized["methoden"])
        q = generate_question_gpt(p, "methoden")
        if q:
            quiz.append(q)

    # 3 Fragen Empfehlung/Zusammenfassung
    for _ in range(3):
        p = random.choice(categorized["empfehlung"])
        q = generate_question_gpt(p, "analyse")
        if q:
            quiz.append(q)

    # 1 Frage anderes Kapitel
    p = random.choice(categorized["other"])
    q = generate_question_gpt(p, "fachwissen")
    if q:
        quiz.append(q)

    random.shuffle(quiz)
    return quiz

# -----------------------------
# Streamlit App
# -----------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Quiz", layout="centered")
    st.title("📘 Projektarbeit Quiz")
    st.write("Teste dein Fach-, Methoden-, Analyse- und Strategiewissen!")

    uploaded_file = st.file_uploader("📄 Projektarbeit (DOCX) hochladen", type="docx")
    categories = ["methoden", "analyse", "fachwissen", "kritik", "transfer"]

    if uploaded_file:
        paragraphs = load_paragraphs_from_file(BytesIO(uploaded_file.read()))
        if "quiz" not in st.session_state:
            st.session_state.quiz = []

        if st.button("🔄 Neues Quiz generieren"):
            st.info("Quiz wird generiert, bitte warten...")
            quiz = generate_quiz_per_chapter(paragraphs)
            st.session_state.quiz = quiz
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.stats = {cat: {"correct": 0, "total": 0} for cat in categories}
            st.success("✅ Quiz erfolgreich generiert!")

        if st.session_state.get("quiz"):
            quiz = st.session_state.quiz
            i = st.session_state.current_index
            q = quiz[i]
            st.markdown(f"### Frage {i+1} ({q['category'].capitalize()})\n{q['question']}")
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

                if i + 1 < len(quiz):
                    st.session_state.current_index += 1
                    st.experimental_rerun()
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