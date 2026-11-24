import base64
import html
import os
import random
import time
from datetime import datetime
from pathlib import Path

import PyPDF2
import streamlit as st
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from fpdf import FPDF
from groq import Groq
from mailjet_rest import Client

from Gsheet import gsheet

load_dotenv()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_groq_client() -> Groq:
    """Returns an initialized Groq client or raises a clear configuration error."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured in .env.")
    return Groq(api_key=api_key)


def _latin1_safe(text: str) -> str:
    """Sanitizes Unicode text so FPDF latin-1 encoding never fails."""
    return text.encode("latin-1", "replace").decode("latin-1")


def inject_custom_css():
    st.markdown(
        """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700&family=Open+Sans:wght@400;600&display=swap');

        :root {
            --primary: #FF9F00;
            --secondary: #FFD700;
            --accent: #F3D87C;
            --background: #141B2D;
            --surface: #1F2940;
            --text-primary: #F1F5F9;
        }

        .stApp {
            background-color: var(--background);
            color: var(--text-primary);
            font-family: 'Open Sans', sans-serif;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--secondary) !important;
            font-family: 'Merriweather', serif;
        }

        .chat-bubble {
            padding: 1rem 1.25rem;
            border-radius: 1rem;
            margin: 0.75rem 0;
            max-width: 82%;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
            font-size: 0.95rem;
            line-height: 1.6;
            word-wrap: break-word;
            white-space: pre-wrap;
        }

        .user-bubble {
            background: var(--accent);
            color: #1A202C;
            margin-left: auto;
            border-bottom-right-radius: 0.25rem;
        }

        .bot-bubble {
            background: var(--surface);
            color: var(--text-primary);
            border: 1px solid rgba(255, 215, 0, 0.2);
            margin-right: auto;
            border-bottom-left-radius: 0.25rem;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


def init_session():
    session_defaults = {
        "documents": {},
        "selected_doc": None,
        "history": [],
        "view_mode": "Insights",
    }
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def process_document(uploaded_file) -> bool:
    """Extracts text/metadata from an uploaded PDF or TXT file and runs AI analysis."""
    try:
        doc_id = uploaded_file.file_id
        if doc_id in st.session_state.documents:
            return True

        raw_bytes = uploaded_file.getvalue()
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            st.error("File exceeds the 10 MB upload limit.")
            return False

        safe_name = Path(uploaded_file.name).name

        if uploaded_file.type == "application/pdf" or safe_name.lower().endswith(".pdf"):
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = "\n".join((page.extract_text() or "") for page in pdf_reader.pages)
            pdf_meta = pdf_reader.metadata or {}
            metadata = {
                "pages": len(pdf_reader.pages),
                "author": pdf_meta.get("/Author", "Unknown"),
                "created": pdf_meta.get("/CreationDate", "Unknown"),
                "modified": pdf_meta.get("/ModDate", "Unknown"),
            }
        else:
            text = raw_bytes.decode("utf-8", errors="replace")
            metadata = {
                "pages": "N/A",
                "author": "Unknown",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "modified": "N/A",
            }

        if not text.strip():
            st.warning(f"No readable text found in {safe_name}.")
            return False

        st.session_state.documents[doc_id] = {
            "name": safe_name,
            "content": text,
            "metadata": metadata,
            "analysis": {},
        }

        with st.spinner(f"Analyzing {safe_name}..."):
            doc_content = text[:12000]
            st.session_state.documents[doc_id]["analysis"] = {
                "risk_score": random.randint(20, 80),
                "summary": get_ai_response(
                    doc_content,
                    "Provide a comprehensive 5-point executive summary with bold headings using **",
                ),
                "risks": get_ai_response(
                    doc_content,
                    "Identify and explain top 5 risks with:\n1. Risk title in bold\n2. Severity score (1-5)\n3. Explanation",
                ),
                "recommendations": get_ai_response(
                    doc_content,
                    "Provide 5 detailed recommendations with:\n1. Recommendation title in bold\n2. Implementation steps\n3. Priority level",
                ),
            }

        st.session_state.selected_doc = doc_id
        return True
    except Exception as e:
        st.error(f"Error processing document: {str(e)}")
        return False


def generate_pdf_report(doc_id: str) -> bytes:
    """Generates a PDF legal analysis report for the selected document."""
    doc = st.session_state.documents[doc_id]
    analysis = doc["analysis"]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_xy(20, 15)

    pdf.set_font("Times", "B", size=18)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 8, txt="Legal Analysis Report", ln=1, align="C")

    pdf.set_font("Times", "I", size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, txt=_latin1_safe(f"Document: {doc['name']}"), ln=1, align="C")
    pdf.cell(
        0,
        6,
        txt=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ln=1,
        align="C",
    )
    pdf.ln(4)

    sections = [
        ("Executive Summary", analysis.get("summary", "No summary available.")),
        ("Risk Assessment", analysis.get("risks", "No risk assessment available.")),
        (
            "Recommendations",
            analysis.get("recommendations", "No recommendations available."),
        ),
    ]
    for title, body in sections:
        pdf.set_font("Times", "B", size=14)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 7, txt=title, ln=1)
        pdf.set_font("Times", "", size=10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, txt=_latin1_safe(body))
        pdf.ln(3)

    pdf.set_y(-15)
    pdf.set_font("Times", "I", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 6, txt="Confidential - For Internal Use Only", align="C")

    return pdf.output(dest="S").encode("latin-1")


