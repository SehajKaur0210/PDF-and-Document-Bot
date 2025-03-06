from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
import pdfplumber
import io
import textwrap
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from jinja2 import Template
import os

# Google Drive API Imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Download NLTK resources
nltk.download('punkt')

app = FastAPI()

# Google Drive Credentials
DRIVE_FOLDER_ID = "165p81zX0V5TIzbb4-ZrcKBgj2W3zX0CL"  # 🔹 Replace with your Google Drive folder ID
SERVICE_ACCOUNT_FILE = r"C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\pdf-bot-project-f2dbe8bed928.json"  # 🔹 Path to your Google API credentials

# Authenticate Google Drive
def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

drive_service = authenticate_drive()

# HTML Template for Upload Form & Displaying Extracted Text
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Processing & Google Drive Upload</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 20px; }
        h2 { color: #333; }
        form { margin: 20px auto; padding: 20px; border: 1px solid #ccc; width: 50%; border-radius: 10px; }
        input { padding: 10px; margin-top: 10px; }
        button { background-color: #007BFF; color: white; padding: 10px 15px; border: none; cursor: pointer; }
        pre { text-align: left; background: #f4f4f4; padding: 15px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
    <h2>Upload a PDF File</h2>
    <form action="/upload-pdf/" enctype="multipart/form-data" method="post">
        <input type="file" name="file" accept="application/pdf" required>
        <button type="submit">Upload & Process</button>
    </form>
    
    {% if extracted_text %}
        <h2>📄 Extracted Text</h2>
        <pre>{{ extracted_text }}</pre>

        <h2>📝 Chunked Text (Each 300 Characters)</h2>
        {% for chunk in chunks %}
            <pre>{{ chunk }}</pre>
        {% endfor %}

        <h2>🔹 Tokenized Words</h2>
        <pre>{{ tokenized_words }}</pre>

        <h2>🔸 Tokenized Sentences</h2>
        <pre>{{ tokenized_sentences }}</pre>

        <h2>✅ Files Uploaded to Google Drive</h2>
        <p>📂 PDF File: <a href="{{ pdf_drive_link }}" target="_blank">View on Drive</a></p>
        <p>📜 Processed Text File: <a href="{{ text_drive_link }}" target="_blank">View on Drive</a></p>
    {% endif %}
</body>
</html>
"""

# 📌 Extract text from a PDF
def extract_text_from_pdf(pdf_bytes):
    text = ""
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

# 📌 Chunking function (splits text into 300-character parts)
def chunk_text(text, chunk_size=300):
    return textwrap.wrap(text, width=chunk_size)

# 📌 Tokenization function
def tokenize_text(text):
    words = word_tokenize(text)  # Tokenize words
    sentences = sent_tokenize(text)  # Tokenize sentences
    return words, sentences

# 📌 Save Text Data to a File
def save_text_to_file(file_name, extracted_text, chunks, tokenized_words, tokenized_sentences):
    file_path = f"./{file_name}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("📄 Extracted Text:\n")
        f.write(extracted_text + "\n\n")

        f.write("📝 Chunked Text:\n")
        for chunk in chunks:
            f.write(chunk + "\n\n")

        f.write("🔹 Tokenized Words:\n")
        f.write(", ".join(tokenized_words) + "\n\n")

        f.write("🔸 Tokenized Sentences:\n")
        f.write(" | ".join(tokenized_sentences) + "\n")

    return file_path

# 📌 Upload a File to Google Drive
def upload_to_drive(file_path, file_name, mime_type):
    file_metadata = {
        "name": file_name,
        "parents": [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype=mime_type)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded_file.get("id")
    return f"https://drive.google.com/file/d/{file_id}/view"

# 📌 Upload PDF & Process Text
@app.post("/upload-pdf/", response_class=HTMLResponse)
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    # Save PDF locally before processing
    pdf_path = f"./{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())  # Save PDF to disk

    # Extract text from PDF
    with open(pdf_path, "rb") as pdf_bytes:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    
    if not extracted_text:
        return Template(HTML_TEMPLATE).render(extracted_text="No text found in PDF.", chunks=[], tokenized_words=[], tokenized_sentences=[])

    # Perform chunking and tokenization
    chunks = chunk_text(extracted_text)
    tokenized_words, tokenized_sentences = tokenize_text(extracted_text)

    # Save extracted text, chunks, and tokenized data to a .txt file
    text_file_name = f"{file.filename}_processed"
    text_file_path = save_text_to_file(text_file_name, extracted_text, chunks, tokenized_words[:50], tokenized_sentences[:5])

    # Upload PDF & text file to Google Drive
    pdf_drive_link = upload_to_drive(pdf_path, file.filename, "application/pdf")
    text_drive_link = upload_to_drive(text_file_path, text_file_name + ".txt", "text/plain")

    # Cleanup: Remove local files after uploading
    os.remove(pdf_path)
    os.remove(text_file_path)

    return Template(HTML_TEMPLATE).render(
        extracted_text=extracted_text,
        chunks=chunks,
        tokenized_words=", ".join(tokenized_words[:50]),  
        tokenized_sentences=" | ".join(tokenized_sentences[:5]),  
        pdf_drive_link=pdf_drive_link,
        text_drive_link=text_drive_link
    )

@app.get("/", response_class=HTMLResponse)
async def home():
    return Template(HTML_TEMPLATE).render()
