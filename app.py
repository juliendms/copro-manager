import os
import base64
from email.mime.text import MIMEText
from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # optional .env

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SHEET_NAME = os.getenv('SHEET_NAME', 'Appels')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')  # must match authorized account
SUBJECT = os.getenv('SUBJECT', 'Appel de charges / fonds')

SCOPES = ['https://www.googleapis.com/auth/gmail.send',
          'https://www.googleapis.com/auth/spreadsheets']

app = FastAPI()
env = Environment(loader=FileSystemLoader('templates'))

def get_creds():
    return Credentials.from_authorized_user_file('token.json', SCOPES)

def get_services():
    creds = get_creds()
    gmail = build('gmail', 'v1', credentials=creds)
    sheets = build('sheets', 'v4', credentials=creds)
    return gmail, sheets

def render_owner(template_name, context):
    tmpl = env.get_template(template_name)
    return tmpl.render(**context)

def send_message(gmail_service, to_email, subject, html_body):
    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['To'] = to_email
    msg['From'] = SENDER_EMAIL
    msg['Subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return gmail_service.users().messages().send(userId='me', body={'raw': raw}).execute()

@app.post('/send_all')
def send_all():
    gmail, sheets = get_services()

    range_read = f"{SHEET_NAME}!A2:E"
    resp = sheets.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_read).execute()
    values = resp.get('values', [])

    updates = []

    for idx, row in enumerate(values, start=2):
        email = row[0].strip() if len(row) > 0 else ''
        name = row[1].strip() if len(row) > 1 else ''
        amount = row[2].strip() if len(row) > 2 else ''
        status = row[3].strip() if len(row) > 3 else ''

        if not email or status.lower() == 'ok':
            continue

        html = render_owner('invoice.html', {'name': name, 'amount': amount})
        try:
            send_message(gmail, email, SUBJECT, html)
            updates.append((idx, 'OK', datetime.utcnow().isoformat()))
        except Exception as e:
            updates.append((idx, f'ERROR: {str(e)[:120]}', ''))

    if updates:
        body = {'valueInputOption': 'RAW', 'data': []}
        for row_num, status_text, sent_at in updates:
            body['data'].append({'range': f"{SHEET_NAME}!D{row_num}", 'values': [[status_text]]})
            body['data'].append({'range': f"{SHEET_NAME}!E{row_num}", 'values': [[sent_at]]})
        sheets.spreadsheets().values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

    return {"processed": len(updates)}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
