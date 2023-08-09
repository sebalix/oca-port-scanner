# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import pathlib
import os


class Storage:
    """Manage the storage of Git repositories and reporting data."""

    _storage_dirname = "oca-port-scanner"
    _repositories_dirname = "repositories"
    _data_dirname = "data"

    def __init__(self, app):
        self.app = app
        self.dir_path = self._get_dir_path()
        self.repositories_path = self.dir_path.joinpath(self._repositories_dirname)
        self.repositories_path.mkdir(parents=True, exist_ok=True)
        self.data_path = self.dir_path.joinpath(self._data_dirname)
        self.data_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_dir_path(cls):
        """Return the path of the cache directory."""
        default_data_dir_path = pathlib.Path.home().joinpath(".local").joinpath("share")
        return pathlib.Path(
            os.environ.get("XDG_DATA_HOME", default_data_dir_path), cls._storage_dirname
        )
