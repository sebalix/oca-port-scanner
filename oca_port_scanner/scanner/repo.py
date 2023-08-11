# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import json
import logging
import time

import git
import oca_port

from .exceptions import PostponeError


logger = logging.getLogger(__name__)


class Repo:
    def __init__(self, app, name):
        self.app = app
        self.name = name
        self.upstream = self.name.split("/", maxsplit=1)[0]
        self.techname = self.name.split("/", maxsplit=1)[1]
        self.path = self.app.storage.repositories_path.joinpath(*self.name.split("/"))
        self.scan_data_path = self.app.storage.data_path.joinpath(*self.name.split("/"))
        # Create the subfolder (e.g. './OCA/') that will host the repository
        self.path.parent.mkdir(exist_ok=True)
        # Create the subfolders (e.g. './OCA/server-tools') that will host the data
        self.scan_data_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.scan_data_path.parent.joinpath(f"{self.techname}.json")
        self._metadata = self._read_metadata()

    def fetch(self):
        """Clone or update the repository."""
        if not self.is_cloned:
            self._clone()
        self._fetch()

    def scan(self):
        """Scan the modules that have changed since last scan."""
        for from_branch, to_branch in self.app.branches_matrix:
            last_scan = self.get_last_scan_commit(from_branch)
            repo = git.Repo(self.path)
            last_commit = repo.rev_parse(f"origin/{from_branch}").hexsha
            if last_scan != last_commit:
                modules_updated = sorted(self._get_modules_updated(last_scan, last_commit))
                logger.info(
                    "%s: %s modules updated on %s",
                    self.name, len(modules_updated), from_branch
                )
                for module in modules_updated:
                    data = self._scan_module(module, from_branch, to_branch)
                    self._store_scan_module_data(module, from_branch, to_branch, data)
                    time.sleep(5)   # Slow down to not hammer GitHub API
            # Store last scanned commits
            self.set_last_scan_commit(from_branch, last_commit)
            self._write_metadata()

    def _scan_module(self, module, from_branch, to_branch):
        logger.info("%s: scan '%s' (%s -> %s)", self.name, module, from_branch, to_branch)
        # Initialize the oca-port app
        params = {
            "from_branch": from_branch,
            "to_branch": to_branch,
            "addon": module,
            "upstream_org": self.upstream,
            "upstream": "origin",
            "repo_path": self.path,
            "repo_name": self.techname,
            "output": "json",
            "fetch": False,
        }
        scan = oca_port.App(**params)
        try:
            json_data = scan.run()
        except RuntimeError as exc:
            if "limit exceeded" in exc.args[0]:
                # GitHub API rate limit exceeded, postpone the next call in 1h
                # https://docs.github.com/rest/overview/resources-in-the-rest-api
                raise PostponeError(exc.args[0], 60*60) from exc
            raise RuntimeError
        return json.loads(json_data)

    def _store_scan_module_data(self, module, from_branch, to_branch, data):
        if not data:
            return
        file_path = self.scan_data_path.joinpath(f"{module}-{from_branch}-{to_branch}.json")
        with open(file_path, "w") as file_:
            json.dump(data, file_)

    def _read_metadata(self):
        # Default metadata
        data = default_data = {
            "last_scan": dict.fromkeys(self.app.branches)
        }
        try:
            with open(self.metadata_path) as metadata_file:
                data = json.load(metadata_file)
                if not data:
                    data = default_data
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass
        return data or default_data

    def _write_metadata(self):
        with open(self.metadata_path, "w") as metadata_file:
            json.dump(self._metadata, metadata_file)

    def get_last_scan_commit(self, branch):
        return self._metadata["last_scan"].get(branch)

    def set_last_scan_commit(self, branch, commit):
        self._metadata["last_scan"][branch] = commit

    def _get_modules_updated(self, from_commit, to_commit):
        """Return a set of modules updated between `from_commit` and `to_commit`."""
        # Same commits: nothing has changed
        if from_commit == to_commit:
            return []
        modules = set()
        repo = git.Repo(self.path)
        if not from_commit:
            # No from_commit means first scan: return all available modules
            to_commit = repo.commit(to_commit)
            modules = set(
                tree.path for tree in to_commit.tree.trees
                if self._filter_module_path(tree.path)
            )
        else:
            # Get only modules updated between the two commits
            from_commit, to_commit = repo.commit(from_commit), repo.commit(to_commit)
            diffs = to_commit.diff(from_commit, R=True)
            for diff in diffs:
                path = diff.a_path.split("/", maxsplit=1)[0]
                if self._filter_module_path(path):
                    modules.add(path)
        return modules

    def _filter_module_path(self, path):
        if path.startswith("setup") or path.startswith(".") or path.endswith(".po"):
            return False
        return True

    @property
    def url(self):
        return f"https://github.com/{self.name}.git"

    @property
    def is_cloned(self):
        return self.path.joinpath(".git").exists()

    def _clone(self):
        logger.info("Clone %s", self.name)
        git.Repo.clone_from(self.url, self.path)

    def _fetch(self):
        repo = git.Repo(self.path)
        sha = repo.rev_parse('origin/14.0')
        logger.info("%s: fetch branches %s", self.name, ", ".join(self.app.branches))
        for branch in self.app.branches:
            repo.remotes.origin.fetch(branch)
