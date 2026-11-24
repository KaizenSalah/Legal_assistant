# AI Legal Assistant

An AI-powered Streamlit application for analyzing legal documents, identifying potential risks, generating structured PDF reports, exporting insights to Google Sheets, and emailing analysis summaries.

## Features

- **Document Upload & Parsing**: Upload PDF or TXT legal documents (up to 10 MB per file) with automatic metadata extraction.
- **Automated AI Analysis**: Uses Groq LLMs to generate an executive summary, top 5 risk items with severity scores (1–5), and prioritized recommendations.
- **Interactive Legal Chat**: Ask follow-up questions grounded in the currently selected document or general legal concepts.
- **PDF Report Generation**: Download formatted PDF analysis reports directly from the sidebar.
- **Google Sheets Export**: Chunk document text and export structured risk & recommendation rows to a configured Google Sheet.
- **Email Delivery**: Send the generated PDF report and original document to a recipient via Mailjet.

## Project Structure

- `app.py` — Main Streamlit application, UI, PDF generation, chat assistant, and Mailjet integration.
- `Gsheet.py` — LangChain text splitter, Groq risk extraction, and Google Sheets API export.
- `Legal_summary.ipynb` / `Risk_assessment.ipynb` — Exploratory notebooks for summarization and risk analysis.
- `tests/test_app.py` — Unit tests for PDF encoding safety and environment configuration guards.
- `.env.example` — Template of required environment variables.

## Setup

1. Clone the repository and enter the project directory:
   ```bash
   cd Legal_assistant
   ```
2. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. *(Optional)* Place your Google service account JSON file at `gcredentials.json` (gitignored) if you plan to use Google Sheets export.

## Environment Variables (`.env`)

| Variable | Description |
| --- | --- |
| `GROQ_API_KEY` | Groq API key used for document analysis and chat |
| `EMAIL_API_KEY` | Mailjet API key for sending email reports |
| `EMAIL_API_SECRET` | Mailjet API secret |
| `EMAIL_FROM` | Verified sender email address for Mailjet |
| `GOOGLE_CREDENTIALS_FILE` | Path to Google service account JSON (default: `gcredentials.json`) |
| `GOOGLE_SPREADSHEET_ID` | Target Google Sheet ID for exporting risk tables |

## Running & Testing

Start the Streamlit app:
```bash
streamlit run app.py
```

Run the test suite:
```bash
pytest
```

## Security Notes

- Never commit `.env` or `gcredentials.json` (both are listed in `.gitignore`).
- HTML output in chat bubbles and email templates is escaped to prevent HTML/script injection.
- Uploaded files are validated for size (10 MB max) and sanitized filenames before processing.
