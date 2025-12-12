import streamlit as st
import json
import hashlib
import os
import PyPDF2
from groq import Groq
from datetime import datetime

pip install PyPDF2

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(page_title="AGL SOP Training", layout="centered")

client = None
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

DATA_USERS = "users.json"
DATA_SOPS = "sops.json"
DATA_RESULTS = "results.json"
LOGO_FILE = "agl_logo.png"

# ============================================================
# HELPERS
# ============================================================

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=4)
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

initial_users = {
    "AGLadmin": {"password": hash_pw("12345678"), "role": "admin"},
    "score": {"password": hash_pw("12345678"), "role": "score_viewer"}
}

users = load_json(DATA_USERS, initial_users)
sops = load_json(DATA_SOPS, {})
results = load_json(DATA_RESULTS, {})

# ============================================================
# AI HELPERS
# ============================================================

def ai(prompt):
    if client is None:
        return ""
    r = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role":"user","content":prompt}]
    )
    return r.choices[0].message.content

def generate_training_package(text):
    prompt = f"""
Turn this SOP into JSON:

{{
 "summary": "Engaging 120-word summary",
 "steps": ["6 key steps"],
 "warnings": ["4 safety warnings"],
 "checklist": ["5 checklist items"]
}}

SOP:
{text}
"""
    out = ai(prompt)
    try:
        return json.loads(out)
    except:
        return None

def generate_quiz(text, weak_topics, num_q=7):
    prompt = f"""
Generate {num_q} SOP training questions in JSON.

WEAK AREAS TO FOCUS ON:
{weak_topics}

Rules:
- At least 60% of questions must focus on weak areas.
- Mix true/false, multiple choice, scenarios, fill-in.
- Provide correct answer.
- Provide a short topic label for each question (what concept it tests).
Format:
{{
 "questions":[
   {{
     "type":"mcq|tf|short|scenario",
     "question":"...",
     "choices":["A)...","B)...","C)...","D)..."],  # only if mcq
     "answer":"...",
     "topic":"short label of concept tested"
   }}
 ]
}}
SOP:
{text}
"""
    out = ai(prompt)
    try:
        return json.loads(out)
    except:
        return None

def extract_pdf_text(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join([p.extract_text() or "" for p in reader.pages])

# ============================================================
# UI HEADER/FOOTER
# ============================================================

def show_header():
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=160)
    else:
        st.markdown("<h2>AGL</h2>", unsafe_allow_html=True)

def show_footer():
    st.markdown("---")
    st.markdown(
        "<p style='font-size:11px;text-align:center;color:gray;'>Created by Marlon Malgas</p>",
        unsafe_allow_html=True
    )

# ============================================================
# LOGIN SYSTEM
# ============================================================

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    show_header()
    st.title("Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u in users and users[u]["password"] == hash_pw(p):
            st.session_state.user = u
            st.experimental_rerun()
        else:
            st.error("Invalid login")

    show_footer()
    st.stop()

# ============================================================
# DASHBOARDS BASED ON ROLE
# ============================================================

username = st.session_state.user
role = users[username]["role"]

show_header()
st.sidebar.write(f"Logged in as: {username} ({role})")

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.experimental_rerun()

# ============================================================
# ADMIN PANEL
# ============================================================

if role == "admin":
    st.header("Admin Dashboard")
    tabs = st.tabs(["SOPs", "Users", "Branding", "Results"])

    # -------------------- TAB 1: SOP MANAGEMENT --------------------
    with tabs[0]:
        st.subheader("Upload / Update SOP")

        sop_name = st.text_input("SOP Title")
        pdf = st.file_uploader("Upload SOP PDF", type="pdf")

        if pdf and sop_name:
            if st.button("Generate Training Package"):
                text = extract_pdf_text(pdf)
                pkg = generate_training_package(text)

                if pkg:
                    sops[sop_name] = {
                        "content": text,
                        "summary": pkg["summary"],
                        "steps": pkg["steps"],
                        "warnings": pkg["warnings"],
                        "checklist": pkg["checklist"]
                    }
                    save_json(DATA_SOPS, sops)
                    st.success("SOP Added!")

        st.markdown("---")
        st.subheader("Existing SOPs")

        for name in list(sops.keys()):
            with st.expander(name):
                st.write(sops[name]["summary"])
                if st.button("Delete", key=f"del_{name}"):
                    del sops[name]
                    save_json(DATA_SOPS, sops)
                    st.experimental_rerun()

    # -------------------- TAB 2: USER MANAGEMENT --------------------
    with tabs[1]:
        st.subheader("Create User")
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type="password")
        nr = st.selectbox("Role", ["user", "admin", "score_viewer"])

        if st.button("Add User"):
            users[nu] = {"password": hash_pw(np), "role": nr}
            save_json(DATA_USERS, users)
            st.success("User added")

        st.markdown("---")
        st.subheader("Edit User")

        pick = st.selectbox("Select", list(users.keys()))
        if pick:
            np2 = st.text_input("New Password", type="password", key=f"pw_{pick}")
            nr2 = st.selectbox("Role", ["user","admin","score_viewer"], key=f"role_{pick}")

            if st.button("Save", key=f"save_{pick}"):
                if np2:
                    users[pick]["password"] = hash_pw(np2)
                users[pick]["role"] = nr2
                save_json(DATA_USERS, users)
                st.success("Updated")

            if pick != username:
                if st.button("Delete", key=f"del_user_{pick}"):
                    del users[pick]
                    save_json(DATA_USERS, users)
                    st.experimental_rerun()

    # -------------------- TAB 3: BRANDING --------------------
    with tabs[2]:
        st.subheader("Upload Logo")
        logo = st.file_uploader("Upload Logo", type=["png","jpg","jpeg"])

        if logo:
            with open(LOGO_FILE, "wb") as f:
                f.write(logo.getvalue())
            st.success("Logo updated")
            st.image(LOGO_FILE, width=160)

    # -------------------- TAB 4: RESULTS --------------------
    with tabs[3]:
        st.subheader("All Results")
        st.json(results)

    show_footer()
    st.stop()

