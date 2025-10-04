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
# Speicher für DOCX
# -----------------------------
STORAGE_DIR = Path(".streamlit_data")
STORAGE_DIR.mkdir(exist_ok=True)
SAVED_DOCX_PATH = STORAGE_DIR / "saved_projektarbeit.docx"

# -----------------------------
# DOCX einlesen & filtern
# -----------------------------
def load_paragraphs_from_file(file, min_length=30):
    doc = Document(file)
    paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        lower = text.lower()
        # Anhänge sinnvoll nutzen, Prozessflüsse ignorieren
        if len(text) > min_length and (
            "prozessfluss" not in lower
        ):
            paragraphs.append(text)
    return paragraphs

def filter_paragraphs(paragraphs):
    allowed = []
    for p in paragraphs:
        lower = p.lower()
        # Prozessfluss ignorieren
        if "prozessfluss" in lower:
            continue
        # Anhänge nur für Rechnungen/Nutzwertanalyse/Bewertungskriterien
        if any(k in lower for k in ["rechnung","nutzwertanalyse","bewertungskriterien"]):
            allowed.append(p)
        elif not lower.startswith("anhang"):
            allowed.append(p)
    return allowed

# -----------------------------
# Kapitel zuweisen
# -----------------------------
def assign_chapters(paragraphs):
    chapter = "allgemein"
    paragraphs_with_chapter = []
    for p in paragraphs:
        # Erkennen von Kapitelüberschriften z.B. "1. Einleitung"
        parts = p.strip().split()
        if parts and parts[0].replace(".","").isdigit():
            chapter = parts[1] if len(parts)>1 else chapter
        paragraphs_with_chapter.append({"text": p, "chapter": chapter})
    return paragraphs_with_chapter

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

Bitte die Antwortmöglichkeiten **zufällig mischen**.
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
            # Nachbearbeitung
            data["question"] = data["question"].replace("...", "").strip()
            data["answer"] = data["answer"].replace("...", "").strip()
            data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]

            # Richtiges mischen
            correct = data["answer"]
            random.shuffle(data["choices"])
            data["answer"] = correct

            data["category"] = category
            return data
        except Exception:
            time.sleep(1)
    return None

# -----------------------------
# Quiz pro Kapitel generieren
# -----------------------------
def generate_quiz_by_chapter(paragraphs_with_chapter, categories, questions_total=10):
    quiz = []
    chapters = list({p["chapter"] for p in paragraphs_with_chapter})
    # 1 Frage pro Kapitel
    for ch in chapters:
        paras = [p["text"] for p in paragraphs_with_chapter if p["chapter"]==ch]
        if paras:
            para = random.choice(paras)
            category = random.choice(categories)
            q = generate_question_gpt(para, category)
            if q:
                q["chapter"] = ch
                quiz.append(q)
        if len(quiz) >= questions_total:
            break
    # Restliche Fragen zufällig auffüllen
    while len(quiz) < questions_total:
        para_dict = random.choice(paragraphs_with_chapter)
        q = generate_question_gpt(para_dict["text"], random.choice(categories))
        if q:
            q["chapter"] = para_dict["chapter"]
            quiz.append(q)
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

    # Hochgeladene Datei speichern
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

    # Quiz generieren
    if st.session_state.uploaded_docx:
        paragraphs = load_paragraphs_from_file(BytesIO(st.session_state.uploaded_docx))
        paragraphs = filter_paragraphs(paragraphs)
        paragraphs_with_chapter = assign_chapters(paragraphs)

        if "quiz" not in st.session_state:
            st.session_state.quiz = []
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.category_score = {cat:0 for cat in categories}
            st.session_state.category_total = {cat:0 for cat in categories}

        if st.button("🔄 Neues Quiz generieren"):
            st.info("⏳ Quiz wird generiert...")
            st.session_state.quiz = generate_quiz_by_chapter(paragraphs_with_chapter, categories, 10)
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.category_score = {cat:0 for cat in categories}
            st.session_state.category_total = {cat:0 for cat in categories}
            st.success("✅ Quiz generiert!")

        # Eine Frage pro Seite
        if st.session_state.quiz:
            q = st.session_state.quiz[st.session_state.current_index]
            st.markdown(f"### Frage {st.session_state.current_index +1} ({q['category']}, Kapitel: {q.get('chapter','allgemein')})")
            st.markdown(f"<div style='background-color:#f9f9f9;padding:15px;border-radius:10px'>{q['question']}</div>", unsafe_allow_html=True)

            choice = st.radio("Antwort auswählen:", q["choices"], key=f"q{st.session_state.current_index}")
            if st.button("Antwort bestätigen"):
                if choice == q["answer"]:
                    st.success("✅ Richtig!")
                    st.session_state.score +=1
                    st.session_state.category_score[q["category"]] +=1
                else:
                    st.error(f"❌ Falsch! Richtige Antwort: {q['answer']}")
                st.session_state.category_total[q["category"]] +=1

            # Navigation Buttons
            col1, col2 = st.columns(2)
            if col1.button("⬅️ Vorherige") and st.session_state.current_index >0:
                st.session_state.current_index -=1
            if col2.button("➡️ Nächste") and st.session_state.current_index < len(st.session_state.quiz)-1:
                st.session_state.current_index +=1

            st.progress((st.session_state.current_index +1)/len(st.session_state.quiz))
            st.markdown("<br>", unsafe_allow_html=True)

            # Statistik Button am Ende
            if st.session_state.current_index == len(st.session_state.quiz)-1:
                st.markdown("---")
                st.subheader("📊 Statistik nach Kategorie")
                for cat in categories:
                    total = st.session_state.category_total.get(cat,0)
                    correct = st.session_state.category_score.get(cat,0)
                    st.write(f"**{cat}**: {correct}/{total} richtig")
                st.metric("Gesamt-Score", f"{st.session_state.score}/{len(st.session_state.quiz)}")

if __name__ == "__main__":
    main()