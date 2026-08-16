import os
import json
import logging
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from typing import List, Dict

from .scheduler import SchedulerManager
from .notifications import send_telegram_summary

load_dotenv()
logger = logging.getLogger("uvicorn")

APP = FastAPI()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_env():
    env = {k: os.getenv(k) for k in os.environ.keys()}
    # Also expose some base paths
    env.setdefault("PROFILE_BASE", os.path.join(BASE_DIR, "profiles"))
    env.setdefault("COOKIE_BASE", os.path.join(BASE_DIR, "cookies"))
    env.setdefault("SCREENSHOT_BASE", os.path.join(BASE_DIR, "screenshots"))
    return env


REQUIRED = [
    "TARGET_URL",
    "LOGIN_URL",
    "USERNAME_SELECTOR",
    "PASSWORD_SELECTOR",
    "LOGIN_BUTTON_SELECTOR",
    "TARGET_BUTTON_SELECTOR",
    "SUCCESS_SELECTOR",
]


def validate_required(env):
    missing = [v for v in REQUIRED if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Missing required env variables: {', '.join(missing)}")


def load_accounts(path: str) -> List[Dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Accounts file not found: {path}. Copy accounts.example.json to accounts.json and fill credentials.")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Validate accounts list
    for a in data:
        if "id" not in a:
            raise RuntimeError("Every account must have an 'id' field")
    return data


@APP.on_event("startup")
def startup_event():
    global ENV, ACCOUNTS, SCHEDULER_MANAGER, MANUAL_LOCK
    ENV = load_env()
    try:
        validate_required(ENV)
    except Exception as e:
        # Let the app start but record the error so endpoints can report clearly
        logger.error("Configuration validation failed: %s", e)
        ENV["_validation_error"] = str(e)

    accounts_path = os.path.join(BASE_DIR, "accounts", "accounts.json")
    try:
        ACCOUNTS = load_accounts(accounts_path)
    except Exception as e:
        logger.warning("Accounts file issue: %s", e)
        ACCOUNTS = []

    SCHEDULER_MANAGER = SchedulerManager(ACCOUNTS, ENV)
    try:
        SCHEDULER_MANAGER.start()
    except Exception:
        logger.exception("Failed to start scheduler")

    MANUAL_LOCK = threading.Lock()


@APP.on_event("shutdown")
def shutdown_event():
    try:
        SCHEDULER_MANAGER.shutdown()
    except Exception:
        logger.exception("Error shutting down scheduler")


@APP.get("/", response_class=HTMLResponse)
def index():
    # Simple dashboard showing latest result per account
    rows = []
    results_file = os.path.join(BASE_DIR, "results", "results.csv")
    if os.path.exists(results_file):
        with open(results_file, "r", encoding="utf-8") as fh:
            lines = fh.read().strip().splitlines()
        # produce simple HTML table
        rows = lines[-21:]

    html = "<html><head><title>Selenium Automation</title></head><body>"
    html += "<h1>Selenium Automation Dashboard</h1>"
    html += "<div><button onclick=fetch('/api/run-all',{method:'POST'}).then(()=>alert('started'))>Run All</button> "
    html += "<button onclick=fetch('/api/stop',{method:'POST'}).then(()=>alert('stop requested'))>Stop</button> "
    html += "<button onclick=location.reload()>Refresh</button></div>"
    html += "<h2>Recent Results</h2><pre>\n"
    html += "\n".join(rows)
    html += "</pre></body></html>"
    return HTMLResponse(content=html)


@APP.get("/health")
def health():
    return JSONResponse({"status": "ok"})


@APP.get("/api/status")
def api_status():
    return {"scheduler_running": getattr(SCHEDULER_MANAGER, "running", False), "accounts_loaded": len(ACCOUNTS), "validation_error": ENV.get("_validation_error")}


@APP.get("/api/accounts")
def api_accounts():
    # Never expose passwords or cookies
    return [{"id": a.get("id"), "enabled": a.get("enabled", False)} for a in ACCOUNTS]


@APP.post("/api/run-all")
def api_run_all(background: BackgroundTasks):
    if not MANUAL_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Manual run already in progress")

    def run_and_release():
        try:
            results = SCHEDULER_MANAGER.run_enabled_accounts()
            send_telegram_summary(ENV, results or [])
        finally:
            MANUAL_LOCK.release()

    background.add_task(run_and_release)
    return {"status": "started"}


@APP.post("/api/run/{account_id}")
def api_run_account(account_id: str):
    try:
        res = SCHEDULER_MANAGER.run_single(account_id)
        return res
    except KeyError:
        raise HTTPException(status_code=404, detail="Account not found")


@APP.post("/api/stop")
def api_stop():
    # Request scheduler to stop scheduling new jobs
    try:
        SCHEDULER_MANAGER.shutdown()
        return {"status": "stopping"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@APP.get("/api/results")
def api_results():
    results_file = os.path.join(BASE_DIR, "results", "results.csv")
    if not os.path.exists(results_file):
        return []
    import csv

    rows = []
    with open(results_file, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    # return last 100 results
    return rows[-100:]

