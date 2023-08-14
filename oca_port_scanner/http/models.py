# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import csv
import io
import json

from pydantic import BaseModel, computed_field, model_validator

from ..backend import Backend
from ..config import Config

config = Config()
config.init()

backend = Backend(config, check_same_thread=False)


class Repository(BaseModel):
    org: str
    name: str
    from_version: str = None
    to_version: str = None
    nb_modules: int
    nb_modules_migrated: int
    nb_modules_to_migrate: int
    nb_modules_to_review: int
    nb_modules_to_port_commits: int

    @computed_field
    def fullname(self) -> str:
        return f"{self.org}/{self.name}"


class PR(BaseModel):
    title: str
    number: int
    url: str
    author: str
    merged_at: str = None


class Module(BaseModel):
    __slots__ = ("_org", "_repo", "_existing_pr_data", "_results_data")
    name: str
    from_version: str = None
    to_version: str = None
    process: str = None
    repository: Repository = None
    existing_pr: PR = None

    def __init__(self, **kwargs):
        for field in self.__slots__:
            object.__setattr__(self, field, kwargs.pop(field))
        super().__init__(**kwargs)

    @model_validator(mode="after")
    def compute_fields(self) -> "Module":
        # Use a 'model_validator' instead of a computed field as the latter
        # can't be serialized by FastAPI
        if self._existing_pr_data:
            pr_data = json.loads(self._existing_pr_data)
            self.existing_pr = PR(**pr_data)
        if self._org and self._repo:
            where = "org=? AND name=? AND from_version=? AND to_version=?"
            args = (self._org, self._repo, self.from_version, self.to_version)
            repositories = get_repositories(where=where, args=args)
            self.repository = repositories[0]
        return self

    @classmethod
    def get_csv(cls, from_version, to_version, module_names):
        """Generate a CSV migration report of modules for given versions."""
        where = "from_version=? AND to_version=? AND module IN (%s)" % (
            ",".join(["?"] * len(module_names))
        )
        args = (from_version, to_version, *module_names)
        modules = get_modules(where=where, args=args)
        with io.StringIO() as file_:
            fields = [
                "repository",
                "module",
                "status",
                "info",
            ]
            writer = csv.DictWriter(file_, fields)
            writer.writeheader()
            for module in modules:
                row = module._get_csv_row()
                writer.writerow(row)
                module_names.pop(module_names.index(module.name))
            # Append remaining modules that haven't been recognized
            if module_names:
                writer.writerow({})
                writer.writerow({"repository": "UNKNOWN"})
            for module_name in module_names:
                row = {
                    "repository": "",
                    "module": module_name,
                    "status": "migrate",
                }
                writer.writerow(row)
            file_.seek(0)
            content = file_.read()
        return content

    def _get_csv_row(self):
        row = {
            "repository": self.repository.fullname,
            "module": self.name,
            "status": self.process,
        }
        if not self.process:
            row["status"] = "available"
        elif self.process == "port_commits":
            results = (
                json.loads(self._results_data) if self._results_data else {}
            )
            commits = [pr["missing_commits"] for pr in results.values()]
            nb_commits = len(commits)
            info = f"{nb_commits} commits to check/port from:"
            info = "\n".join(
                [info] + [f"- {pr['url']}" for pr in results.values()]
            )
            row["info"] = info
        if self.existing_pr:
            row["status"] = "to review"
            row["info"] = self.existing_pr.url
        return row


def get_repositories(where="", args=tuple()):
    con = backend.db
    cr = con.cursor()
    query = """
        SELECT
            org,
            name,
            from_version,
            to_version,
            nb_modules,
            nb_modules_migrated,
            nb_modules_to_migrate,
            nb_modules_to_review,
            nb_modules_to_port_commits
        FROM repositories
    """
    if where:
        query = f"{query} WHERE {where}"
    cr.execute(query, args)
    rows = cr.fetchall()
    repositories = []
    for row in rows:
        repo = Repository(
            org=row[0],
            name=row[1],
            from_version=row[2],
            to_version=row[3],
            nb_modules=row[4],
            nb_modules_migrated=row[5],
            nb_modules_to_migrate=row[6],
            nb_modules_to_review=row[7],
            nb_modules_to_port_commits=row[8],
        )
        repositories.append(repo)
    return repositories


def get_modules(where="", args=tuple()):
    con = backend.db
    cr = con.cursor()
    query = """
        SELECT
            org,
            repo,
            module,
            from_version,
            to_version,
            process,
            existing_pr,
            results
        FROM modules
    """
    if where:
        query = f"{query} WHERE {where}"
    cr.execute(query, args)
    rows = cr.fetchall()
    modules = []
    for row in rows:
        module = Module(
            _org=row[0],
            _repo=row[1],
            name=row[2],
            from_version=row[3],
            to_version=row[4],
            process=row[5],
            _existing_pr_data=row[6],
            _results_data=row[7],
        )
        modules.append(module)
    return modules


def get_versions():
    con = backend.db
    cr = con.cursor()
    query = "SELECT DISTINCT from_version, to_version FROM modules"
    cr.execute(query)
    rows = cr.fetchall()
    return rows
