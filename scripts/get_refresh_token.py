from google_auth_oauthlib.flow import InstalledAppFlow
import pickle, os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://mail.google.com/"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

if not os.path.exists(CREDENTIALS_FILE):
    raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}. Download it from Google Cloud Console (Desktop App).")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "wb") as token:
    pickle.dump(creds, token)

print("✅ token.json generated successfully — Gmail + Sheets access granted!")
