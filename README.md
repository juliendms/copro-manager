# Copro-Manager

A local web application for managing condominium co-owners: charges, invoices, and email communication. Built with Flask, SQLAlchemy, HTMX, and BeerCSS (Material Design 3).

## Features

- **Co-owner management:** Track owners, their shares (tantièmes), and email addresses.
- **Charge management:** Create and distribute common or extraordinary charges across owners, with support for Limited Common Elements (LCE).
- **Invoice generation & emailing:** Generate personalized invoices and send them via Gmail API.

## Quick Setup

### Prerequisites

- Python 3.10+
- A Gmail account with OAuth 2.0 credentials (for sending emails)

### Installation

1. **Clone the repository:**

    ```bash
    git clone [repository_url]
    cd copro-manager
    ```

2. **Create a virtual environment and install dependencies:**

    ```bash
    python -m venv .venv
    # Windows (PowerShell)
    .\.venv\Scripts\Activate.ps1
    # macOS/Linux
    source .venv/bin/activate

    pip install -r requirements.txt
    ```

3. **Configure environment variables:**

    Copy `.env.exemple` to `.env` and fill in the values:

    ```bash
    cp .env.exemple .env
    ```

    ```dotenv
    SECRET_KEY=your_secret_key_here
    FLASK_DEBUG=false   # set to true to enable debug mode
    ```

4. **Configure Gmail OAuth (optional, for email sending):**

    - Enable the Gmail API in your [Google Cloud Console](https://console.cloud.google.com/) and download `credentials.json` (Desktop app type) to the project root.
    - Run `python oauth_setup.py` and follow the browser prompts to generate `token.json`.

### Running the application

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`. On first run, the database does not exist yet — the app shows an empty state with a setup button to initialize the database tables.

**Debug mode** is controlled by the `FLASK_DEBUG` environment variable in `.env`:

```dotenv
FLASK_DEBUG=true   # enables auto-reload and the debugger
FLASK_DEBUG=false  # production-like (default)
```

## Seeding Initial Owners (Dev Workflow)

When iterating on the DB structure (e.g., after dropping and recreating it), you can bulk-import owners from a JSON file instead of adding them one by one through the UI.

1. Create or update `owner_management/data/initial_owners.json` with your owner list:

    ```json
    [
      {
        "name": "DUPONT J.",
        "lot": "12/13",
        "share": "182",
        "email": "jean.dupont@example.com"
      },
      {
        "name": "MARTIN A. / MARTIN B.",
        "lot": "14",
        "share": "90",
        "email": "alice@example.com,bob@example.com"
      }
    ]
    ```

    - `lot`: lot number(s) as a string
    - `share`: general share as a number
    - `email`: one address, or multiple comma-separated addresses

2. After initializing the DB, go to **Owners** and click **"Load initial data"** (or equivalent button in the empty state). The route `/owners/init_data` reads the file and creates owners, skipping any that already exist.

## Running Tests

Tests use pytest with an in-memory SQLite database — no setup required.

```bash
python -m pytest tests/ -v
```

## Project Structure

```
copro-manager/
├── app.py                  # Application entry point
├── models.py               # SQLAlchemy models
├── app_utils.py            # Shared utilities
├── owner_management/       # Blueprint: /owners
├── charges_management/     # Blueprint: /charges
├── lce_management/         # Blueprint: /elements
├── templates/              # Jinja2 templates
├── static/                 # CSS, JS, images
├── tests/                  # pytest test suite
├── docs/decisions/         # Architecture Decision Records (ADRs)
├── .env.exemple            # Environment variable template
└── requirements.txt
```

## License

This project is licensed under the MIT License.
