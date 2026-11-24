import os

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from langchain.text_splitter import CharacterTextSplitter
from langchain_groq import ChatGroq

load_dotenv()

MODEL_NAME = "llama-3.2-11b-vision-preview"


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured in .env.")
    return ChatGroq(groq_api_key=api_key, model_name=MODEL_NAME)


def detect_risks_and_recommendations(text_chunks):
    """Analyzes text chunks and extracts risks and recommendations."""
    llm = _get_llm()
    results = []
    for chunk in text_chunks:
        prompt = (
            f"Analyze the following text and provide a structured response:\n\n"
            f"Text: {chunk}\n\n"
            f"Provide the following details:\n"
            f"- Risks: Summarize potential risks, issues, or hidden dependencies clearly.\n"
            f"- Recommendations: Suggest practical, clear, and actionable recommendations to mitigate the risks.\n\n"
            f"Output format:\n"
            f"Risks: <List the risks in simple points>\n"
            f"Recommendations: <List the recommendations in simple points>"
        )
        response = llm.invoke(prompt)
        response_text = response.content.strip()
        risks, recommendations = "No risks identified.", "No recommendations provided."

        if "Risks:" in response_text and "Recommendations:" in response_text:
            try:
                risks_start = response_text.index("Risks:") + len("Risks:")
                recommendations_start = response_text.index("Recommendations:")
                risks = response_text[risks_start:recommendations_start].strip()
                recommendations = response_text[
                    recommendations_start + len("Recommendations:") :
                ].strip()
            except ValueError:
                pass

        results.append(
            {
                "context": chunk,
                "risks": risks,
                "recommendations": recommendations,
            }
        )
    return results


def gsheet(file_text: str):
    """Exports document risk analysis to the configured Google Sheet."""
    service_account_file = os.getenv(
        "GOOGLE_CREDENTIALS_FILE", "gcredentials.json"
    ).strip()
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()

    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SPREADSHEET_ID is not configured in .env.")
    if not os.path.exists(service_account_file):
        raise FileNotFoundError(
            f"Google service account file not found: {service_account_file}"
        )

    text_splitter = CharacterTextSplitter(
        separator="\n", chunk_size=1000, chunk_overlap=20
    )
    texts = text_splitter.split_text(file_text)
    results = detect_risks_and_recommendations(texts)

    credentials = Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=credentials)
    sheet = service.spreadsheets()

    values = [["Context", "Risks", "Recommendations"]]
    for result in results:
        values.append([result["context"], result["risks"], result["recommendations"]])

    body = {"values": values}
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body=body,
    ).execute()