# ============================================================
# SCORE VIEWER PANEL
# ============================================================

if role == "score_viewer":
    st.header("Score Viewer")
    st.json(results)
    show_footer()
    st.stop()

# ============================================================
# USER TRAINING MODULE
# ============================================================

st.header("SOP Training")

if not sops:
    st.info("No SOPs yet.")
    show_footer()
    st.stop()

choice = st.selectbox("Choose SOP", ["--"] + list(sops.keys()))
if choice == "--":
    show_footer()
    st.stop()

sop = sops[choice]

# Create user result profile if missing
if username not in results:
    results[username] = {}

if choice not in results[username]:
    results[username][choice] = {
        "weak_areas": {},
        "history": []
    }
save_json(DATA_RESULTS, results)

weak_areas = results[username][choice]["weak_areas"]

# ----------------------------- SHOW SOP CONTENT -----------------------------

st.subheader("Summary")
st.write(sop["summary"])

st.subheader("Steps")
for s in sop["steps"]:
    st.write("• " + s)

st.subheader("Warnings")
for w in sop["warnings"]:
    st.write("⚠ " + w)

st.subheader("Checklist")
for c in sop["checklist"]:
    st.checkbox(c, key=f"{username}_{choice}_{c}")

st.markdown("---")

# ----------------------------- QUIZ BUTTON -----------------------------

num = st.slider("Number of Questions", 5, 12, 7)

if st.button("Start Quiz"):
    with st.spinner("Generating Quiz..."):
        quiz = generate_quiz(
            sop["content"],
            weak_topics=list(weak_areas.keys()),
            num_q=num
        )
        st.session_state["current_quiz"] = quiz

        st.experimental_rerun()

# ----------------------------- QUIZ RUNNER -----------------------------

if "current_quiz" in st.session_state:
    quiz = st.session_state["current_quiz"]
    st.subheader("Quiz")

    answers = []
    for i, q in enumerate(quiz["questions"]):
        st.markdown(f"**Q{i+1} — {q['question']}**")

        if q["type"] == "mcq":
            ans = st.radio("Select", q["choices"], key=f"q{i}")
        elif q["type"] == "tf":
            ans = st.radio("True/False", ["True","False"], key=f"q{i}")
        else:
            ans = st.text_input("Answer", key=f"q{i}")

        answers.append(ans)

    if st.button("Submit Quiz"):
        score = 0
        wrong_topics = []

        for i, q in enumerate(quiz["questions"]):
            correct = q["answer"].strip().lower()
            user_ans = answers[i].strip().lower()

            if correct in user_ans or user_ans in correct:
                score += 1
            else:
                wrong_topics.append(q["topic"])

        # UPDATE weak areas
        for t in wrong_topics:
            weak_areas[t] = weak_areas.get(t, 0) + 1

        # REMOVE mastered topics
        mastered = [t for t, count in weak_areas.items() if count == 0]
        for m in mastered:
            del weak_areas[m]

        # SAVE
        results[username][choice]["weak_areas"] = weak_areas
        results[username][choice]["history"].append(
            {"score":score, "total":len(quiz["questions"]), "time":datetime.now().isoformat()}
        )
        save_json(DATA_RESULTS, results)

        st.success(f"Score: {score} / {len(quiz['questions'])}")

        if weak_areas:
            st.warning("You still have weak areas:")
            st.write(list(weak_areas.keys()))
            st.write("Your next quiz will focus on these.")

        else:
            st.success("You have mastered all weak areas for this SOP!")

        del st.session_state["current_quiz"]

show_footer()