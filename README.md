
# Selenium Automation (Dockerized)

This project provides a Dockerized Python Selenium automation system designed to run authorized automated actions on a website using multiple isolated accounts. It manages per-account Chrome profiles and cookie persistence, schedules daily runs, provides a simple FastAPI dashboard, logs, screenshots on failures, CSV results, and optional Telegram notifications.

Directory structure

```
selenium-automation/
├── app/                      # Application code (FastAPI + automation)
├── accounts/                 # Example accounts config
├── cookies/                  # Per-account cookie files (ignored)
├── profiles/                 # Per-account Chrome profiles (ignored)
├── screenshots/              # Failure screenshots (ignored)
├── logs/                     # Runtime logs (ignored)
├── results/                  # results.csv (ignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

Features

- Runs browser automation for up to 20 accounts with isolated Chrome profiles and cookie files.
- Headless Chromium running in Docker (or locally) using Selenium.
- Scheduling via APScheduler (daily run at configured hour/minute, timezone-aware).
- Concurrency control using `MAX_CONCURRENT_BROWSERS`.
- FastAPI dashboard with endpoints to run jobs, view accounts, and view results.
- CSV result logging (`results/results.csv`) with file locking.
- Screenshots captured on failure.
- Telegram summary notifications (optional).

System requirements

- Docker Desktop (macOS/Windows/Linux) to run in containers.
- Python 3.12 for local development and tests.

macOS Apple Silicon (M1/M2) notes

- Official Chromium packages in Debian-based images may not match Apple Silicon. Use Docker Desktop with platform emulation or install a compatible Chromium build. If you see driver errors, consider running the container with `--platform linux/amd64` or using a custom Chromium build.

Windows and Linux notes

- Docker Desktop or Docker Engine needed. Volume mounts behave differently across platforms; compose file is set to mount host folders for persistence.

Getting started

1. Copy `.env.example` to `.env` and fill values. See "Environment variables" below for explanations.
2. Copy `accounts/accounts.example.json` to `accounts/accounts.json` and add up to 20 accounts. Each account should look like:

```json
{
	"id": "01",
	"username": "user01@example.com",
	"password": "changeme",
	"enabled": false
}
```

3. (Optional) Add cookie files for accounts in Selenium JSON format `cookies/account_<id>.json`. Example cookie files shipped contain `[]` (empty array) and are safe to track as examples.

4. Build and start with Docker Compose:

```bash
docker compose up --build -d
```

5. Open dashboard: http://localhost:8000

Environment variables

Copy `.env.example` → `.env` and set these variables. Required variables (must be configured before running real automation):

- `TARGET_URL`: The URL to validate session and perform the action.
- `LOGIN_URL`: The login page URL.
- `USERNAME_SELECTOR`: CSS selector for the username input field.
- `PASSWORD_SELECTOR`: CSS selector for the password input field.
- `LOGIN_BUTTON_SELECTOR`: CSS selector for the login button.
- `TARGET_BUTTON_SELECTOR`: CSS selector for the button to click during automation.
- `SUCCESS_SELECTOR`: CSS selector used to detect successful action or login.

Optional configuration:

- `MAX_CONCURRENT_BROWSERS` (default `3`) — limits concurrent browser sessions.
- `SCHEDULE_HOUR`, `SCHEDULE_MINUTE` — schedule for daily run.
- `TIMEZONE` — timezone for scheduling (default `Asia/Riyadh`).
- `HEADLESS` — `true` or `false` (default `true`).
- `PAGE_LOAD_TIMEOUT`, `ELEMENT_WAIT_TIMEOUT`, `MAX_RETRIES` — timeouts and retry counts.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — to enable Telegram summary notifications.

Cookie persistence and profiles

- Each account uses a separate Chrome profile directory under `profiles/profile_<id>` and a cookie file `cookies/account_<id>.json`.
- On login, cookies are saved to the cookie file. On subsequent runs, cookies are loaded and validated.
- If cookies are invalid, the app will attempt login with credentials from `accounts/accounts.json`.

Automatic login behavior

- The project includes a placeholder `is_session_valid(driver)` function in `app/worker.py`. Customize it to match site behavior (e.g., by checking for a dashboard element or logout link).

Testing one account safely

1. Add a single account to `accounts/accounts.json` with `enabled: true`.
2. Fill `.env` selectors and URLs for the test site.
3. Start the app and use the dashboard `Run All` or `POST /api/run/{account_id}` to test.

Building and running without Docker (development)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:APP --app-dir . --host 127.0.0.1 --port 8000
```

Running individual account manually

- `POST /api/run/{account_id}` triggers a single account run.

Scheduling

- The scheduler runs once every 24 hours at `SCHEDULE_HOUR:SCHEDULE_MINUTE` in `TIMEZONE` and prevents overlapping runs.

Logs, screenshots, and CSV results

- `logs/` collects runtime logs (ignored by git).
- `screenshots/` stores failure screenshots.
- `results/results.csv` contains execution results with columns: `account_id,status,started_at,finished_at,duration_seconds,current_url,attempts,error`.

Telegram notifications

- Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to enable summary notifications after a batch.

Stopping and restarting

- Docker: `docker compose down` then `docker compose up --build -d`.
- Local: stop the `uvicorn` process and restart with the previous uvicorn command.

Troubleshooting

- If Chromium/driver errors occur in Docker on Apple Silicon, try `--platform linux/amd64` or use a custom image with a compatible Chromium build.
- Ensure mounted volumes have correct permissions; the container runs under a non-root `appuser`.

Security and legal

- Do not commit `.env`, `accounts/accounts.json`, cookies, or profile directories.
- This tool does not include CAPTCHA bypassing, fingerprint spoofing, proxy rotation, or other anti-bot bypass techniques.
- Only automate actions on websites for which you have authorization.

