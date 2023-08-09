# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import pathlib
import sqlite3


class Backend:
    """Manage the SQLite3 database."""

    def __init__(self, config):
        self.config = config
        self.db_path = pathlib.Path(self.config["options"]["database_path"])
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        cr = self.db.cursor()
        create_idx = "CREATE INDEX IF NOT EXISTS"
        repo_stats_trigger_query = """
            UPDATE repositories
            SET
                nb_modules=(
                    SELECT COUNT(*) FROM modules m
                    WHERE m.org=repositories.org
                    AND m.repo=repositories.name
                    AND m.from_version=repositories.from_version
                    AND m.to_version=repositories.to_version
                ),
                nb_modules_migrated=(
                    SELECT COUNT(*) FROM modules m
                    WHERE m.org=repositories.org
                    AND m.repo=repositories.name
                    AND m.from_version=repositories.from_version
                    AND m.to_version=repositories.to_version
                    AND (process IS NULL OR process = 'port_commits')
                ),
                nb_modules_to_migrate=(
                    SELECT COUNT(*) FROM modules m
                    WHERE m.org=repositories.org
                    AND m.repo=repositories.name
                    AND m.from_version=repositories.from_version
                    AND m.to_version=repositories.to_version
                    AND process = 'migrate'
                    AND results NOT LIKE '%existing_pr%'
                ),
                nb_modules_to_review=(
                    SELECT COUNT(*) FROM modules m
                    WHERE m.org=repositories.org
                    AND m.repo=repositories.name
                    AND m.from_version=repositories.from_version
                    AND m.to_version=repositories.to_version
                    AND process = 'migrate'
                    AND results LIKE '%existing_pr%'
                ),
                nb_modules_to_port_commits=(
                    SELECT COUNT(*) FROM modules m
                    WHERE m.org=repositories.org
                    AND m.repo=repositories.name
                    AND m.from_version=repositories.from_version
                    AND m.to_version=repositories.to_version
                    AND process = 'port_commits'
                )
            WHERE org=NEW.org
            AND name=NEW.repo
            AND from_version=NEW.from_version
            AND to_version=NEW.to_version;
        """
        queries = [
            # repositories
            """
            CREATE TABLE IF NOT EXISTS repositories (
                org CHAR,
                name CHAR,
                from_version CHAR,
                to_version CHAR,
                from_commit CHAR,
                to_commit CHAR,
                nb_modules INTEGER DEFAULT 0,
                nb_modules_migrated INTEGER DEFAULT 0,
                nb_modules_to_migrate INTEGER DEFAULT 0,
                nb_modules_to_review INTEGER DEFAULT 0,
                nb_modules_to_port_commits INTEGER DEFAULT 0,
                UNIQUE(org, name, from_version, to_version)
            );
            """,
            f"""
            {create_idx} repositories_name_index
                ON repositories (name);
            """,
            # modules
            """
            CREATE TABLE IF NOT EXISTS modules (
                org CHAR,
                repo CHAR,
                module CHAR,
                from_version CHAR,
                to_version CHAR,
                process CHAR,
                existing_pr TEXT,
                results TEXT,
                UNIQUE(org, repo, module, from_version, to_version),
                FOREIGN KEY (org, repo, from_version, to_version)
                REFERENCES repositories (org, name, from_version, to_version)
                ON DELETE CASCADE
            );
            """,
            f"{create_idx} migrations_module_index ON modules (module);",
            f"""
            {create_idx} migrations_from_to_version_index
                ON modules (from_version, to_version);
            """,
            f"{create_idx} migrations_process_index ON modules (process);",
            # triggers to compute some repository stats
            #   - after insert on modules
            f"""
            CREATE TRIGGER IF NOT EXISTS repositories_stats_insert_trigger
            AFTER INSERT ON modules
            BEGIN
                {repo_stats_trigger_query}
            END;
            """,
            #   - after update on modules
            f"""
            CREATE TRIGGER IF NOT EXISTS repositories_stats_update_trigger
            AFTER UPDATE ON modules
            BEGIN
                {repo_stats_trigger_query}
            END;
            """,
        ]
        for query in queries:
            cr.execute(query)
