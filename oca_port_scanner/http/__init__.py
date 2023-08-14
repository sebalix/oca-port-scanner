# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

from typing import Annotated

import pathlib
import re

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .models import (
    Repository,
    Module,
    get_repositories,
    get_modules,
    get_versions,
)

app = FastAPI()

current_dir_path = pathlib.Path(__file__).parent.resolve()
app.mount(
    "/static",
    StaticFiles(directory=current_dir_path.joinpath("static")),
    name="static",
)
templates = Jinja2Templates(directory=current_dir_path.joinpath("templates"))


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    versions = get_versions()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "versions": versions,
        },
    )


@app.post("/report", response_class=Response)
async def report(
    versions: Annotated[str, Form()], modules: Annotated[str, Form()] = None
):
    versions = versions.split(",")
    if len(versions) != 2:
        return HTMLResponse("Wrong 'versions' parameter", status_code=400)
    from_version, to_version = versions
    module_names = re.split(r"\W+", modules) if modules else []
    csv_content = Module.get_csv(from_version, to_version, module_names)
    headers = {
        "Content-Disposition": "attachment;filename=modules_report.csv",
    }
    return Response(csv_content, headers=headers, media_type="text/csv")


@app.get("/api/repositories")
async def api_repositories(
    org: str = None,
    name: str = None,
    from_version: str = None,
    to_version: str = None,
) -> list[Repository]:
    where = []
    args = tuple()
    if org:
        where.append("org=?")
        args += (org,)
    if name:
        where.append("name=?")
        args += (name,)
    if from_version:
        where.append("from_version=?")
        args += (from_version,)
    if to_version:
        where.append("to_version=?")
        args += (to_version,)
    return get_repositories(where=" AND ".join(where), args=args)


@app.get("/api/modules")
async def api_modules(
    org: str = None,
    repo: str = None,
    from_version: str = None,
    to_version: str = None,
    process: str = None,
    existing_pr: bool = None,
) -> list[Module]:
    where = []
    args = tuple()
    if org:
        where.append("org=?")
        args += (org,)
    if repo:
        where.append("repo=?")
        args += (repo,)
    if from_version:
        where.append("from_version=?")
        args += (from_version,)
    if to_version:
        where.append("to_version=?")
        args += (to_version,)
    if process:
        where.append("process=?")
        args += (process,)
    if existing_pr:
        where.append("existing_pr=?")
        args += (existing_pr,)
    modules = get_modules(where=" AND ".join(where), args=args)
    return modules
