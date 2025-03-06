import firebase_admin
from firebase_admin import credentials, firestore

# Load Firebase credentials
cred = credentials.Certificate(r"C:\Users\sehaj\OneDrive\Desktop\pdf bot\pdfenv\pdf-and-document-bot-firebase-adminsdk-fbsvc-2bf0b7d577.json")  # Path to your JSON key file
firebase_admin.initialize_app(cred)

# Initialize Firestore Database
db = firestore.client()
print("Firebase Firestore connected successfully!")
