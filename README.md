# Skill Passport

A browser-based prototype for building a skills passport, recording projects
and achievements, and finding campus opportunities.

## Free shared deployment setup

GitHub Pages only hosts the frontend. To enable shared accounts and persistent
profiles, deploy the FastAPI API on Render and connect it to a Neon PostgreSQL
database. The frontend is configured to call the Render service at
`https://skill-passport-api.onrender.com`; deploy the API before publishing the
frontend changes that remove the browser-only mode.

### Free-tier setup

1. Create a free PostgreSQL database on Neon and copy its connection string.
2. In Render, create a **Blueprint** from this repository and select the
   `render.yaml` configuration.
3. Set the Render service's `DATABASE_URL` environment variable to the Neon
   connection string. Do not commit the connection string to GitHub.
4. Deploy the service as `skill-passport-api` so the Pages frontend can reach
   `https://skill-passport-api.onrender.com`.
5. In the repository's **Settings → Pages**, select **GitHub Actions**.
   Pushes to `main` deploy the `static/` frontend.

The Render free web service may sleep while idle and take time to wake. Neon
provides the persistent database; do not replace it with the Render service's
temporary filesystem. This starter keeps shared application state in one
database record and is intended to run as a single API instance. Move to
transactional per-entity tables before scaling it to multiple instances.

The Pages deployment workflow publishes `static/` from `main`. Until the
Render service and Neon database are configured, keep the currently published
frontend in place; it is the browser-only version.

## Accounts and resume privacy

Accounts use password hashing and bearer-token sessions. Resume analysis
accepts `.txt`, text-based `.pdf`, and `.docx` files up to 10 MB. Uploaded
resumes are sent to the API for extraction; extracted text is saved to the
profile only after the user chooses **ADD TO PASSPORT**. Scanned PDFs need OCR,
and legacy `.doc` files must be saved as `.docx`. Do not upload documents
without permission to store their extracted text.

The public repository intentionally excludes the resume dataset, generated
model artifacts, local database, and sample resume because they may contain
personal or resume-derived information. The sample opportunity list is seeded
from `data/opportunities.csv`.
