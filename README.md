# Skill Passport

A prototype for recording skills and matching student profiles with opportunities.

## Privacy and local data

This public repository contains the application source and the sample
`data/opportunities.csv` file. It intentionally excludes the resume dataset,
the generated model artifacts, the local database, and the sample resume
because those files may contain personal or resume-derived information.

The local prototype expects `data/resume_data.csv` to generate the model with
`inspect_data.py` or `simple_ml.py`. The API in `server.py` expects the
generated `model/tfidf_data.pkl`. Keep those files local and do not commit or
upload them.
