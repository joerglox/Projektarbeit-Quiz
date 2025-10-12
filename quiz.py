import re
import random
import time
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
import streamlit as st

# -------------------------------------------------
# 🔍 Inhaltsverzeichnis aus PDF
# -------------------------------------------------
def extract_toc_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    text_all = ""
    for page in reader.pages[:60]:
        text_all += "\n" + (page.extract_text() or "")
    toc_entries = []
    toc_line = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+\.{2,}\s*(\d+)\s*$")
    for ln in text_all.splitlines():
        m = toc_line.match(ln.strip())
        if m:
            num, title, page = m.groups()
            toc_entries.append({
                "chapter_num": num,
                "chapter_title": title.strip(),
                "printed_page": int(page)
            })
    return toc_entries

# -------------------------------------------------
# 📄 Inhaltsverzeichnis aus DOCX
# -------------------------------------------------
def extract_toc_from_docx(file_stream):
    doc = Document(file_stream)
    toc_entries = []
    pat = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s+(\d+)$")
    for p in doc.paragraphs:
        m = pat.match(p.text.strip())
        if m:
            num, title, page = m.groups()
            toc_entries.append({
                "chapter_num": num,
                "chapter_title": title.strip(),
                "printed_page": int(page)
            })
    return toc_entries

# -------------------------------------------------
# 📑 Abbildungen / Tabellen / Anhänge
# -------------------------------------------------
def extract_elements_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    elements = []
    pattern = re.compile(
        r"(?:(Abbildung|Tabelle|Anhang|Anlage|Appendix))\s*([A-Za-z0-9\.\-]*)\s*[:\-–]?\s*(.{3,120})",
        re.IGNORECASE
    )
    alt_pattern = re.compile(r"^(?:ANHANG|ANLAGE|APPENDIX)\s*([A-Za-z0-9\.\-]*)\s*(.{3,120})$", re.IGNORECASE)

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = pattern.search(line) or alt_pattern.search(line)
            if m:
                type_ = m.group(1) if m.lastindex >= 1 else "Anhang"
                label = m.group(2).strip() if len(m.groups()) > 1 else ""
                title = m.group(len(m.groups())).strip(" .:-–")
                if type_.lower() in ["anlage", "appendix"]:
                    type_ = "Anhang"
                if label.lower().startswith("a"):
                    label = label[1:]
                elements.append({
                    "type": type_.capitalize(),
                    "label": label or "?",
                    "title": title,
                    "page": page_num + 1
                })

    seen = set()
    cleaned = []
    for e in elements:
        key = (e["type"], e["label"], e["title"])
        if key not in seen:
            cleaned.append(e)
            seen.add(key)
    cleaned.sort(key=lambda x: (x["type"], x.get("label", ""), x.get("page", 9999)))
    return cleaned

# -------------------------------------------------
# 🔀 Antwortoptionen
# -------------------------------------------------
def build_choices_from_toc(correct_entry, toc_list, n_choices=4, include_page=True):
    def fmt(e):
        num = e.get("chapter_num", "")
        page = e.get("printed_page", "")
        if include_page:
            return f"Kapitel {num} – Seite {page}"
        return f"Kapitel {num}"

    correct = fmt(correct_entry)
    near = sorted(toc_list, key=lambda x: abs(x["printed_page"] - correct_entry["printed_page"]))
    distract = [fmt(e) for e in near if e is not correct_entry][:n_choices - 1]
    choices = [correct] + distract
    random.shuffle(choices)
    return choices, correct

# -------------------------------------------------
# 🧠 Professionelle Fragen (inhaltlich)
# -------------------------------------------------
def generate_professional_question(toc_list, elements, category):
    q_types = ["kapitel", "abbildung", "anhang"]
    q_type = random.choice(q_types if elements else ["kapitel"])

    # --- Kapitel / Seite ---
    if q_type == "kapitel":
        e = random.choice(toc_list)
        stems = [
            "Die Berechnung der Prozesskosten wurde wo beschrieben?",
            "Die Bewertung von Risiken wurde wo erläutert?",
            "Die Durchführung der FMEA ist wo dokumentiert?",
            "Die Szenarioanalyse ist in welchem Abschnitt dargestellt?",
            "Die Entscheidungsfindung wurde wo erklärt?"
        ]
        question = random.choice(stems)
        choices, correct = build_choices_from_toc(e, toc_list, n_choices=4, include_page=True)
        return {"question": question, "choices": choices, "answer": correct, "category": category}

    # --- Abbildungen ---
    if q_type == "abbildung":
        subset = [x for x in elements if x["type"].lower() == "abbildung"]
        if not subset:
            return generate_professional_question(toc_list, elements, category)
        e = random.choice(subset)
        question = random.choice([
            f"Die grafische Darstellung zur „{e['title']}“ befindet sich wo?",
            f"In welchem Kapitel oder Anhang wird die Abbildung zur „{e['title']}“ gezeigt?"
        ])
        correct = f"Abbildung {e['label']}"
        distract = [f"Kapitel {random.choice(toc_list)['chapter_num']}" for _ in range(3)]
        choices = [correct] + distract
        random.shuffle(choices)
        return {"question": question, "choices": choices, "answer": correct, "category": category}

    # --- Anhänge ---
    subset = [x for x in elements if x["type"].lower() == "anhang"]
    if not subset:
        return generate_professional_question(toc_list, elements, category)
    e = random.choice(subset)
    question = random.choice([
        f"Die Tabelle oder Berechnung zu „{e['title']}“ ist wo enthalten?",
        f"Die Auswertung zu „{e['title']}“ wurde wo abgelegt?",
        f"Die Berechnungsergebnisse zu „{e['title']}“ sind wo dokumentiert?"
    ])

    # plausible Ablenker
    labels = sorted(list({x["label"] for x in subset if x["label"]}))
    distract = []
    if labels:
        idx = labels.index(e["label"]) if e["label"] in labels else 0
        for offset in [-2, -1, 1, 2]:
            if 0 <= idx + offset < len(labels):
                distract.append(f"Anhang {labels[idx + offset]}")
    distract += [f"Kapitel {random.choice(toc_list)['chapter_num']}" for _ in range(2)]
    distract = distract[:3]
    correct = f"Anhang {e['label']}"
    choices = [correct] + distract
    random.shuffle(choices)

    return {"question": question, "choices": choices, "answer": correct, "category": category}

