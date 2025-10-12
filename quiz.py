import os
import re
import random
import time
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
import streamlit as st

# -------------------------------------------------
# 🔍 Inhaltsverzeichnis aus PDF extrahieren
# -------------------------------------------------
def extract_toc_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    text_all = ""
    for page in reader.pages[:50]:  # ersten 50 Seiten durchsuchen
        text_all += "\n" + (page.extract_text() or "")
    lines = text_all.splitlines()
    toc_entries = []
    toc_line = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s+\.{2,}\s*(\d+)\s*$")
    for ln in lines:
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
# 📊 Abbildungen, Tabellen, Anhänge aus PDF
# -------------------------------------------------
def extract_elements_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    elements = []
    pattern = re.compile(r"(Abbildung|Tabelle|Anhang)\s+([\d\.]+)\s*[:\-–]?\s*(.+)", re.IGNORECASE)
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for line in text.splitlines():
            m = pattern.search(line)
            if m:
                elements.append({
                    "type": m.group(1).capitalize(),
                    "label": m.group(2),
                    "title": m.group(3).strip(),
                    "page": page_num + 1
                })
    return elements

# -------------------------------------------------
# 🧩 Antwortoptionen
# -------------------------------------------------
def build_choices_from_toc(correct_entry, toc_list, n_choices=4, show_titles=False, include_page=True):
    def fmt(e):
        num = e.get("chapter_num","")
        page = e.get("printed_page","")
        if show_titles:
            return f"Kapitel {num} {e['chapter_title']} – Seite {page}"
        if include_page:
            return f"Kapitel {num} – Seite {page}"
        return f"Kapitel {num}"
    correct = fmt(correct_entry)
    near = sorted(toc_list, key=lambda x: abs(x["printed_page"] - correct_entry["printed_page"]))
    distract = [fmt(e) for e in near if e is not correct_entry][:n_choices-1]
    choices = [correct]+distract
    random.shuffle(choices)
    return choices, correct

# -------------------------------------------------
# 🧠 Professionelle Fragen
# -------------------------------------------------
def generate_professional_question(toc_list, elements, category):
    q_types = ["kapitel","abbildung","tabelle","anhang"]
    q_type = random.choice(q_types if elements else ["kapitel"])

    # --- Kapitel/Seite ---
    if q_type == "kapitel":
        e = random.choice(toc_list)
        stems = [
            "Die Bewertung von Risiken wurde wo erwähnt?",
            "Das methodische Vorgehen wurde wo beschrieben?",
            "Die Analyse der Ergebnisse findet sich wo?",
            "Wo wurde die Szenarioanalyse erläutert?",
            "Die Entscheidungsgrundlage wurde wo dargestellt?"
        ]
        question = random.choice(stems)
        choices, correct = build_choices_from_toc(e, toc_list, n_choices=4, show_titles=False, include_page=True)
        return {"question":question,"choices":choices,"answer":correct,"category":category}

    # --- Abbildungen / Tabellen / Anhänge ---
    subset = [x for x in elements if x["type"].lower()==q_type]
    if not subset:
        return generate_professional_question(toc_list, elements, category)
    e = random.choice(subset)
    templates={
        "abbildung":[
            f"In welcher Abbildung wird „{e['title']}“ gezeigt?",
            f"Die grafische Darstellung „{e['title']}“ findet sich in welcher Abbildung?"
        ],
        "tabelle":[
            f"Die Ergebnisse zu „{e['title']}“ sind in welcher Tabelle aufgeführt?",
            f"Wo ist „{e['title']}“ tabellarisch dargestellt?"
        ],
        "anhang":[
            f"In welchem Anhang werden „{e['title']}“ beschrieben?",
            f"Die Detailauswertung „{e['title']}“ befindet sich in welchem Anhang?"
        ]
    }
    question=random.choice(templates[q_type])
    distract=[f"{x['type']} {x['label']}" for x in subset if x is not e]
    random.shuffle(distract)
    distract=distract[:3]
    correct=f"{e['type']} {e['label']}"
    choices=[correct]+distract
    random.shuffle(choices)
    return {"question":question,"choices":choices,"answer":correct,"category":category}

