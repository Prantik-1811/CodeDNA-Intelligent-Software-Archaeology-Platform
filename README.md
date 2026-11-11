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

## Run locally with Docker

Docker Desktop (or Docker Engine with the Compose plugin) is the only required
local prerequisite. The default setup uses SQLite in a persistent Docker volume;
PostgreSQL is optional.

1. Create a local-only Docker env file from the safe template:

   ```powershell
   Copy-Item .env.local.example .env.local
   ```

   Keep any existing `.env` intact. The local commands below explicitly load
   `.env.local`, so your other deployment settings are not used. Do not paste
   `docker compose config` output into public chats: it expands variables and
   can display secrets.

2. Start CodeDNA:

   ```powershell
   docker compose --env-file .env.local up --build
   ```

3. Open the dashboard at <http://localhost:5173/dashboard/>. The API and its
   interactive docs are at <http://localhost:8001> and <http://localhost:8001/docs>.

Data (including the local SQLite database and cloned public repositories) is
stored in the `codna-data` Docker volume. Stop with `Ctrl+C`; restart with
`docker compose up`. To stop and remove containers while keeping data, use
`docker compose down`. Removing the named volume deletes its contents.

### Use PostgreSQL locally

Set a local password and database URL in `.env`:

```env
POSTGRES_PASSWORD=choose-a-local-password
CODNA_DATABASE_URL=postgresql+psycopg://codna:choose-a-local-password@postgres:5432/codna
```

Then start the optional database profile:

```powershell
docker compose --env-file .env.local --profile postgres up --build
```

The database port is bound to `127.0.0.1` only. SQLite remains the default for
the simplest contributor workflow.

### OAuth setup

Email/password registration works locally without OAuth credentials. To enable
Google or GitHub sign-in, create OAuth credentials with your provider and set
the corresponding values in `.env`. Set callback URLs to the actual API URL,
for example `http://127.0.0.1:8001/auth/google/callback` locally. For an HTTPS
deployment, use the public API callback URL, a unique `CODNA_AUTH_SECRET`,
`CODNA_COOKIE_SECURE=true`, and the public dashboard URL in
`CODNA_FRONTEND_URL`. If the dashboard and API are on different sites (for
example, separate `onrender.com` services), also set
`CODNA_COOKIE_SAMESITE=none`; `SameSite=None` requires secure HTTPS cookies.
For local development, keep `CODNA_COOKIE_SAMESITE=lax` and
`CODNA_COOKIE_SECURE=false`. Never commit `.env` or share production credentials.

See [RISK_MODEL.md](RISK_MODEL.md) for the current risk methodology and its
validation status.

## Prepare for public hosting

The Docker Compose file is the self-hosting baseline, not a complete managed
cloud deployment. Before exposing the API publicly:

- Set unique secrets through the host's secret manager. Do not reuse the sample
  values in `.env.local.example` or commit a real `.env` file.
- Use managed PostgreSQL or a backed-up persistent database volume.
- Keep `/codna-data` on persistent storage because repository clones live there.
- Set `CODNA_COOKIE_SECURE=true`, configure the real dashboard URL, and register
  OAuth callbacks against the public API URL.
- Put HTTPS in front of the dashboard and API, and restrict API access/rates for
  repository ingestion.

If any real credential was included in diagnostic output or shared outside its
secret store, rotate it before deployment.

### First hosted deployment on Render

For the initial hosted version, deploy the dashboard as a Static Site, the API
as a Docker Web Service, and use Render Postgres. The dashboard build supports
both the local `/dashboard/` path and the hosted root path. Keep the API's
`/codna-data` directory on a persistent disk because it stores repository
clones. This disk requires a paid Render service; without persistent storage,
clones disappear when the service restarts or redeploys.

1. Connect the public GitHub repository to Render.
2. Create a **Static Site** for the dashboard from the repository, set root
   directory to `dashboard`, build command to `npm ci && npm run build`, and
   publish directory to `dist`. Set `VITE_BASE_PATH=/`, `VITE_API_BASE_URL` to
   the API's public HTTPS URL, and optionally set `VITE_SUPPORT_EMAIL`.
3. Create a **PostgreSQL** database in Render.
4. Create a **Web Service** for the API from the repository root, using the root
   `Dockerfile`. Set its health check path to `/`, and attach a persistent disk
   mounted at `/codna-data`.
5. Set these API environment variables in Render's secret/environment settings:
   `CODNA_DATABASE_URL` (the database's internal URL), `CODNA_DATA_DIR=/codna-data`,
   `CODNA_AUTH_SECRET` (a newly generated random secret),
   `CODNA_COOKIE_SECURE=true`, `CODNA_COOKIE_SAMESITE=none`,
   `CODNA_FRONTEND_URL` (the dashboard's HTTPS URL),
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REDIRECT_URI`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and
   `GITHUB_REDIRECT_URI`.
6. Set the production OAuth callbacks to
   `https://<api-host>/auth/google/callback` and
   `https://<api-host>/auth/github/callback`. Create separate provider apps for
   production so local OAuth callbacks continue working.
7. After both services are created, set the dashboard's `VITE_API_BASE_URL` to
   the API URL and redeploy the dashboard.

Keep provider secrets and database credentials in Render's environment
settings, never in this repository. Render's deployment screens and pricing can
change; confirm the current storage and database plan details before creating
paid resources.

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
