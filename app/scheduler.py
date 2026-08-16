import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict

# Import APScheduler lazily inside start() to avoid import-time dependency issues

from .worker import run_account

logger = logging.getLogger(__name__)


class SchedulerManager:
    def __init__(self, accounts: List[Dict], env: Dict[str, str]):
        self.accounts = accounts
        self.env = env
        self.scheduler = None
        self.job = None
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        # Lazy import to prevent pkg_resources issues at module import time
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except Exception as e:
            logger.exception("Failed to import APScheduler: %s", e)
            # Scheduler is optional at runtime if the environment lacks system packages
            self.scheduler = None
            return

        try:
            hour = int(self.env.get("SCHEDULE_HOUR", 8))
            minute = int(self.env.get("SCHEDULE_MINUTE", 0))
            self.scheduler = BackgroundScheduler(timezone=self.env.get("TIMEZONE", "Asia/Riyadh"))
            trigger = CronTrigger(hour=hour, minute=minute, timezone=self.env.get("TIMEZONE", "Asia/Riyadh"))
            self.job = self.scheduler.add_job(self.run_enabled_accounts, trigger, id="daily_batch", max_instances=1)
            self.scheduler.start()
            logger.info("Scheduler started: runs at %s:%s %s", hour, minute, self.env.get("TIMEZONE"))
        except Exception:
            logger.exception("Failed to start APScheduler")
            self.scheduler = None

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)

    def run_enabled_accounts(self):
        # Prevent overlap
        if not self.lock.acquire(blocking=False):
            logger.info("Previous run still in progress; skipping this schedule")
            return
        try:
            self.running = True
            enabled = [a for a in self.accounts if a.get("enabled")]
            max_workers = int(self.env.get("MAX_CONCURRENT_BROWSERS", 3))
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = {ex.submit(run_account, a, self.env): a for a in enabled}
                for fut in as_completed(futures):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        logger.exception("Account task error: %s", e)
            return results
        finally:
            self.running = False
            self.lock.release()

    def run_single(self, account_id: str):
        acc = next((a for a in self.accounts if a.get("id") == account_id), None)
        if not acc:
            raise KeyError("Account not found")
        return run_account(acc, self.env)
