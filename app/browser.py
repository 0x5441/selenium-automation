import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


def create_driver(profile_dir: str, page_load_timeout: int, headless: bool = True):
    """Create a Chrome WebDriver configured for Docker and a per-account profile.

    The caller is responsible for quitting the driver in a finally block.
    """
    options = Options()
    # Headless mode: use the new headless implementation which works better in recent Chrome
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Use a persistent profile per account
    os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")

    # Service binary path: Dockerfile installs chromedriver to /usr/bin/chromedriver
    service = Service("/usr/bin/chromedriver")
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(page_load_timeout)
        return driver
    except WebDriverException as e:
        logger.exception("Failed to start Chrome WebDriver: %s", e)
        raise


def load_cookies(driver, cookie_file: str):
    try:
        import json

        if os.path.exists(cookie_file):
            with open(cookie_file, "r") as fh:
                cookies = json.load(fh)
            # Cookie format should be list of dicts compatible with Selenium
            for c in cookies:
                # Selenium expects expiry as int if present
                try:
                    driver.add_cookie(c)
                except Exception:
                    # Skip invalid cookie entries
                    logger.debug("Skipping invalid cookie entry for %s", cookie_file)
    except Exception:
        logger.exception("Failed to load cookies from %s", cookie_file)


def save_cookies(driver, cookie_file: str):
    try:
        import json

        cookies = driver.get_cookies()
        os.makedirs(os.path.dirname(cookie_file) or ".", exist_ok=True)
        with open(cookie_file, "w") as fh:
            json.dump(cookies, fh)
    except Exception:
        logger.exception("Failed to save cookies to %s", cookie_file)
