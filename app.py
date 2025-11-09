import streamlit as st
import pandas as pd
import os
import pickle
import time
import base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Email Automation", layout="wide")

# ==========================================
# 🔐 Decode credentials from Streamlit Secrets
# ==========================================
def write_temp_json(var_name, file_name):
    """Decode base64 strings from Streamlit Secrets into local JSON files."""
    if var_name in st.secrets:
        data = base64.b64decode(st.secrets[var_name])
        with open(file_name, "wb") as f:
            f.write(data)

# Create temp credentials if available
write_temp_json("CREDENTIALS_BASE64", "credentials.json")
write_temp_json("TOKEN_BASE64", "token.json")

# Default fallback values (for local dev)
DEFAULT_SHEET_ID = "1Ucf2UY8QnLYpvRjdL7Q8rbAzr2ymJLkPsiPDKsJOeWQ"
DEFAULT_SHEET_TAB = "Email_Campaign"

# Load from secrets (if running on Streamlit Cloud)
SHEET_ID = st.secrets.get("SHEET_ID", DEFAULT_SHEET_ID)
SHEET_TAB = st.secrets.get("SHEET_TAB", DEFAULT_SHEET_TAB)

# Scopes for Gmail + Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://mail.google.com/"
]

st.title("📧 Gmail + Google Sheets Email Automation (Smart Selective Send)")

# ---------------- GOOGLE AUTH ----------------
def get_credentials():
    creds = None
    token_path = "token.json"

    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        except (EOFError, pickle.UnpicklingError):
            st.error("⚠️ Corrupted token.json detected. Delete and re-authenticate.")
            st.stop()

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
        else:
            st.error("No valid credentials found. Run the local auth script again.")
            st.stop()

    return creds


creds = get_credentials()

# ---------------- GOOGLE SHEETS ----------------
try:
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SHEET_TAB}'",
        majorDimension="ROWS"
    ).execute()
    values = result.get("values", [])
except Exception as e:
    st.error(f"Failed to read Google Sheet: {e}")
    st.stop()

if not values:
    st.error("No data found in sheet.")
    st.stop()

# Normalize all rows
max_cols = max(len(row) for row in values)
values = [row + [""] * (max_cols - len(row)) for row in values]

# Clean up headers
clean_headers = []
used = {}
for i, h in enumerate(values[0]):
    name = h.strip() if h.strip() else f"Extra_{i+1}"
    if name in used:
        used[name] += 1
        name = f"{name}_{used[name]}"
    else:
        used[name] = 1
    clean_headers.append(name)

rows = values[1:]
df = pd.DataFrame(rows, columns=clean_headers)

# ---------------- SHEET PREVIEW + SELECTION ----------------
st.subheader("📄 Sheet Preview & Smart Selection")

# Normalize Sent Status column (ensure exists)
if "Sent Status" not in df.columns:
    df["Sent Status"] = ""

# Automatically select only those whose Sent Status is blank
df["Select"] = df["Sent Status"].astype(str).str.strip().eq("")

edited_df = st.data_editor(
    df,
    hide_index=True,
    use_container_width=True,
    key="email_table"
)

selected_df = edited_df[edited_df["Select"] == True]
selected_count = len(selected_df)
st.info(f"✅ {selected_count} recipient(s) selected for sending.")

# ---------------- TEMPLATE UPLOAD ----------------
st.subheader("Upload Email Template (HTML)")
uploaded_html = st.file_uploader("Choose an HTML file", type=["html", "htm"])
html_content = uploaded_html.read().decode("utf-8") if uploaded_html else None
if html_content:
    st.components.v1.html(html_content, height=400, scrolling=True)
else:
    st.info("Please upload an HTML file to preview/send.")

subject = st.text_input("Email Subject", "Your Subject Here")

# ---------------- SEND EMAILS ----------------
if st.button("🚀 Send Selected Emails"):
    if not html_content:
        st.error("Please upload an HTML file.")
    elif selected_count == 0:
        st.warning("No recipients selected. Please select at least one email.")
    else:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        sender_email = creds._id_token.get("email") if creds._id_token else "ankit.c@hirednext.info"
        st.info(f"Using Gmail account: {sender_email}")

        creds.refresh(Request())
        access_token = creds.token

        # Build OAuth2 string
        auth_string = f"user={sender_email}\1auth=Bearer {access_token}\1\1"
        auth_bytes = base64.b64encode(auth_string.encode())

        server = None
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()

            code, response = server.docmd("AUTH", "XOAUTH2 " + auth_bytes.decode())
            if code != 235:
                raise Exception(f"OAuth2 authentication failed: {response}")

            st.success("✅ Gmail SMTP connection established!")

            total_recipients = len(selected_df)
            sent_count = 0
            progress = st.progress(0)
            status_placeholder = st.empty()

            for idx, row in selected_df.iterrows():
                recipient = row.get("Email", "").strip()
                if not recipient:
                    continue

                msg = MIMEMultipart("alternative")
                msg["From"] = sender_email
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(html_content, "html"))

                try:
                    server.sendmail(sender_email, recipient, msg.as_string())
                    status = "✅ Sent"
                    err = ""
                    sent_count += 1
                    status_placeholder.success(f"✅ Sent to {recipient}")
                except Exception as e:
                    status = "❌ Failed"
                    err = str(e)
                    status_placeholder.error(f"❌ Failed to send to {recipient}: {e}")

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    sheet.values().update(
                        spreadsheetId=SHEET_ID,
                        range=f"'{SHEET_TAB}'!F{idx+2}:H{idx+2}",
                        valueInputOption="RAW",
                        body={"values": [[status, timestamp, err]]}
                    ).execute()
                except Exception as e:
                    st.warning(f"⚠️ Could not update row {idx+2}: {e}")

                progress.progress((sent_count) / total_recipients)
                time.sleep(1)

            st.success(f"🎉 All done! Sent {sent_count}/{total_recipients} selected emails successfully.")

        except Exception as e:
            st.error(f"SMTP connection or authentication failed: {e}")

        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass
