"""Base repository for raw-SQL transitional access."""

from __future__ import annotations

from database import execute, fetchall, fetchone


class BaseRepository:
    fetchone = staticmethod(fetchone)
    fetchall = staticmethod(fetchall)
    execute = staticmethod(execute)
