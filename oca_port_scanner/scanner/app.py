# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import logging
import signal
import time
from typing import List
import sys

import schedule

from .repo import Repo
from .storage import Storage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SignalHandler:

  def __init__(self):
    signal.signal(signal.SIGINT, self._exit)
    signal.signal(signal.SIGTERM, self._exit)

  def _exit(self, *args):
    logger.info("Stop")
    # NOTE: Do not let gitpython subprocesses raising exceptions to the parent
    # process. A bit ugly but this avoids a traceback of gitpython processes
    # (which is catching signals too) when stopping the app.
    sys.exit(0)


class App:
    """Scan OCA-like repositories.

    It behaves as follow:
        1. clone or update repositories locally
        2. for each updated module since the last check, scan it and save the result
    """
    def __init__(self, repositories: List, branches_matrix: List):
        self.storage = Storage(self)
        self.repositories = repositories
        self.branches_matrix = branches_matrix
        self.branches = sorted(set(sum(branches_matrix, ())))
        # FIXME test
        # schedule.every().hour.do(fetch_repositories)
        schedule.every(2).seconds.do(self._scan_repositories)

    def _scan_repositories(self):
        logger.info("Scan %s repositories...", len(self.repositories))
        for repository in self.repositories:
            repo = Repo(self, repository)
            repo.fetch()
            repo.scan()

    def run(self):
        logger.info("Started")
        handler = SignalHandler()
        while True:
            schedule.run_pending()
            time.sleep(1)
        logger.info("Stopped")
