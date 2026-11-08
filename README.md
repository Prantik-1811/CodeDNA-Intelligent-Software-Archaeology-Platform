# CodeDNA-Intelligent-Software-Archaeology-Platform.

**Understand the Impact Before You Change the Code.**

CodeDNA is a platform that helps developers understand large and unfamiliar software projects. It analyzes the code, identifies connections between different parts of the application, and shows developers what could be affected when they make changes.

## Key Features

- Repository structure analysis
- Code dependency visualization
- Function and class identification
- Git history analysis
- Change impact analysis
- Related test discovery

## Tech Stack

- Python
- FastAPI
- Tree-sitter
- NetworkX
- React
- PostgreSQL

## Project Status

Currently under development.

## License

This project is licensed under the MIT License.
# CodeDNA

## Google OAuth local setup

1. Open [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and create an OAuth 2.0 Client ID with application type **Web application**.
2. Add this exact authorized redirect URI:
   `http://127.0.0.1:8001/auth/google/callback`
3. Use `.env.example` as a template, then export these variables in the shell
   that starts the API: `CODNA_AUTH_SECRET`, `GOOGLE_CLIENT_ID`, and
   `GOOGLE_CLIENT_SECRET`.
4. Start the API from the repository root with those variables loaded. The demo then uses **Sign in with Google**.

The client ID and secret are never committed. For local PowerShell sessions:

```powershell
$env:CODNA_AUTH_SECRET = "generate-a-long-random-value"
$env:GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
$env:GOOGLE_CLIENT_SECRET = "your-client-secret"
python -m uvicorn codna.api:app --host 127.0.0.1 --port 8001
```
