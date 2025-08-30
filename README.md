# Copro-Manager

Copro-Manager is a Python application designed to streamline the management and communication with co-owners in a condominium setting. It automates the process of generating and sending personalized invoices based on data from a local database.

## Features

*   **Automated Invoice Generation:** Creates individual HTML invoices for co-owners using a customizable template.
*   **Database Integration:** Manages co-owner data (emails, names, charges, etc.) through a local database.
*   **Gmail API Integration:** Sends personalized invoices via email using a designated Gmail account.
*   **Dynamic Data:** Utilizes charge and owner data from the database for dynamic content in invoices.

## Quick Setup

### Prerequisites

*   Python 3.10+
*   Google Cloud Platform (GCP) account with Gmail API enabled.
*   OAuth 2.0 credentials (Desktop app type) downloaded as `credentials.json`.
*   `.env` file configured with `SECRET_KEY` to access the database.

### Installation

1.  **Clone the repository:**

    ```powershell
    git clone [repository_url]
    cd copro-manager
    ```

2.  **Set up a virtual environment and install dependencies:**

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```

3.  **Configure Google OAuth:**

    *   Place your `credentials.json` in the project root.
    *   Run `python oauth_setup.py` to generate `token.json` (follow browser prompts).

4.  **Run the application:**

    ```powershell
    python app.py
    ```

    Access the application in your browser (usually `http://127.0.0.1:5000`).

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License.
