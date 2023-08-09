# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import json
import os
import pathlib


class Config(dict):
    _dirname = "oca-port-scanner"
    _default_config_filename = "oca-port-scanner.json"
    _default_db_filename = "data.db"

    def init(self):
        """Read or create the configuration file if it doesn't exist."""
        storage_path = self._get_default_storage_path()
        database_path = storage_path.joinpath(self._default_db_filename)
        config_path = self._get_config_path()
        if config_path.exists():
            with open(config_path) as file_:
                self.update(json.load(file_))
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            # Default configuration file
            self.update(
                {
                    "options": {
                        "repositories_path": str(storage_path),
                        "database_path": str(database_path),
                    },
                    "branches_matrix": [
                        ("14.0", "15.0"),
                        ("14.0", "16.0"),
                        ("15.0", "16.0"),
                    ],
                    "repositories": [
                        "OCA/server-env",
                        "OCA/server-tools",
                    ],
                }
            )
            with open(config_path, "w") as file_:
                json.dump(self, file_, indent=4)

    @classmethod
    def _get_config_path(cls):
        """Return the path of the configuration file."""
        default_config_dir_path = pathlib.Path.home().joinpath(".config")
        return pathlib.Path(
            os.environ.get("XDG_CONFIG_HOME", default_config_dir_path),
            cls._dirname,
            cls._default_config_filename,
        )

    @classmethod
    def _get_default_storage_path(cls):
        """Return the path of the data directory."""
        default_data_dir_path = (
            pathlib.Path.home().joinpath(".local").joinpath("share")
        )
        return pathlib.Path(
            os.environ.get("XDG_DATA_HOME", default_data_dir_path),
            cls._dirname,
        )