# -------------------------------------------------
# 🧩 Quiz erstellen
# -------------------------------------------------
def generate_full_quiz(toc_list, elements, categories, questions_total=10):
    quiz = []
    while len(quiz) < questions_total:
        cat = random.choice(categories)
        q = generate_professional_question(toc_list, elements, cat)
        if q and q["question"] not in [x["question"] for x in quiz]:
            quiz.append(q)
    return quiz

# -------------------------------------------------
# 🎮 Streamlit-App
# -------------------------------------------------
def main():
    st.set_page_config(page_title="Projektarbeit Struktur-Quiz", layout="centered")
    st.title("📘 Struktur- & Navigationsquiz zur Projektarbeit")
    st.caption("Trainiere dein Verständnis – finde sofort, wo Inhalte, Berechnungen und Auswertungen stehen.")

    uploaded = st.file_uploader("📄 Lade deine Projektarbeit (PDF oder DOCX)", type=["pdf", "docx"])
    cats = ["Kapitel", "Strukturwissen", "Abbildungen", "Anhänge"]

    if uploaded:
        ext = uploaded.name.lower().split(".")[-1]
        st.info("📖 Analysiere Dokument ...")
        data = uploaded.read()
        toc, elements = [], []
        if ext == "pdf":
            toc = extract_toc_from_pdf(BytesIO(data))
            elements = extract_elements_from_pdf(BytesIO(data))
        elif ext == "docx":
            toc = extract_toc_from_docx(BytesIO(data))

        st.success(f"✅ {len(toc)} Kapitel und {len(elements)} Elemente erkannt.")
        with st.expander("📜 Inhaltsverzeichnis"):
            for e in toc:
                st.write(f"- Kapitel {e.get('chapter_num','')} {e['chapter_title']} (Seite {e['printed_page']})")
        if elements:
            with st.expander("📊 Abbildungen / Anhänge"):
                for el in elements:
                    st.write(f"- {el['type']} {el['label']}: {el['title']} (Seite {el['page']})")

        if st.button("🎯 Quiz starten"):
            quiz = generate_full_quiz(toc, elements, cats, questions_total=10)
            st.session_state.quiz = quiz
            st.session_state.index = 0
            st.session_state.score = 0
            st.session_state.stats = {c: {"correct": 0, "total": 0} for c in cats}
            st.success("✅ Quiz erstellt!")

    if st.session_state.get("quiz"):
        qlist = st.session_state.quiz
        i = st.session_state.index
        q = qlist[i]
        st.markdown(f"### Frage {i+1} ({q['category']})")
        st.write(q["question"])
        choice = st.radio("Antwort auswählen:", q["choices"], key=f"q{i}")

        if st.button("Antwort bestätigen"):
            st.session_state.stats[q["category"]]["total"] += 1
            if choice == q["answer"]:
                st.success("✅ Richtig!")
                st.session_state.score += 1
                st.session_state.stats[q["category"]]["correct"] += 1
            else:
                st.error(f"❌ Falsch! Richtige Antwort: {q['answer']}")
            time.sleep(1)
            if i + 1 < len(qlist):
                st.session_state.index += 1
                st.rerun()
            else:
                st.balloons()
                st.subheader("🏁 Quiz abgeschlossen!")
                st.write(f"**Gesamt: {st.session_state.score}/{len(qlist)} "
                         f"({round(st.session_state.score / len(qlist) * 100)} %)**")
                st.markdown("### 📊 Kategorie-Statistik")
                for c, s in st.session_state.stats.items():
                    if s["total"]:
                        st.write(f"**{c}**: {s['correct']}/{s['total']} richtig")

if __name__ == "__main__":
    main()