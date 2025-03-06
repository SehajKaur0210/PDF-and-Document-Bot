from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
import pdfplumber
import io
import textwrap
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from PIL import Image
import easyocr
import numpy as np
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Initialize FastAPI app
app = FastAPI()
nltk.download('punkt')

# Google Drive API Credentials
DRIVE_FOLDER_ID = "165p81zX0V5TIzbb4-ZrcKBgj2W3zX0CL"  # Replace with your actual folder ID
SERVICE_ACCOUNT_FILE = r"C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\PDF-and-Document-Bot\pdf-bot-project-f2dbe8bed928.json" # Replace with your JSON credentials file

def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

drive_service = authenticate_drive()

def upload_to_drive(file_path, file_name, mime_type):
    file_metadata = {"name": file_name, "parents": [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(file_path, mimetype=mime_type)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return f"https://drive.google.com/file/d/{uploaded_file['id']}/view"

def extract_text_from_pdf(pdf_bytes):
    text = ""
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

def extract_text_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    img_cv = np.array(image)
    result = reader.readtext(img_cv, detail=0)
    return "\n".join(result).strip()

def process_text(text):
    words = word_tokenize(text)
    sentences = sent_tokenize(text)
    chunks = textwrap.wrap(text, width=300)
    return words, sentences, chunks

def save_text_to_file(file_name, extracted_text, chunks, words, sentences):
    file_path = f"{file_name}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Extracted Text:\n" + extracted_text + "\n\n")
        f.write("Chunked Text:\n" + "\n".join(chunks) + "\n\n")
        f.write("Tokenized Words:\n" + ", ".join(words[:50]) + "\n\n")
        f.write("Tokenized Sentences:\n" + " | ".join(sentences[:5]) + "\n")
    return file_path

@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    pdf_path = file.filename
    with open(pdf_path, "wb") as f:
        f.write(await file.read())
    
    drive_link = upload_to_drive(pdf_path, file.filename, "application/pdf")
    
    with open(pdf_path, "rb") as pdf_bytes:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    
    words, sentences, chunks = process_text(extracted_text)
    text_file_path = save_text_to_file(file.filename, extracted_text, chunks, words, sentences)
    processed_drive_link = upload_to_drive(text_file_path, file.filename + "_processed.txt", "text/plain")
    
    os.remove(pdf_path)
    os.remove(text_file_path)
    
    return {"original_file": drive_link, "processed_file": processed_drive_link}

@app.post("/upload-image/")
async def upload_image(file: UploadFile = File(...)):
    image_path = file.filename
    with open(image_path, "wb") as img:
        img.write(await file.read())
    
    drive_link = upload_to_drive(image_path, file.filename, "image/png")
    
    with open(image_path, "rb") as img_bytes:
        extracted_text = extract_text_from_image(img_bytes.read())
    
    words, sentences, chunks = process_text(extracted_text)
    text_file_path = save_text_to_file(file.filename, extracted_text, chunks, words, sentences)
    processed_drive_link = upload_to_drive(text_file_path, file.filename + "_processed.txt", "text/plain")
    
    os.remove(image_path)
    os.remove(text_file_path)
    
    return {"original_file": drive_link, "processed_file": processed_drive_link}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <h2>Upload a PDF or Image</h2>
    <form action="/upload-pdf/" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept="application/pdf">
        <button type="submit">Upload PDF</button>
    </form>
    <form action="/upload-image/" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept="image/*">
        <button type="submit">Upload Image</button>
    </form>
    """
