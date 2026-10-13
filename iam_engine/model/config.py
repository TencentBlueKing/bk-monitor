"""Model-registration options, unrelated to existing user-authorizations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationConfig:
    mode: str = "manual"
    directory: str = ""
    allow_destructive: bool = False
    auto_makemigrations: bool = False
    database: str = "default"
    table_name: str = "iam_migration_state"
