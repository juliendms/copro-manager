# app.py
import os
import re
import base64
from typing import List
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from fastapi import FastAPI, HTTPException
from jinja2 import Environment, FileSystemLoader
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SHEET_NAME = os.getenv('SHEET_NAME', 'Owners')  # expected pattern: "Name - YEAR - YYYY-MM-DD"
SUBJECT = os.getenv('SUBJECT', 'Appel de charges / fonds')

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

app = FastAPI()
env = Environment(loader=FileSystemLoader('templates'))

EMAIL_SPLIT_RE = re.compile(r'[,\;\s]+')


def get_creds():
    if not os.path.exists('token.json'):
        raise FileNotFoundError("token.json not found. Run oauth_setup.py first.")
    return Credentials.from_authorized_user_file('token.json', SCOPES)


def get_services():
    creds = get_creds()
    gmail = build('gmail', 'v1', credentials=creds)
    sheets = build('sheets', 'v4', credentials=creds)
    oauth2 = build('oauth2', 'v2', credentials=creds)
    return creds, gmail, sheets, oauth2


def get_account_info(oauth2_service):
    try:
        info = oauth2_service.userinfo().get().execute()
        email = info.get('email', '') if isinstance(info, dict) else ''
        name = info.get('name', '') if isinstance(info, dict) else ''
        return email, name
    except Exception:
        return '', ''


def extract_emails(raw: str) -> List[str]:
    if not raw:
        return []
    parts = EMAIL_SPLIT_RE.split(raw)
    emails = [p.strip() for p in parts if p and is_probable_email(p.strip())]
    return emails


def is_probable_email(s: str) -> bool:
    return '@' in s and '.' in s and ' ' not in s


def col_letter(index0: int) -> str:
    result = ''
    i = index0
    while True:
        result = chr((i % 26) + ord('A')) + result
        i = i // 26 - 1
        if i < 0:
            break
    return result


def parse_sheet_for_year_and_date(sheet_name: str):
    m = re.search(r'-\s*(\d{4})\s*-\s*(\d{4}-\d{2}-\d{2})\s*$', sheet_name)
    if m:
        return m.group(1), m.group(2)
    return '', ''


def parse_amount_raw(s):
    if not s:
        return 0.0
    s = str(s).strip()
    s = s.replace('\u00A0', '')
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    s = re.sub(r'[^\d\.\-]', '', s)
    try:
        return float(s) if s != '' else 0.0
    except:
        return 0.0


def read_headers_and_rows(sheets_service, sheet_name):
    hr = sheets_service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!1:1"
    ).execute()
    headers = hr.get('values', [[]])[0]
    headers = [h.strip().lower() for h in headers]
    rr = sheets_service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A2:ZZ"
    ).execute()
    rows = rr.get('values', [])
    return headers, rows


def render_owner(template_name: str, context: dict) -> str:
    tmpl = env.get_template(template_name)
    return tmpl.render(**context)


def send_message(gmail_service, recipients: List[str], subject: str, html_body: str, sender_email: str, sender_name: str):
    # recipients: list -> To header becomes comma-separated
    to_header = ', '.join(recipients)
    if sender_name:
        encoded_name = str(Header(sender_name, 'utf-8'))
        from_header = formataddr((encoded_name, sender_email))
    else:
        from_header = sender_email

    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['To'] = to_header
    msg['From'] = from_header
    msg['Subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return gmail_service.users().messages().send(userId='me', body={'raw': raw}).execute()


@app.post("/send_all")
def send_all():
    if not SPREADSHEET_ID:
        raise HTTPException(status_code=500, detail="Missing SPREADSHEET_ID env var.")
    creds, gmail, sheets, oauth2 = get_services()

    account_email, account_name = get_account_info(oauth2)
    if not account_email:
        raise HTTPException(status_code=500, detail="Unable to retrieve account info via userinfo. Ensure token.json has correct scopes.")

    year_parsed, voting_date_parsed = parse_sheet_for_year_and_date(SHEET_NAME)
    headers, rows = read_headers_and_rows(sheets, SHEET_NAME)
    idx = {name: i for i, name in enumerate(headers)}

    if 'email' not in idx:
        raise HTTPException(status_code=400, detail=f"Missing required column 'email' in {SHEET_NAME} headers.")

    # compute total_budget as sum of all yearly_amount across all rows (non-empty rows counted)
    total_budget = 0.0
    ya_index = idx.get('yearly_amount', None)
    for row in rows:
        if ya_index is not None and ya_index < len(row):
            total_budget += parse_amount_raw(row[ya_index])

    updates = []
    processed = 0

    for row_offset, row in enumerate(rows, start=2):
        row_index = row_offset
        raw_email_cell = row[idx['email']].strip() if idx['email'] < len(row) and row[idx['email']] is not None else ''
        status = row[idx['status']].strip() if 'status' in idx and idx['status'] < len(row) and row[idx['status']] is not None else ''
        if not raw_email_cell or status.lower() == 'ok':
            continue

        def cell_val(col_name):
            i = idx.get(col_name)
            return (row[i].strip() if i is not None and i < len(row) and row[i] is not None else '')

        name = cell_val('name')
        lot = cell_val('lot')
        share = cell_val('share')
        yearly_amount = cell_val('yearly_amount')
        amount_due = cell_val('amount_due') if cell_val('amount_due') else yearly_amount

        context = {
            'title': SUBJECT,
            'name': name,
            'lot': lot,
            'share': share,
            'yearly_amount': yearly_amount,
            'amount_due': amount_due,
            'year': year_parsed,
            'voting_date': voting_date_parsed,
            'total_budget': "{:.2f}".format(total_budget)
        }
        html = render_owner('invoice.html', context)

        recipients = extract_emails(raw_email_cell)
        if not recipients:
            updates.append((row_index, 'ERROR: no valid email', ''))
            continue

        try:
            resp = send_message(gmail, recipients, SUBJECT, html, account_email, account_name)
            msg_id = resp.get('id') if isinstance(resp, dict) else ''
            updates.append((row_index, 'OK', datetime.utcnow().isoformat()))
            processed += 1
        except Exception as e:
            updates.append((row_index, f"ERROR: {str(e)[:120]}", ''))

    # batch write status and sent_at
    if updates:
        body = {'valueInputOption': 'RAW', 'data': []}
        status_idx = idx.get('status', len(headers))
        sent_at_idx = idx.get('sent_at', max(len(headers), status_idx + 1))
        for row_num, status_text, sent_at in updates:
            status_col = col_letter(status_idx)
            sent_col = col_letter(sent_at_idx)
            body['data'].append({
                'range': f"{SHEET_NAME}!{status_col}{row_num}",
                'values': [[status_text]]
            })
            body['data'].append({
                'range': f"{SHEET_NAME}!{sent_col}{row_num}",
                'values': [[sent_at]]
            })
        sheets.spreadsheets().values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

    return {
        "processed": processed,
        "total_budget": total_budget,
        "year": year_parsed,
        "voting_date": voting_date_parsed,
        "sender_email": account_email,
        "sender_name": account_name
    }
