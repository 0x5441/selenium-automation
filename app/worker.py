import os
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, Any
from filelock import FileLock
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from . import browser

logger = logging.getLogger(__name__)

RESULTS_CSV = os.path.join(os.path.dirname(__file__), "..", "results", "results.csv")
RESULTS_LOCK = RESULTS_CSV + ".lock"


def is_session_valid(driver) -> bool:
    """Placeholder to validate session.

    Customize this to your site: for example, check for a unique dashboard element,
    absence of the login form, or the presence of a logout link. Examples:
    - return bool(driver.find_elements(By.CSS_SELECTOR, "#dashboard"))
    - return "logout" in driver.page_source.lower()
    - check that the current url is not the login url
    """
    # Default conservative behavior: return False so login will be attempted.
    return False


def append_result_csv(row: Dict[str, Any]):
    import csv

    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    lock = FileLock(RESULTS_LOCK, timeout=10)
    with lock:
        file_exists = os.path.exists(RESULTS_CSV)
        with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if not file_exists:
                writer.writerow([
                    "account_id",
                    "status",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                    "current_url",
                    "attempts",
                    "error",
                ])
            writer.writerow([
                row.get("account_id"),
                row.get("status"),
                row.get("started_at"),
                row.get("finished_at"),
                row.get("duration_seconds"),
                row.get("current_url"),
                row.get("attempts"),
                row.get("error"),
            ])


def run_account(account: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    started_at = datetime.utcnow().isoformat()
    attempts = 0
    max_retries = int(env.get("MAX_RETRIES", 2))
    page_load_timeout = int(env.get("PAGE_LOAD_TIMEOUT", 40))
    headless = env.get("HEADLESS", "true").lower() in ("1", "true", "yes")

    account_id = account.get("id")
    profile_dir = os.path.abspath(os.path.join(env.get("PROFILE_BASE", "profiles"), f"profile_{account_id}"))
    cookie_file = os.path.abspath(os.path.join(env.get("COOKIE_BASE", "cookies"), f"account_{account_id}.json"))

    last_error = ""
    status = "failed"
    start_time = time.time()

    while attempts <= max_retries:
        attempts += 1
        driver = None
        try:
            driver = browser.create_driver(profile_dir=profile_dir, page_load_timeout=page_load_timeout, headless=headless)
            target_url = env.get("TARGET_URL")
            login_url = env.get("LOGIN_URL")

            # Load a blank page to set domain for cookies
            driver.get(target_url or "about:blank")
            browser.load_cookies(driver, cookie_file)
            driver.get(target_url or login_url)

            # Validate session
            if not is_session_valid(driver):
                # Perform login flow
                if not login_url:
                    raise RuntimeError("Session invalid and LOGIN_URL not configured")
                driver.get(login_url)
                wait = WebDriverWait(driver, int(env.get("ELEMENT_WAIT_TIMEOUT", 20)))
                username_sel = env.get("USERNAME_SELECTOR")
                password_sel = env.get("PASSWORD_SELECTOR")
                login_btn_sel = env.get("LOGIN_BUTTON_SELECTOR")
                if not (username_sel and password_sel and login_btn_sel):
                    raise RuntimeError("Missing login selectors in environment")

                # Fill credentials; never log or store the password
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, username_sel))).send_keys(account.get("username"))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, password_sel))).send_keys(account.get("password"))
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, login_btn_sel))).click()

                # Wait for either target URL or success selector
                success_sel = env.get("SUCCESS_SELECTOR")
                if success_sel:
                    WebDriverWait(driver, int(env.get("ELEMENT_WAIT_TIMEOUT", 20))).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, success_sel))
                    )
                # Save cookies after login
                browser.save_cookies(driver, cookie_file)

            # Perform the action: find target button, scroll and click
            target_button = env.get("TARGET_BUTTON_SELECTOR")
            if not target_button:
                raise RuntimeError("TARGET_BUTTON_SELECTOR not configured")
            wait = WebDriverWait(driver, int(env.get("ELEMENT_WAIT_TIMEOUT", 20)))
            elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, target_button)))
            driver.execute_script("arguments[0].scrollIntoView({behavior:'auto',block:'center'});", elem)
            elem.click()

            # Wait for success
            success_sel = env.get("SUCCESS_SELECTOR")
            if success_sel:
                WebDriverWait(driver, int(env.get("ELEMENT_WAIT_TIMEOUT", 20))).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, success_sel))
                )

            status = "success"
            last_error = ""
            return_result = {
                "account_id": account_id,
                "status": status,
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
                "duration_seconds": round(time.time() - start_time, 2),
                "current_url": driver.current_url if driver else "",
                "attempts": attempts,
                "error": last_error,
            }
            append_result_csv(return_result)
            return return_result

        except Exception as exc:
            last_error = str(exc)
            logger.exception("Account %s attempt %s failed: %s", account_id, attempts, last_error)
            # capture screenshot
            try:
                os.makedirs(env.get("SCREENSHOT_BASE", "screenshots"), exist_ok=True)
                ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                path = os.path.join(env.get("SCREENSHOT_BASE", "screenshots"), f"{account_id}_{attempts}_{ts}.png")
                if driver:
                    driver.save_screenshot(path)
            except Exception:
                logger.exception("Failed to save screenshot for %s", account_id)
            # on last attempt record failure
            if attempts > max_retries:
                return_result = {
                    "account_id": account_id,
                    "status": status,
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat(),
                    "duration_seconds": round(time.time() - start_time, 2),
                    "current_url": driver.current_url if driver else "",
                    "attempts": attempts,
                    "error": last_error[:1000],
                }
                append_result_csv(return_result)
                return return_result
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                logger.exception("Error quitting driver for %s", account_id)

