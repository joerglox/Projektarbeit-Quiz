#!/usr/bin/env python3
import os
import json
import random
import time
import openai
from docx import Document

# -----------------------------
# OPENAI API Key
# -----------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OpenAI API-Key nicht gefunden. Bitte als Umgebungsvariable OPENAI_API_KEY setzen.")

# -----------------------------
# DOCX einlesen
# -----------------------------
def load_paragraphs(docx_path):
    doc = Document(docx_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    paragraphs = [p for p in paragraphs if len(p) > 10]
    return paragraphs

# -----------------------------
# Absatz in kleinere Teile splitten
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
# GPT-Generierung pro Frage
# -----------------------------
def generate_question_gpt(paragraph, category, retries=7, debug=False):
    paragraph = paragraph[:300]
    prompt = f"""
Du bist ein Quiz-Generator. Erstelle eine **kritische und komplexe Prüfungsfrage** der Kategorie '{category}' aus folgendem Absatz:

{paragraph}

Die Frage soll prüfen:
- Ob der Prüfling den Inhalt der Projektarbeit verstanden hat
- Warum diese Methode eingesetzt wurde
- Wie die Methode funktioniert
- Welche Alternativen es gibt und wie diese funktionieren
- Welche Auswirkungen Änderungen der Rahmenbedingungen auf das Ergebnis haben
- Szenarien, die zu anderen Empfehlungen führen könnten
- Der Prüfling muss Fach-, Methoden-, Analytische- und strategische Kompetenz nachweisen

Antwort im JSON-Format. WICHTIG:
- Jede Antwortmöglichkeit muss ein vollständiger, klarer Satz sein (keine "..." oder abgebrochene Aussagen).
- Es müssen genau 4 plausible Antwortmöglichkeiten in "choices" stehen.
- "answer" muss exakt einer der "choices" entsprechen.
- Keine zusätzliche Erklärung außerhalb des JSON.

Beispiel:
{{
    "question": "Welche Methode wurde eingesetzt und warum?",
    "choices": ["Methode A wurde gewählt, weil ...", "Methode B hat Vorteile, da ...", "Methode C wurde genutzt, um ...", "Methode D ist geeignet, wenn ..."],
    "answer": "Methode A wurde gewählt, weil ..."
}}
"""
    for attempt in range(retries):
        try:
            if debug:
                print(f"DEBUG: Generiere Frage (Retry {attempt+1})...")
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system","content":"Du bist ein Quiz-Generator, der komplexe Prüfungsfragen erstellt."},
                    {"role":"user","content":prompt}
                ],
                max_tokens=750
            )
            content = response.choices[0].message.content.strip()
            if debug:
                print("DEBUG GPT-Ausgabe:", content[:500], "...")
            if not content:
                if debug:
                    print("⚠️ Leere Antwort vom Modell")
                time.sleep(1)
                continue
            data = json.loads(content)
            if all(k in data for k in ["question","choices","answer"]):
                # Nachbearbeitung: "..." entfernen und trimmen
                data["question"] = data["question"].replace("...", "").strip()
                data["answer"] = data["answer"].replace("...", "").strip()
                data["choices"] = [c.replace("...", "").strip() for c in data["choices"]]
                data["category"] = category
                return data
        except json.JSONDecodeError:
            if debug:
                print("⚠️ JSONDecodeError")
                print(content)
            time.sleep(1)
        except Exception as e:
            if debug:
                print(f"⚠️ API-Fehler: {e}")
            time.sleep(1)
    return None

# -----------------------------
# Quiz generieren
# -----------------------------
def generate_quiz(paragraphs, categories, questions_total=10, debug=False):
    quiz = []
    # Jede Kategorie mindestens einmal abfragen
    for cat in categories:
        paragraph = random.choice(paragraphs)
        parts = split_paragraph(paragraph, max_length=300)
        for part in parts:
            q = generate_question_gpt(part, cat, retries=7, debug=debug)
            if q:
                quiz.append(q)
            if len(quiz) >= questions_total:
                break
        if len(quiz) >= questions_total:
            break
    # Restliche Fragen zufällig auffüllen
    while len(quiz) < questions_total:
        paragraph = random.choice(paragraphs)
        category = random.choice(categories)
        parts = split_paragraph(paragraph, max_length=300)
        for part in parts:
            q = generate_question_gpt(part, category, retries=7, debug=debug)
            if q:
                quiz.append(q)
            if len(quiz) >= questions_total:
                break
    return quiz

# -----------------------------
# Quiz speichern / laden
# -----------------------------
def save_quiz(quiz, filename="quiz_fragen.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, indent=2)

def load_quiz(filename="quiz_fragen.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------
# Terminal-Quiz
# -----------------------------
def run_quiz_terminal(quiz):
    score = {}
    total = {}
    for i, q in enumerate(quiz,1):
        cat = q.get("category","allgemein")
        if cat not in score:
            score[cat] = 0
            total[cat] = 0
        print(f"\nFrage {i} ({cat}): {q['question']}")
        for idx, choice in enumerate(q['choices'],1):
            print(f" {idx}. {choice}")
        try:
            ans = int(input("Deine Wahl (1-4): "))
            sel = q['choices'][ans-1]
        except:
            sel = ""
        if sel.lower() == q['answer'].lower():
            print("Richtig!")
            score[cat] +=1
        else:
            print(f"Falsch! Richtige Antwort: {q['answer']}")
        total[cat] +=1
    print("\n--- Auswertung ---")
    for cat in score:
        print(f"{cat}: {score[cat]}/{total[cat]}")
    print(f"Gesamt: {sum(score.values())}/{sum(total.values())}")

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    docx_path = "projektarbeit.docx"
    print(f"Lade Projektarbeit: {docx_path}")
    paragraphs = load_paragraphs(docx_path)
    print(f"{len(paragraphs)} Absätze gefunden.")
    categories = ["fachwissen","methoden","analyse","kritik","transfer"]

    print(f"Quiz wird generiert ({10} Fragen)...")
    quiz = generate_quiz(paragraphs, categories, questions_total=10, debug=False)
    print(f"{len(quiz)} Fragen generiert. Speichere in 'quiz_fragen.json'...")
    save_quiz(quiz)

    start = input("Quiz jetzt im Terminal starten? (j/n): ").strip().lower()
    if start == "j":
        run_quiz_terminal(quiz)
    else:
        print("Fertig. Du kannst das Quiz jederzeit aus 'quiz_fragen.json' laden.")