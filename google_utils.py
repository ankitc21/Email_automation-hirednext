# google_utils.py
import os, base64, pickle, streamlit as st
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://mail.google.com/"
]

def bootstrap_secrets_to_files():
    """If Streamlit secrets contain base64 blobs, write local files at runtime."""
    s = st.secrets
    token_b64 = s.get("GOOGLE_TOKEN_B64")
    creds_b64 = s.get("GOOGLE_CREDENTIALS_B64")
    if token_b64 and not os.path.exists("token.json"):
        with open("token.json", "wb") as f:
            f.write(base64.b64decode(token_b64))
    if creds_b64 and not os.path.exists("scripts/client_secret.json"):
        os.makedirs("scripts", exist_ok=True)
        with open("scripts/client_secret.json", "w", encoding="utf-8") as f:
            f.write(base64.b64decode(creds_b64).decode("utf-8"))

def get_credentials():
    """Load token.json (created locally or bootstrapped from secrets) and refresh if needed."""
    try:
        bootstrap_secrets_to_files()
    except Exception:
        pass

    token_path = "token.json"
    creds = None
    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as t:
                creds = pickle.load(t)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as t:
                pickle.dump(creds, t)
        else:
            # On cloud we don't want interactive flow; instruct user to create token locally
            raise RuntimeError("No valid token found. Run scripts/get_refresh_token.py locally to create token.json.")
    return creds

def read_sheet(spreadsheet_id: str, tab_name: str, creds):
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=f"'{tab_name}'", majorDimension="ROWS").execute()
    return result.get("values", [])

def update_row_status(spreadsheet_id: str, tab_name: str, row_index: int, creds, status, timestamp, error_msg):
    service = build("sheets", "v4", credentials=creds)
    range_a1 = f"'{tab_name}'!F{row_index+2}:H{row_index+2}"
    body = {"values": [[status, timestamp, error_msg]]}
    service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=range_a1,
                                          valueInputOption="RAW", body=body).execute()