def get_ai_response(context: str, prompt: str, max_tokens: int = 1500) -> str:
    """Queries Groq LLM with legal analysis formatting instructions."""
    system_prompt = (
        "You are a legal expert assistant. Format responses with:\n"
        "- Clear section headers in **bold**\n"
        "- Bullet points for lists\n"
        "- Numbered steps when appropriate\n"
        "- Risk scores (1-5) for risk items\n"
        "- Priority levels for recommendations"
    )

    try:
        client = _get_groq_client()
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append(
                {
                    "role": "user",
                    "content": f"Document Content: {context[:12000]}\n\n{prompt}",
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            messages=messages,
            model="mixtral-8x7b-32768",
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error processing request: {str(e)}"


def send_email_report(recipient: str, doc_id: str) -> None:
    """Sends the generated PDF report and original document via Mailjet."""
    api_key = os.getenv("EMAIL_API_KEY", "").strip()
    api_secret = os.getenv("EMAIL_API_SECRET", "").strip()
    sender_email = os.getenv("EMAIL_FROM", "noreply@legalassistant.local").strip()

    if not api_key or not api_secret:
        raise RuntimeError("EMAIL_API_KEY and EMAIL_API_SECRET must be set in .env.")

    valid = validate_email(recipient)
    doc_data = st.session_state.documents[doc_id]
    original_doc_name = doc_data["name"]
    safe_doc_name = html.escape(original_doc_name)

    logo_html = ""
    logo_path = Path("assets/logo.jpeg")
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
        logo_html = (
            f'<img src="data:image/jpeg;base64,{logo_b64}" '
            'alt="AI Legal Assistant Logo" style="max-width: 180px; margin-bottom: 16px;">'
        )

    report = generate_pdf_report(doc_id)
    report_name = f"{original_doc_name}_analysis_report.pdf"
    original_doc_content = doc_data["content"].encode("utf-8")
    content_type = (
        "application/pdf"
        if original_doc_name.lower().endswith(".pdf")
        else "text/plain; charset=utf-8"
    )

    risk_score = doc_data["analysis"].get("risk_score", 50)
    risk_label = (
        "urgent attention required" if risk_score > 70 else "moderate risk level"
    )

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
            <div style="max-width: 600px; margin: 0 auto;">
                {logo_html}
                <h2 style="color: #2A2F4F;">Legal Document Analysis Report</h2>
                <p>Dear Client,</p>
                <p>We have completed the analysis of your document:
                <strong>{safe_doc_name}</strong>. Please review the attached report.</p>
                <h3 style="color: #2A2F4F;">Risk Overview</h3>
                <p>Risk score: <strong>{risk_score}/100</strong> ({risk_label}).</p>
                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee;">
                    <p>Best regards,<br><strong>AI Legal Assistant</strong></p>
                </div>
            </div>
        </body>
    </html>
    """

    mailjet = Client(auth=(api_key, api_secret), version="v3.1")
    data = {
        "Messages": [
            {
                "From": {"Email": sender_email, "Name": "AI Legal Assistant"},
                "To": [{"Email": valid.email}],
                "Subject": f"Legal Analysis Report: {original_doc_name}",
                "HTMLPart": html_content,
                "Attachments": [
                    {
                        "ContentType": "application/pdf",
                        "Filename": report_name,
                        "Base64Content": base64.b64encode(report).decode(),
                    },
                    {
                        "ContentType": content_type,
                        "Filename": original_doc_name,
                        "Base64Content": base64.b64encode(original_doc_content).decode(),
                    },
                ],
            }
        ]
    }
    result = mailjet.send.create(data=data)
    if result.status_code != 200:
        raise RuntimeError(
            result.json().get("ErrorMessage", f"HTTP {result.status_code}")
        )


def main():
    st.set_page_config(
        page_title="AI Legal Assistant", page_icon="⚖️", layout="wide"
    )
    inject_custom_css()
    init_session()

    st.markdown(
        """
        <div style="text-align: center; padding: 0.5rem 0 1.5rem 0;">
            <h1 style="font-size: 2.6rem; margin-bottom: 0.25rem;">⚖️ AI Legal Assistant</h1>
            <p style="color: #F3D87C; font-size: 1.05rem; margin: 0;">
                AI-Powered Legal Document Analysis &amp; Risk Assessment Suite
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### ⚖️ Documents")
        uploaded_files = st.file_uploader(
            "Upload legal documents",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            help="Upload PDF or TXT legal documents (max 10 MB each)",
            label_visibility="collapsed",
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.file_id not in st.session_state.documents:
                    process_document(uploaded_file)

        if st.session_state.documents:
            for doc_id, doc_data in st.session_state.documents.items():
                if st.button(
                    doc_data["name"],
                    key=f"doc_{doc_id}",
                    use_container_width=True,
                    type=(
                        "primary"
                        if st.session_state.selected_doc == doc_id
                        else "secondary"
                    ),
                ):
                    st.session_state.selected_doc = doc_id

            st.markdown("---")

            if st.session_state.selected_doc:
                doc_id = st.session_state.selected_doc
                report = generate_pdf_report(doc_id)
                st.download_button(
                    "💾 Download PDF Report",
                    report,
                    file_name=f"{st.session_state.documents[doc_id]['name']}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

                if st.button("📄 Export to Google Sheet", use_container_width=True):
                    try:
                        gsheet(st.session_state.documents[doc_id]["content"])
                        st.success("Analysis exported to Google Sheets.")
                    except Exception as e:
                        st.error(f"Google Sheets export failed: {str(e)}")

            st.markdown("---")
            with st.expander("📧 Email Report"):
                email = st.text_input("Recipient Email")
                if st.button("Send Report", use_container_width=True):
                    if not st.session_state.selected_doc:
                        st.warning("Please select a document first.")
                    else:
                        try:
                            send_email_report(email, st.session_state.selected_doc)
                            st.success("Report and document sent successfully!")
                        except EmailNotValidError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Error sending email: {str(e)}")

        st.markdown("---")
        if st.button("🗑️ Clear Session", use_container_width=True):
            st.session_state.documents = {}
            st.session_state.selected_doc = None
            st.session_state.history = []
            st.rerun()

    col1, col2 = st.columns([1, 2], gap="medium")

    with col1:
        st.markdown("### 📑 Document Insights")
        st.session_state.view_mode = st.radio(
            "View Mode",
            ["Insights", "Document Preview"],
            horizontal=True,
        )

        if st.session_state.selected_doc:
            doc = st.session_state.documents[st.session_state.selected_doc]
            if st.session_state.view_mode == "Insights":
                analysis = doc["analysis"]
                with st.expander("🔍 Metadata", expanded=True):
                    st.write(f"**Author:** {doc['metadata']['author']}")
                    st.write(f"**Created:** {doc['metadata']['created']}")
                    st.write(f"**Modified:** {doc['metadata']['modified']}")
                    st.write(f"**Pages:** {doc['metadata']['pages']}")

                with st.expander("📝 Summary", expanded=True):
                    st.markdown(analysis.get("summary", "No summary available."))

                with st.expander("⚠️ Risks"):
                    st.markdown(analysis.get("risks", "No risk analysis available."))

                with st.expander("💡 Recommendations"):
                    st.markdown(
                        analysis.get("recommendations", "No recommendations available.")
                    )
            else:
                st.markdown(f"#### {doc['name']}")
                preview = doc["content"][:10000]
                if len(doc["content"]) > 10000:
                    preview += "..."
                st.text_area(
                    "Content",
                    value=preview,
                    height=550,
                    label_visibility="collapsed",
                )
        else:
            st.info("Upload a PDF or TXT legal document in the sidebar to begin.")

    with col2:
        st.markdown("### 💬 Legal Assistant")
        with st.container(height=620):
            if not st.session_state.history:
                st.caption(
                    "Ask questions about your selected document or general legal concepts."
                )
            for msg in st.session_state.history:
                bubble_class = (
                    "user-bubble" if msg["role"] == "user" else "bot-bubble"
                )
                icon = "👤" if msg["role"] == "user" else "⚖️"
                label = "You" if msg["role"] == "user" else "Legal AI"
                safe_content = html.escape(msg["content"])
                st.markdown(
                    f"""
                    <div class="chat-bubble {bubble_class}">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span>{icon}</span>
                            <strong>{label}</strong>
                        </div>
                        {safe_content}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        user_input = st.chat_input("Type your legal query...")
        if user_input:
            st.session_state.history.append({"role": "user", "content": user_input})
            with st.spinner("Analyzing..."):
                start_time = time.time()
                if st.session_state.selected_doc:
                    context = st.session_state.documents[
                        st.session_state.selected_doc
                    ]["content"]
                    response = get_ai_response(context, user_input)
                elif any(
                    word in user_input.lower() for word in ("hi", "hello", "hey")
                ):
                    response = (
                        "Hello! I'm your legal AI assistant. "
                        "Upload a document or ask a legal question to get started."
                    )
                else:
                    response = get_ai_response("", user_input)

                elapsed = time.time() - start_time
                if elapsed > 3:
                    st.toast(f"Response generated in {elapsed:.1f}s", icon="⏳")

                st.session_state.history.append(
                    {"role": "assistant", "content": response}
                )
                st.rerun()


if __name__ == "__main__":
    main()
