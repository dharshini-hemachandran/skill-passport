# Skill Passport

A browser-based prototype for building a skills passport, recording projects
and achievements, and finding campus opportunities.

## GitHub Pages demo

The static site in `static/` runs without Python, an API server, or the private
resume dataset. It includes local student and opportunity-creator demos,
editable passports, challenges, opportunity posting and applications, and
on-device text-similarity matching.

To deploy:

1. Open the repository's **Settings → Pages**.
2. Set the build and deployment source to **GitHub Actions**.
3. Push to `main` (or manually run **Deploy GitHub Pages** under Actions).
4. Open `https://dharshini-hemachandran.github.io/skill-passport/`.

The workflow publishes `static/` as the site root. GitHub Pages serves this
frontend only; it does not run `server.py` or provide a shared database.

## Demo limitations and privacy

The Pages demo stores its profiles, resumes, opportunities, and activity in
the current browser's local storage. There is no secure authentication, cloud
sync, cross-device access, or shared candidate directory. Do not use real
passwords or sensitive personal information. Resume analysis supports `.txt`,
text-based `.pdf`, and `.docx` files in the browser. Scanned PDFs need OCR and
legacy `.doc` files must be saved as `.docx`. PDF.js and Mammoth are loaded
from jsDelivr; uploaded files are processed locally and are not sent to those
services.

The public repository intentionally excludes the resume dataset, generated
model artifacts, local database, and sample resume because they may contain
personal or resume-derived information. The demo uses its built-in sample
opportunities instead.
