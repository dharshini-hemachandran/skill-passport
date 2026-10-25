import pandas as pd
import numpy as np
import os
import re
import math
import joblib


print("Loading dataset...")

df = pd.read_csv("data/resume_data.csv")

print("Dataset loaded!")
print("Rows:", len(df))


# Columns containing useful resume information
columns = [
    "career_objective",
    "skills",
    "degree_names",
    "major_field_of_studies",
    "professional_company_names",
    "positions",
    "responsibilities",
    "certification_skills",
    "extra_curricular_activity_types"
]


def combine_text(row):
    parts = []

    for column in columns:
        value = row[column]

        if pd.notna(value):
            parts.append(str(value))

    return " ".join(parts)


print("Combining resume information...")

df["profile_text"] = df.apply(combine_text, axis=1)

df = df[df["profile_text"].str.strip() != ""]

print("Usable profiles:", len(df))


# --------------------------------
# Simple text preprocessing
# --------------------------------

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


df["clean_text"] = df["profile_text"].apply(clean_text)


# --------------------------------
# Build vocabulary
# --------------------------------

print("Building vocabulary...")

documents = df["clean_text"].tolist()

word_counts = {}

for document in documents:
    words = set(document.split())

    for word in words:
        if len(word) > 2:
            word_counts[word] = word_counts.get(word, 0) + 1


# Keep useful words
vocabulary = {
    word: count
    for word, count in word_counts.items()
    if count >= 3
}


# Limit vocabulary size
vocabulary = sorted(
    vocabulary,
    key=word_counts.get,
    reverse=True
)[:5000]

word_to_index = {
    word: i
    for i, word in enumerate(vocabulary)
}


print("Vocabulary size:", len(vocabulary))


# --------------------------------
# TF-IDF
# --------------------------------

print("Creating TF-IDF representation...")


N = len(documents)

idf = np.zeros(len(vocabulary))


for word, index in word_to_index.items():

    count = 0

    for document in documents:
        if word in set(document.split()):
            count += 1

    idf[index] = math.log((N + 1) / (count + 1)) + 1


def create_vector(document):

    words = document.split()

    vector = np.zeros(len(vocabulary))

    total_words = len(words)

    if total_words == 0:
        return vector

    for word in words:

        if word in word_to_index:

            index = word_to_index[word]

            tf = words.count(word) / total_words

            vector[index] = tf * idf[index]

    return vector


# Use a smaller sample for tonight's prototype
sample_size = min(3000, len(documents))

print("Creating vectors for", sample_size, "profiles...")

vectors = np.array([
    create_vector(documents[i])
    for i in range(sample_size)
])


print("Vectors created!")

print("Vector shape:", vectors.shape)


# --------------------------------
# Save model data
# --------------------------------

os.makedirs("model", exist_ok=True)

np.save("model/tfidf_vectors.npy", vectors)

joblib.dump(
    {
        "vocabulary": vocabulary,
        "word_to_index": word_to_index,
        "idf": idf
    },
    "model/tfidf_data.pkl"
)


print()
print("================================")
print("ML PROCESS COMPLETE")
print("================================")
print("Profiles processed:", sample_size)
print("Features:", len(vocabulary))
print("Model files saved inside model/")