from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
import pdfplumber
import io
import textwrap
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from jinja2 import Template
import os
from PIL import Image
import pytesseract
import cv2
import numpy as np
import subprocess

cmd = r'C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\tesseract-ocr-w64-setup-5.5.0.20241111.exe'
subprocess.run([cmd, "--version"], shell=True)

# Google Drive API Imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Download NLTK resources
nltk.download('punkt')

app = FastAPI()

# Configure Tesseract OCR path (Update this to your installation path)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\tesseract-ocr-w64-setup-5.5.0.20241111.exe"

# Google Drive Credentials
DRIVE_FOLDER_ID = "165p81zX0V5TIzbb4-ZrcKBgj2W3zX0CL"  # Replace with your Drive folder ID
SERVICE_ACCOUNT_FILE = r"C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\pdf-bot-project-f2dbe8bed928.json"  # Replace with your Google API credentials

# Authenticate Google Drive
def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

drive_service = authenticate_drive()

# 📌 Extract text from a PDF
def extract_text_from_pdf(pdf_bytes):
    text = ""
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

# 📌 Extract text from an image using OCR
def extract_text_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))

    # Convert image to OpenCV format for preprocessing
    img_cv = np.array(image)
    img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)  # Convert to grayscale
    img_cv = cv2.threshold(img_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]  # Binarization

    # Use Tesseract OCR to extract text
    text = pytesseract.image_to_string(img_cv)
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

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import PyPDF2
import nltk

# Initialize FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")  # Ensure templates folder exists

# Ensure nltk resources are downloaded
nltk.download("punkt")

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF file."""
    pdf_reader = PyPDF2.PdfReader(pdf_bytes)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n" if page.extract_text() else ""
    return text.strip()

def process_text(text):
    """Tokenize text into words and sentences, then create chunks."""
    words = nltk.word_tokenize(text)
    sentences = nltk.sent_tokenize(text)
    chunks = [words[i : i + 10] for i in range(0, len(words), 10)]  # Chunking in sets of 10 words
    return words, sentences, chunks

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the upload page."""
    return templates.TemplateResponse("template.html", {"request": request})

@app.post("/upload-pdf/", response_class=HTMLResponse)
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Handle PDF upload and process text."""
    pdf_path = f"./{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())  # Save the PDF

    # Extract text from PDF
    with open(pdf_path, "rb") as pdf_bytes:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    
    # Process text: tokenize & chunk
    words, sentences, chunks = process_text(extracted_text)

    # Convert chunks to readable format
    chunked_text = [" ".join(chunk) for chunk in chunks]

    return templates.TemplateResponse(
        "template.html",
        {
            "request": request,
            "extracted_text": extracted_text if extracted_text else "No text found.",
            "tokenized_words": words,
            "tokenized_sentences": sentences,
            "chunks": chunked_text,
        },
    )


    

# 📌 Upload Image & Process Text
@app.post("/upload-image/", response_class=HTMLResponse)
async def upload_image(request: Request, file: UploadFile = File(...)):
    image_bytes = await file.read()
    extracted_text = extract_text_from_image(image_bytes)

    if not extracted_text:
        return {"message": "No text found in image."}

    chunks = chunk_text(extracted_text)
    tokenized_words, tokenized_sentences = tokenize_text(extracted_text)

    text_file_name = f"{file.filename}_processed"
    text_file_path = save_text_to_file(text_file_name, extracted_text, chunks, tokenized_words[:50], tokenized_sentences[:5])

    image_path = f"./{file.filename}"
    with open(image_path, "wb") as img:
        img.write(image_bytes)

    image_drive_link = upload_to_drive(image_path, file.filename, "image/png")
    text_drive_link = upload_to_drive(text_file_path, text_file_name + ".txt", "text/plain")

    os.remove(image_path)
    os.remove(text_file_path)

    return {"image_drive_link": image_drive_link, "text_drive_link": text_drive_link}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """<h2>Upload a PDF or Image</h2>
              <form action="/upload-pdf/" method="post" enctype="multipart/form-data">
                  <input type="file" name="file" accept="application/pdf">
                  <button type="submit">Upload PDF</button>
              </form>
              <form action="/upload-image/" method="post" enctype="multipart/form-data">
                  <input type="file" name="file" accept="image/*">
                  <button type="submit">Upload Image</button>
              </form>"""