# -------------------------------------------------
# 🧩 Quiz erstellen
# -------------------------------------------------
def generate_full_quiz(toc_list,elements,categories,questions_total=10):
    quiz=[]
    while len(quiz)<questions_total:
        cat=random.choice(categories)
        q=generate_professional_question(toc_list,elements,cat)
        if q and q["question"] not in [x["question"] for x in quiz]:
            quiz.append(q)
    return quiz

# -------------------------------------------------
# 🎮 Streamlit-App
# -------------------------------------------------
def main():
    st.set_page_config(page_title="Projektarbeit-Navigationsquiz",layout="centered")
    st.title("🧭 Navigations- und Struktur-Quiz zur Projektarbeit")
    st.caption("Teste, ob du dich in deiner Arbeit perfekt zurechtfindest – Kapitel, Anhänge, Abbildungen & Tabellen.")

    uploaded=st.file_uploader("📄 Lade deine Projektarbeit (PDF oder DOCX)",type=["pdf","docx"])
    cats=["Kapitel","Strukturwissen","Abbildungen","Tabellen","Anhänge"]

    if uploaded:
        ext=uploaded.name.lower().split(".")[-1]
        st.info("📖 Analysiere Dokument …")
        toc=[]; elements=[]
        data=uploaded.read()
        if ext=="pdf":
            toc=extract_toc_from_pdf(BytesIO(data))
            elements=extract_elements_from_pdf(BytesIO(data))
        else:
            toc=extract_toc_from_docx(BytesIO(data))

        st.success(f"✅ {len(toc)} Kapitel und {len(elements)} Sonder-Elemente erkannt.")
        with st.expander("📜 Erkanntes Inhaltsverzeichnis"):
            for e in toc:
                st.write(f"- Kapitel {e.get('chapter_num','')} {e['chapter_title']} (Seite {e['printed_page']})")
        if elements:
            with st.expander("🖼️ Erkannte Abbildungen / Tabellen / Anhänge"):
                for el in elements:
                    st.write(f"- {el['type']} {el['label']}: {el['title']} (Seite {el['page']})")

        if st.button("🎯 Quiz starten"):
            quiz=generate_full_quiz(toc,elements,cats,questions_total=10)
            st.session_state.quiz=quiz
            st.session_state.index=0
            st.session_state.score=0
            st.session_state.stats={c:{"correct":0,"total":0} for c in cats}
            st.success("✅ Quiz erstellt!")

    if st.session_state.get("quiz"):
        qlist=st.session_state.quiz
        i=st.session_state.index
        q=qlist[i]
        st.markdown(f"### Frage {i+1} ({q['category']})")
        st.write(q["question"])
        choice=st.radio("Antwort auswählen:",q["choices"],key=f"q{i}")

        if st.button("Antwort bestätigen"):
            st.session_state.stats[q["category"]]["total"]+=1
            if choice==q["answer"]:
                st.success("✅ Richtig!")
                st.session_state.score+=1
                st.session_state.stats[q["category"]]["correct"]+=1
            else:
                st.error(f"❌ Falsch! Richtig: {q['answer']}")
            time.sleep(1)
            if i+1<len(qlist):
                st.session_state.index+=1
                st.rerun()
            else:
                st.balloons()
                st.subheader("🏁 Quiz abgeschlossen!")
                st.write(f"**Gesamt: {st.session_state.score}/{len(qlist)} ("
                         f"{round(st.session_state.score/len(qlist)*100)} %)**")
                st.markdown("### 📊 Statistik")
                for c,s in st.session_state.stats.items():
                    if s["total"]:
                        st.write(f"**{c}**: {s['correct']}/{s['total']} richtig")

if __name__=="__main__":
    main()