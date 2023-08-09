# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import json
import logging
import time

import git
import oca_port

logger = logging.getLogger(__name__)


class Repo:
    def __init__(self, app, name):
        self.app = app
        self.name = name
        self.upstream, self.techname = self.name.split("/", maxsplit=1)
        self.path = self.app.storage.repositories_path.joinpath(
            *self.name.split("/")
        )

    def fetch(self):
        """Clone or update the repository."""
        if not self.is_cloned:
            self._clone()
        self._fetch()

    def scan(self):
        """Scan the modules that have changed since last scan."""
        for from_branch, to_branch in self.app.branches_matrix:
            repo = git.Repo(self.path)
            if not self._check_branches(repo, from_branch, to_branch):
                continue
            self._create_repository_entry(from_branch, to_branch)
            last_from_scan, last_to_scan = self._get_last_scanned_commits(
                from_branch, to_branch
            )
            last_from_commit = repo.rev_parse(f"origin/{from_branch}").hexsha
            last_to_commit = repo.rev_parse(f"origin/{to_branch}").hexsha
            from_branch_updated = last_from_scan != last_from_commit
            to_branch_updated = last_to_scan != last_to_commit
            if from_branch_updated or to_branch_updated:
                from_branch_modules_updated = self._get_modules_updated(
                    last_from_scan, last_from_commit
                )
                to_branch_modules_updated = self._get_modules_updated(
                    last_to_scan, last_to_commit
                )
                modules_updated = sorted(
                    from_branch_modules_updated | to_branch_modules_updated
                )
                logger.info(
                    "%s: %s modules updated on %s",
                    self.name,
                    len(modules_updated),
                    from_branch,
                )
                for module in modules_updated:
                    data = self._scan_module(module, from_branch, to_branch)
                    if data:
                        self._save_module_data(
                            module, from_branch, to_branch, data
                        )
                    time.sleep(3)  # Slow down to not hammer GitHub API
            # Store last scanned commits
            self._save_last_scanned_commits(
                from_branch, to_branch, last_from_commit, last_to_commit
            )

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
        remote_branches = [r.name for r in repo.remotes.origin.refs]
        logger.info(
            "%s: fetch branches %s", self.name, ", ".join(self.app.branches)
        )
        for branch in self.app.branches:
            if f"origin/{branch}" in remote_branches:
                repo.remotes.origin.fetch(branch)

    def _check_branches(self, repo, from_branch, to_branch):
        refs = [r.name for r in repo.remotes.origin.refs]
        fbranch, tbranch = f"origin/{from_branch}", f"origin/{to_branch}"
        return fbranch in refs and tbranch in refs

    def _create_repository_entry(self, from_branch, to_branch):
        con = self.app.backend.db
        cr = con.cursor()
        # Create repository entry
        query = """
            INSERT OR IGNORE INTO repositories(
                org,
                name,
                from_version,
                to_version
            )
            VALUES (?, ?, ?, ?);
        """
        args = (self.upstream, self.techname, from_branch, to_branch)
        cr.execute(query, args)
        con.commit()

    def _scan_module(self, module, from_branch, to_branch):
        logger.info(
            "%s: scan '%s' (%s -> %s)",
            self.name,
            module,
            from_branch,
            to_branch,
        )
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
        except ValueError as exc:
            logger.warning(exc)
        else:
            return json.loads(json_data)

    def _save_module_data(self, module, from_branch, to_branch, data):
        con = self.app.backend.db
        cr = con.cursor()
        # Create or update module entry
        query = """
            INSERT OR REPLACE INTO modules(
                org,
                repo,
                module,
                from_version,
                to_version,
                process,
                existing_pr,
                results
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        existing_pr = results = None
        if data.get("results"):
            results = json.dumps(data["results"])
            if data.get("process") == "migrate":
                existing_pr = json.dumps(data["results"].get("existing_pr"))
        args = (
            self.upstream,
            self.techname,
            module,
            from_branch,
            to_branch,
            data.get("process"),
            existing_pr,
            results,
        )
        cr.execute(query, args)
        con.commit()

    def _get_last_scanned_commits(self, from_branch, to_branch):
        con = self.app.backend.db
        cr = con.cursor()
        query = """
            SELECT from_commit, to_commit
            FROM repositories
            WHERE org=? AND name=? AND from_version=? AND to_version=?;
        """
        args = (self.upstream, self.techname, from_branch, to_branch)
        cr.execute(query, args)
        res = cr.fetchone()
        if res:
            return res[0], res[1]
        return None, None

    def _save_last_scanned_commits(
        self, from_branch, to_branch, from_commit, to_commit
    ):
        con = self.app.backend.db
        cr = con.cursor()
        query = """
            UPDATE repositories
            SET from_commit=?, to_commit=?
            WHERE org=? AND name=? AND from_version=? AND to_version=?;
        """
        args = (
            from_commit,
            to_commit,
            self.upstream,
            self.techname,
            from_branch,
            to_branch,
        )
        cr.execute(query, args)
        con.commit()

    def _get_modules_updated(self, from_commit, to_commit):
        """Return modules updated between `from_commit` and `to_commit`."""
        # Same commits: nothing has changed
        modules = set()
        if from_commit == to_commit:
            return modules
        repo = git.Repo(self.path)
        if not from_commit:
            # No from_commit means first scan: return all available modules
            to_commit = repo.commit(to_commit)
            modules = {
                tree.path
                for tree in to_commit.tree.trees
                if self._filter_module_path(tree.path)
            }
        else:
            # Get only modules updated between the two commits
            from_commit, to_commit = repo.commit(from_commit), repo.commit(
                to_commit
            )
            diffs = to_commit.diff(from_commit, R=True)
            for diff in diffs:
                # Exclude files located in root folder
                if "/" not in diff.a_path:
                    continue
                path = diff.a_path.split("/", maxsplit=1)[0]
                if self._filter_module_path(path):
                    modules.add(path)
        return modules

    def _filter_module_path(self, path):
        if (
            path.startswith("setup")
            or path.startswith(".")
            or path.endswith(".po")
        ):
            return False
        return True
