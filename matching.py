import pandas as pd
import numpy as np
import re
import joblib
from collections import Counter


# ============================================================
# SKILL PASSPORT - COMPLETE ML PROTOTYPE
# ============================================================

print()
print("==============================================")
print("          SKILL PASSPORT AI PROTOTYPE")
print("==============================================")


# ============================================================
# 1. LOAD ML DATA
# ============================================================

print("\nLoading ML model data...")

data = joblib.load("model/tfidf_data.pkl")

vocabulary = data["vocabulary"]
word_to_index = data["word_to_index"]
idf = data["idf"]

opportunities = pd.read_csv("data/opportunities.csv")

print("ML data loaded!")


# ============================================================
# 2. READ STUDENT RESUME
# ============================================================

print("\nReading student resume...")

with open(
    "test_resume.txt",
    "r",
    encoding="utf-8"
) as file:

    resume = file.read()

print("Resume loaded!")


# ============================================================
# 3. CLEAN TEXT
# ============================================================

def clean_text(text):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# 4. SKILL EXTRACTION
# ============================================================

SKILLS = [

    "python",
    "java",
    "javascript",
    "c++",
    "sql",

    "html",
    "css",
    "react",

    "machine learning",
    "deep learning",
    "artificial intelligence",

    "data science",
    "data analysis",

    "pandas",
    "numpy",

    "tensorflow",
    "pytorch",

    "computer vision",
    "opencv",

    "nlp",
    "natural language processing",

    "statistics",

    "excel",
    "power bi",
    "tableau",

    "git",
    "github",

    "docker",
    "linux",

    "cybersecurity",
    "networking",

    "figma",
    "ui design",
    "ux design"
]


def extract_skills(text):

    text = text.lower()

    found = []

    for skill in SKILLS:

        pattern = r"\b" + re.escape(skill) + r"\b"

        if re.search(pattern, text):

            found.append(skill)

    return found


student_skills = extract_skills(resume)


# ============================================================
# 5. CREATE TF-IDF VECTOR
# ============================================================

def create_vector(text):

    text = clean_text(text)

    words = text.split()

    counts = Counter(words)

    vector = np.zeros(
        len(vocabulary),
        dtype=np.float32
    )

    total_words = len(words)

    if total_words == 0:

        return vector

    for word, count in counts.items():

        if word in word_to_index:

            index = word_to_index[word]

            tf = count / total_words

            vector[index] = tf * idf[index]

    return vector


# ============================================================
# 6. COSINE SIMILARITY
# ============================================================

def cosine_similarity(a, b):

    denominator = (
        np.linalg.norm(a)
        *
        np.linalg.norm(b)
    )

    if denominator == 0:

        return 0

    return np.dot(a, b) / denominator


# ============================================================
# 7. MATCH STUDENT TO OPPORTUNITIES
# ============================================================

def find_matches(student_text):

    student_vector = create_vector(
        student_text
    )

    results = []

    for _, opportunity in opportunities.iterrows():

        opportunity_vector = create_vector(
            opportunity["description"]
        )

        similarity = cosine_similarity(
            student_vector,
            opportunity_vector
        )

        results.append({

            "title":
                opportunity["title"],

            "description":
                opportunity["description"],

            "similarity":
                float(similarity)
        })


    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return results


matches = find_matches(resume)


# ============================================================
# 8. DISPLAY SKILL PASSPORT
# ============================================================

print()
print("==============================================")
print("              SKILL PASSPORT")
print("==============================================")


print("\nDEMONSTRATED / MENTIONED SKILLS")
print("----------------------------------------------")

if student_skills:

    for skill in student_skills:

        print("•", skill.title())

else:

    print("No recognized skills found.")


print()
print(
    "Total recognized skills:",
    len(student_skills)
)


# ============================================================
# 9. DISPLAY OPPORTUNITY MATCHES
# ============================================================

print()
print("==============================================")
print("          OPPORTUNITY MATCHING")
print("==============================================")


for i, match in enumerate(matches[:5], 1):

    percentage = (
        match["similarity"]
        * 100
    )

    print()
    print(
        f"{i}. {match['title']}"
    )

    print(
        "   Match:",
        round(percentage, 2),
        "%"
    )


# ============================================================
# 10. FINISHED
# ============================================================

print()
print("==============================================")
print("             ANALYSIS COMPLETE")
print("==============================================")

print()
print("Resume → Skills → ML Representation →")
print("Opportunity Matching")

print()