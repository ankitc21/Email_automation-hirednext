# scripts/get_refresh_token.py
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle, os

SCOPES = [
    
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDS_PATH = "D:\Hired Next\email_automation_app\credentials.json"  # put your downloaded OAuth JSON here (Desktop app)
if not os.path.exists(CREDS_PATH):
    raise FileNotFoundError(f"Put your OAuth client JSON at {CREDS_PATH} (Desktop app)")

flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
creds = flow.run_local_server(port=0)
with open("token.json", "wb") as f:
    pickle.dump(creds, f)
print("✅ token.json created in project root. Keep it safe.")
