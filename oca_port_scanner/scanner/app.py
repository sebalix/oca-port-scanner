# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import logging
import signal
import sys
import time

import schedule

from .. import backend, config, storage
from .repo import Repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalHandler:
    def __init__(self):
        signal.signal(signal.SIGINT, self._exit)
        signal.signal(signal.SIGTERM, self._exit)

    def _exit(self, *args):
        logger.info("Stop")
        # NOTE: Do not let gitpython subprocesses raising exceptions to the
        # parent process. A bit ugly but this avoids a traceback of gitpython
        # processes (which are catching signals too) when stopping the app.
        sys.exit(0)


class App:
    """Scan OCA-like repositories.

    It behaves as follow:
        1. clone or update repositories locally
        2. for each updated module since the last check, scan it
    """

    def __init__(self):
        self.config = config.Config()
        self.config.init()
        self.storage = storage.Storage(self.config)
        self.backend = backend.Backend(self.config)
        self.repositories = self.config["repositories"]
        self.branches_matrix = [
            (k, v) for k, v in self.config["branches_matrix"]
        ]
        self.branches = sorted(set(sum(self.branches_matrix, ())))
        # FIXME test
        # schedule.every().hour.do(self._scan_repositories)
        schedule.every(2).seconds.do(self._scan_repositories)

    def _scan_repositories(self):
        """Scan repositories for all branch combinations provided."""
        logger.info("Scan %s repositories...", len(self.repositories))
        for repository in self.repositories:
            repo = Repo(self, repository)
            repo.fetch()
            repo.scan()

    def run(self):
        logger.info("Started")
        SignalHandler()
        while True:
            schedule.run_pending()
            time.sleep(1)
        logger.info("Stopped")
