import os
import re
import random
import time
import json
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
import streamlit as st

# -------------------------------------------------
# 🧭 Inhaltsverzeichnis (TOC) aus PDF extrahieren
# -------------------------------------------------
def extract_toc_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    n_pages = len(reader.pages)
    toc_candidate_idx = None

    for i in range(min(8, n_pages)):
        text = reader.pages[i].extract_text() or ""
        if re.search(r"Inhaltsverzeichnis", text, re.IGNORECASE):
            toc_candidate_idx = i
            break

    text_toc = ""
    if toc_candidate_idx is not None:
        for j in range(toc_candidate_idx, min(toc_candidate_idx + 6, n_pages)):
            text_toc += "\n" + (reader.pages[j].extract_text() or "")
    else:
        for i in range(min(12, n_pages)):
            text_toc += "\n" + (reader.pages[i].extract_text() or "")

    lines = text_toc.splitlines()
    toc_entries = []
    toc_line_re = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+\.{3,}\s*(\d+)\s*$")
    toc_line_re2 = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+(\d+)\s*$")

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = toc_line_re.match(ln)
        if not m:
            m = toc_line_re2.match(ln)
        if m:
            chap_num = m.group(1).strip()
            chap_title = m.group(2).strip()
            printed_page = int(m.group(3))
            toc_entries.append({
                "chapter_label": f"{chap_num} {chap_title}",
                "chapter_num": chap_num,
                "chapter_title": chap_title,
                "printed_page": printed_page
            })

    if not toc_entries:
        simple_re = re.compile(r"^(.+?)\s+(\d{1,3})$")
        for ln in lines:
            m = simple_re.match(ln.strip())
            if m:
                title = m.group(1).strip()
                pg = int(m.group(2))
                toc_entries.append({
                    "chapter_label": title,
                    "chapter_num": "",
                    "chapter_title": title,
                    "printed_page": pg
                })

    seen = set()
    cleaned = []
    for e in toc_entries:
        key = (e.get("chapter_title", "").lower(), e.get("printed_page"))
        if key not in seen:
            cleaned.append(e)
            seen.add(key)
    return cleaned


# -------------------------------------------------
# 📘 Inhaltsverzeichnis aus DOCX extrahieren
# -------------------------------------------------
def extract_toc_from_docx(file_stream):
    doc = Document(file_stream)
    toc_entries = []
    toc_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s+(\d+)$")

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        m = toc_pattern.match(text)
        if m:
            chap_num, chap_title, page = m.groups()
            toc_entries.append({
                "chapter_label": f"{chap_num} {chap_title}",
                "chapter_num": chap_num,
                "chapter_title": chap_title,
                "printed_page": int(page)
            })
    return toc_entries


# -------------------------------------------------
# 🔀 Antwortoptionen aus TOC generieren
# -------------------------------------------------
def build_choices_from_toc(correct_entry, toc_list, n_choices=4):
    def format_entry(e):
        if e.get("chapter_num"):
            return f"Kapitel {e['chapter_num']} {e['chapter_title']} — Seite {e['printed_page']}"
        else:
            return f"{e['chapter_title']} — Seite {e['printed_page']}"

    correct_text = format_entry(correct_entry)
    candidates = []
    for e in toc_list:
        if e is correct_entry:
            continue
        candidates.append((abs(e['printed_page'] - correct_entry['printed_page']), e))
    candidates.sort(key=lambda x: x[0])
    distractors = [format_entry(e[1]) for e in candidates[:n_choices - 1]]

    if len(distractors) < n_choices - 1:
        extras = [format_entry(e) for e in toc_list if format_entry(e) not in distractors and format_entry(e) != correct_text]
        random.shuffle(extras)
        distractors += extras[:(n_choices - 1) - len(distractors)]

    choices = [correct_text] + distractors
    random.shuffle(choices)
    return choices, correct_text


# -------------------------------------------------
# 🧠 Navigationsfrage erstellen (deterministisch)
# -------------------------------------------------
def generate_navigation_question_strict(toc_list, category):
    correct_entry = random.choice(toc_list)
    q_types = ["kapitel_seite", "kapitel_only"]
    q_type = random.choice(q_types)

    if q_type == "kapitel_seite":
        question_text = f"In welchem Kapitel und auf welcher Seite befindet sich \"{correct_entry['chapter_title']}\"?"
    else:
        question_text = f"Welches Kapitel behandelt \"{correct_entry['chapter_title']}\"?"

    choices, correct_text = build_choices_from_toc(correct_entry, toc_list, n_choices=4)

    return {
        "question": question_text,
        "choices": choices,
        "answer": correct_text,
        "category": category
    }


# -------------------------------------------------
# 🧩 Quiz generieren
# -------------------------------------------------
def generate_quiz_from_toc(toc_list, categories, questions_total=10):
    quiz = []
    attempts = 0
    while len(quiz) < questions_total and attempts < questions_total * 5:
        category = random.choice(categories)
        q = generate_navigation_question_strict(toc_list, category)
        if all(existing["question"] != q["question"] for existing in quiz):
            quiz.append(q)
        attempts += 1
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
    st.caption("Teste, ob du dich in deiner Arbeit perfekt zurechtfindest – Kapitel, Seiten & Anhänge.")

    uploaded_file = st.file_uploader("📄 Lade deine Projektarbeit (PDF oder DOCX)", type=["pdf", "docx"])
    categories = ["Kapitel", "Strukturwissen", "Verortung", "Anhänge"]

    if uploaded_file:
        file_ext = uploaded_file.name.lower().split(".")[-1]
        st.info("📖 Extrahiere Inhaltsverzeichnis...")
        toc_entries = []

        if file_ext == "pdf":
            toc_entries = extract_toc_from_pdf(BytesIO(uploaded_file.read()))
        elif file_ext == "docx":
            toc_entries = extract_toc_from_docx(BytesIO(uploaded_file.read()))

        if not toc_entries:
            st.error("⚠️ Kein Inhaltsverzeichnis erkannt. Bitte überprüfe dein Dokument.")
            return

        st.success(f"✅ {len(toc_entries)} Kapitel im Inhaltsverzeichnis erkannt.")
        with st.expander("📜 Erkanntes Inhaltsverzeichnis anzeigen"):
            for e in toc_entries:
                st.write(f"- Kapitel {e.get('chapter_num', '')} {e['chapter_title']} (Seite {e['printed_page']})")

        if st.button("🎯 Quiz starten"):
            st.info("Quiz wird erstellt... bitte warten ⏳")
            quiz = generate_quiz_from_toc(toc_entries, categories, questions_total=10)
            st.session_state.quiz = quiz
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.stats = {cat: {"correct": 0, "total": 0} for cat in categories}
            st.success("✅ Quiz erfolgreich erstellt!")

    if st.session_state.get("quiz"):
        quiz = st.session_state.quiz
        i = st.session_state.current_index
        q = quiz[i]

        st.markdown(f"<div class='question-card'><h4>Frage {i+1} ({q['category']})</h4><p>{q['question']}</p></div>", unsafe_allow_html=True)
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
                st.write(f"**Gesamtscore: {st.session_state.score}/{len(quiz)} ({round((st.session_state.score / len(quiz)) * 100)}%)**")

                st.markdown("### 📊 Kategorie-Statistik")
                for cat, stats in st.session_state.stats.items():
                    total, correct = stats["total"], stats["correct"]
                    if total > 0:
                        st.write(f"**{cat}**: {correct}/{total} richtig")

if __name__ == "__main__":
    main()