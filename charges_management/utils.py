import os
import base64
from typing import List
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

from flask import render_template, abort, current_app
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

def get_creds():
    if not os.path.exists('token.json'):
        abort(500, description="token.json not found. Run oauth_setup.py first.")
    return Credentials.from_authorized_user_file('token.json', SCOPES)

def get_services():
    creds = get_creds()
    gmail = build('gmail', 'v1', credentials=creds)
    oauth2 = build('oauth2', 'v2', credentials=creds)
    return creds, gmail, oauth2

def get_account_info(oauth2_service):
    try:
        info = oauth2_service.userinfo().get().execute()
        email = info.get('email', '') if isinstance(info, dict) else ''
        name = info.get('name', '') if isinstance(info, dict) else ''
        return email, name
    except Exception as e:
        print(f"Error retrieving account info: {e}")
        return '', '', # Corrected to return two values

def render_owner(template_name: str, context: dict) -> str:
    return render_template(template_name, **context)

def send_message(gmail_service, recipients: List[str], subject: str, html_body: str, sender_email: str, sender_name: str):
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
