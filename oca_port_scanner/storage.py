# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import pathlib


class Storage:
    """Manage the storage of Git repositories."""

    def __init__(self, config):
        self.config = config
        self.repositories_path = pathlib.Path(
            self.config["options"]["repositories_path"]
        )
        self.repositories_path.mkdir(parents=True, exist_ok=True)
