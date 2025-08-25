# README — copro-manager

## What this does

Service that reads an Owners Google Sheet, renders per-owner HTML invoices and sends them from a Gmail account via the Gmail API. Multiple recipient addresses may be placed in the owner `email` cell (comma/semicolon/space separated). Status and sent timestamp are written back to the sheet.

## Quick prerequisites

* Python 3.10+
* Google Cloud account with a project you control
* A Gmail account used to send messages (interactive OAuth consent required)
* VSCode or terminal on your machine

---

## 1) GCP / Google setup (one-time)

1. Create or pick a Google Cloud Project.
2. Enable APIs:

   * Gmail API
   * Google Sheets API
3. Configure OAuth consent screen (external or internal depending on account).
4. Create OAuth 2.0 Credentials → **Desktop app** (or Web if you prefer). Download the JSON and save as `credentials.json` in the repo root.

   * Scopes required by the repo:

     ```
     https://www.googleapis.com/auth/gmail.send
     https://www.googleapis.com/auth/spreadsheets
     https://www.googleapis.com/auth/userinfo.email
     https://www.googleapis.com/auth/userinfo.profile
     openid
     ```
5. (Optional) If using an organization/internal app you may not need verification. For external apps and wide distribution follow GCP verification rules.

Security: never commit `credentials.json` or `token.json` to git.

---

## 2) Spreadsheet setup

1. Create a Google Sheet and a tab for owners. Default tab name expected by `.env` is `Owners` but you can set `SHEET_NAME` to any tab name following the pattern to extract year/voting date:

   ```
   <any> - <YEAR> - <YYYY-MM-DD>
   Example: Owners - 2025 - 2025-05-12
   ```

   Year and voting\_date are parsed from the sheet name if present.
2. Owners sheet header row (case-insensitive). Required:

   * `email` (can contain multiple addresses separated by comma/semicolon/space)
     Optional but recommended:
   * `name`, `lot`, `share`, `yearly_amount`, `amount_due`, `status`, `sent_at`
3. `yearly_amount` values are summed for `total_budget`. Empty rows are considered 0.

Template:

* Place your HTML template as `templates/invoice.html`.

---

## 3) Repo .env example

Create a `.env` file in repo root (copy `.env.example`) and set:

```
SPREADSHEET_ID=your_sheet_id_here
SHEET_NAME=Owners - 2025 - 2025-05-12
SUBJECT=Appel de charges - Copropriété
```

* `SPREADSHEET_ID` is the long ID from the sheet URL.
* No `SENDER_EMAIL` is required. Sender name and email are retrieved from Google via OAuth.

---

## 4) Local install and test (Windows PowerShell)

Open PowerShell in the repo root.

1. Create and activate venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If execution blocked:
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

2. Install packages:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

3. Place `credentials.json` in repo root.

4. Run the one-time OAuth flow to generate `token.json`:

```powershell
python oauth_setup.py
```

Follow the browser prompt and accept consent for the requested scopes. `token.json` is saved in the repo root.

> If you change scopes in the code you must re-run `python oauth_setup.py` to refresh `token.json`.

5. Start the server:

```powershell
uvicorn app:app --reload
```

6. Trigger sending (test first with a few rows):

```powershell
curl.exe -X POST http://127.0.0.1:8000/send_all
```

Server returns JSON with `processed`, `total_budget`, `year`, `voting_date`, `sender_email`, `sender_name`.

7. Verify:

* Inbox(es) of recipients show the message.
* Check the Owners sheet `status` and `sent_at` cells updated.

---

## 5) Notes, tips and troubleshooting

* If you see `Insufficient Permission` or userinfo empty re-run `python oauth_setup.py` to regenerate token with correct scopes.
* If clients hide display names that is client behavior. We set an encoded `From` header; that works for most recipients.
* For large volumes consider transactional mail provider due to Gmail quotas.
* Keep `credentials.json` and `token.json` secure. Rotate or revoke tokens if compromised.
* To change template edit `templates/invoice.html`. Template variables available:

  ```
  title, name, lot, share, yearly_amount, amount_due, year, voting_date, total_budget
  ```
* Multiple addresses in `email` cell are joined into the `To` header. If you later prefer per-recipient sends and a log, that can be re-added.
