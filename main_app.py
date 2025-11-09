# main_app.py — Direct Send Mode
import streamlit as st
import pandas as pd
import time, base64, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google_utils import get_credentials, read_sheet, update_row_status
from google.auth.transport.requests import Request

st.set_page_config(page_title="Email Automation", layout="wide")

# Config from secrets (or fallback)
SHEET_ID = st.secrets.get("SHEET_ID", "1Ucf2UY8QnLYpvRjdL7Q8rbAzr2ymJLkPsiPDKsJOeWQ")
SHEET_TAB = st.secrets.get("SHEET_TAB", "EM HiredNext")

st.title("📧 Email Automation — Live Send Mode")

# Authenticate
try:
    creds = get_credentials()
except Exception as e:
    st.error(f"Authentication required: {e}")
    st.stop()

# Read Google Sheet
try:
    values = read_sheet(SHEET_ID, SHEET_TAB, creds)
except Exception as e:
    st.error(f"Failed to read Google Sheet: {e}")
    st.stop()

if not values:
    st.info("No data found in sheet.")
    st.stop()

# Normalize data
max_cols = max(len(r) for r in values)
values = [r + [""] * (max_cols - len(r)) for r in values]

# Handle headers cleanly
headers = []
used = {}
for i, h in enumerate(values[0]):
    name = str(h).strip() if str(h).strip() else f"Extra_{i+1}"
    if name in used:
        used[name] += 1
        name = f"{name}_{used[name]}"
    else:
        used[name] = 1
    headers.append(name)

rows = values[1:]
df = pd.DataFrame(rows, columns=headers)

# Ensure Sent Status column exists
if "Sent Status" not in df.columns:
    df["Sent Status"] = ""

# Smart select: only those without "Sent Status"
df["Select"] = df["Sent Status"].astype(str).str.strip().eq("")

st.subheader("📄 Sheet Preview — Select recipients to send emails")
edited = st.data_editor(df, hide_index=True, use_container_width=True, key="editor")
selected_df = edited[edited["Select"] == True]

st.info(f"✅ {len(selected_df)} selected for sending.")

# Upload email template
uploaded_html = st.file_uploader("Upload Email Template (HTML)", type=["html", "htm"])
html_content = uploaded_html.read().decode("utf-8") if uploaded_html else None

if html_content:
    st.components.v1.html(html_content, height=400, scrolling=True)
else:
    st.warning("Please upload an HTML email template before sending.")

subject = st.text_input("Email Subject", "Your Subject Here")

# Confirm before sending
if st.button("🚀 Send Selected Emails"):
    if not html_content:
        st.error("Please upload an HTML file first.")
    elif selected_df.empty:
        st.warning("No recipients selected.")
    else:
        sender_email = creds._id_token.get("email") if getattr(creds, "_id_token", None) else None
        if not sender_email:
            st.error("Sender email not found. Make sure token.json is valid.")
            st.stop()

        st.info(f"📨 Sending emails directly from: {sender_email}")
        
        # Refresh OAuth token
        creds.refresh(Request())
        access_token = creds.token
        auth_string = f"user={sender_email}\1auth=Bearer {access_token}\1\1"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        server = None
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.ehlo()
            server.starttls()
            server.ehlo()
            code, resp = server.docmd("AUTH", "XOAUTH2 " + auth_b64)
            if code != 235:
                raise RuntimeError(f"SMTP auth failed: {resp}")

            st.success("✅ SMTP connected — starting live send.")
            total = len(selected_df)
            sent = 0
            prog = st.progress(0)
            status_box = st.empty()

            for idx, row in selected_df.iterrows():
                recipient = row.get("Email", "").strip()
                if not recipient:
                    continue

                name = str(row.get("Name", ""))
                body = html_content.replace("{{Name}}", name)

                msg = MIMEMultipart("alternative")
                msg["From"] = sender_email
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "html"))

                try:
                    server.sendmail(sender_email, recipient, msg.as_string())
                    status, err = "✅ Sent", ""
                    sent += 1
                    status_box.success(f"✅ Sent to {recipient}")
                except Exception as e:
                    status, err = "❌ Failed", str(e)
                    status_box.error(f"❌ Failed to send to {recipient}: {e}")

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Update Google Sheet with result
                try:
                    update_row_status(SHEET_ID, SHEET_TAB, idx, creds, status, timestamp, err)
                except Exception as e:
                    st.warning(f"⚠️ Could not update row {idx+2}: {e}")

                prog.progress(sent / total)
                time.sleep(1)

            st.success(f"🎉 All done! {sent}/{total} emails sent successfully.")
        except Exception as e:
            st.error(f"Send error: {e}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
