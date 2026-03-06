"""
Purpose
-------
Unit tests for the psycopg3 adapter utilities used for Postgres connections and
transaction boundaries.

Key behaviors
-------------
- Validates DBConfig environment loading and DSN construction rules.
- Ensures connect(...) opens a connection and always closes it.
- Ensures tx(conn) runs work inside conn.transaction().
- Ensures dict_rows(conn) configures dict-like row factories.

Conventions
-----------
- psycopg is fully mocked; tests never open a real database connection.
- Environment variables are controlled via pytest monkeypatch.
- Tests assert behavior via observable side effects on fakes.

Downstream usage
----------------
Run with pytest:
    pytest -q

These tests protect the connection/transaction contract expected by ETL code.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import FrozenInstanceError
from typing import Any, Dict, Optional, Type

import pytest

from db.psycopg_adapter import (
    DBConfig,
    as_dsn,
    connect,
    dict_rows,
    tx,
)
import db.psycopg_adapter as psycopg_adapter


class _FakeTransaction(AbstractContextManager[None]):
    """
    Purpose
    -------
    Stand-in for a psycopg transaction context manager.

    Key behaviors
    -------------
    - Records whether it was entered.
    - Records whether exit occurred cleanly (commit) or with error (rollback).

    Parameters
    ----------
    None

    Attributes
    ----------
    entered : bool
        True once __enter__ is called.
    committed : bool
        True if the context exits without an exception.
    rolled_back : bool
        True if the context exits with an exception.

    Notes
    -----
    - This imitates the observable contract the adapter relies on.
    """

    def __init__(self) -> None:
        self.entered = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> None:
        self.entered = True
        return None

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[Any],
    ) -> bool:
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class _FakeConnection:
    """
    Purpose
    -------
    Minimal fake psycopg Connection used to observe adapter behavior.

    Key behaviors
    -------------
    - Provides .transaction() returning a controllable context manager.
    - Records whether close() was called.
    - Allows mutation of row_factory.

    Parameters
    ----------
    None

    Attributes
    ----------
    closed : bool
        True once close() is called.
    last_transaction : _FakeTransaction | None
        Most recently created transaction context.
    row_factory : Any
        Mutable attribute set by dict_rows().

    Notes
    -----
    - This avoids any dependency on real psycopg.Connection internals.
    """

    def __init__(self) -> None:
        self.closed = False
        self.last_transaction: Optional[_FakeTransaction] = None
        self.row_factory: Any = None

    def close(self) -> None:
        """
        Mark the connection as closed.

        Parameters
        ----------
        None

        Returns
        -------
        None
            Sets an observable flag.
        """

        self.closed = True

    def transaction(self) -> _FakeTransaction:
        """
        Return a new transaction context manager.

        Parameters
        ----------
        None

        Returns
        -------
        _FakeTransaction
            New transaction context for a unit of work.
        """

        self.last_transaction = _FakeTransaction()
        return self.last_transaction


def test_dbconfig_from_env_prefers_database_url(monkeypatch: Any) -> None:
    """
    DBConfig.from_env prefers DATABASE_URL and ignores PG* variables.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        Assertions validate DBConfig construction.

    Notes
    -----
    - DATABASE_URL is treated as authoritative by convention.
    """

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("PGHOST", "ignored")
    cfg = DBConfig.from_env()
    assert cfg.dsn == "postgresql://u:p@h:5432/db"
    assert cfg.host is None
    assert cfg.dbname is None


def test_dbconfig_from_env_uses_pg_variables_when_no_database_url(monkeypatch: Any) -> None:
    """
    DBConfig.from_env uses PG* variables when DATABASE_URL is not set.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        Assertions validate DBConfig construction.

    Notes
    -----
    - PGPORT is parsed as an integer when present.
    """

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGHOST", "localhost")
    monkeypatch.setenv("PGPORT", "5433")
    monkeypatch.setenv("PGDATABASE", "app")
    monkeypatch.setenv("PGUSER", "dor")
    monkeypatch.setenv("PGPASSWORD", "pw")
    monkeypatch.setenv("PGSSLMODE", "require")

    cfg = DBConfig.from_env()
    assert cfg.dsn is None
    assert cfg.host == "localhost"
    assert cfg.port == 5433
    assert cfg.dbname == "app"
    assert cfg.user == "dor"
    assert cfg.password == "pw"
    assert cfg.sslmode == "require"


def test_dbconfig_from_env_raises_when_incomplete(monkeypatch: Any) -> None:
    """
    DBConfig.from_env raises ValueError when no DSN is set and required PG vars
    are missing.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts that ValueError is raised.

    Raises
    ------
    ValueError
        Raised by DBConfig.from_env under incomplete configuration.
    """

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGDATABASE", raising=False)
    monkeypatch.delenv("PGUSER", raising=False)

    with pytest.raises(ValueError):
        DBConfig.from_env()


def test_as_dsn_returns_cfg_dsn_when_set() -> None:
    """
    as_dsn returns cfg.dsn unchanged when it is set.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Assertions validate behavior.
    """

    cfg = DBConfig(dsn="postgresql://u:p@h/db")
    assert as_dsn(cfg) == "postgresql://u:p@h/db"


def test_as_dsn_builds_libpq_style_dsn_with_optional_fields() -> None:
    """
    as_dsn builds a libpq-style DSN when cfg.dsn is not set.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Assertions validate DSN content.

    Notes
    -----
    - Optional fields are included only when non-None.
    """

    cfg = DBConfig(
        host="h",
        port=5432,
        dbname="db",
        user="u",
        password="p",
        sslmode="require",
    )
    dsn = as_dsn(cfg)
    assert "host=h" in dsn
    assert "port=5432" in dsn
    assert "dbname=db" in dsn
    assert "user=u" in dsn
    assert "password=p" in dsn
    assert "sslmode=require" in dsn


def test_as_dsn_raises_when_incomplete_and_no_dsn() -> None:
    """
    as_dsn raises ValueError when cfg.dsn is not set and required fields are
    missing.

    Parameters
    ----------
    None

    Returns
    -------
    None
        The test asserts that ValueError is raised.

    Raises
    ------
    ValueError
        Raised by as_dsn under incomplete configuration.
    """

    cfg = DBConfig(host=None, dbname="db", user="u")
    with pytest.raises(ValueError):
        as_dsn(cfg)


def test_connect_opens_and_closes_connection_for_string_dsn(monkeypatch: Any) -> None:
    """
    connect opens a connection using a DSN string and always closes it.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        Assertions validate psycopg.connect arguments and close behavior.
    """

    calls: Dict[str, Any] = {}
    fake_conn = _FakeConnection()

    def _fake_connect(dsn: str) -> _FakeConnection:
        calls["dsn"] = dsn
        return fake_conn

    monkeypatch.setattr(psycopg_adapter, "psycopg", type("_P", (), {"connect": _fake_connect}))

    with connect("host=h dbname=db user=u") as conn:
        assert conn is fake_conn
        assert fake_conn.closed is False

    assert calls["dsn"] == "host=h dbname=db user=u"
    assert fake_conn.closed is True


def test_connect_opens_and_closes_connection_for_dbconfig(monkeypatch: Any) -> None:
    """
    connect opens a connection using a DBConfig and always closes it.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        Assertions validate DSN conversion and close behavior.
    """

    calls: Dict[str, Any] = {}
    fake_conn = _FakeConnection()
    cfg = DBConfig(host="h", port=5432, dbname="db", user="u")

    def _fake_connect(dsn: str) -> _FakeConnection:
        calls["dsn"] = dsn
        return fake_conn

    monkeypatch.setattr(psycopg_adapter, "psycopg", type("_P", (), {"connect": _fake_connect}))

    with connect(cfg) as conn:
        assert conn is fake_conn

    assert "host=h" in calls["dsn"]
    assert "dbname=db" in calls["dsn"]
    assert "user=u" in calls["dsn"]
    assert "port=5432" in calls["dsn"]
    assert fake_conn.closed is True


def test_connect_closes_connection_when_body_raises(monkeypatch: Any) -> None:
    """
    connect closes the connection even if the caller body raises.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts close behavior on exceptions.

    Raises
    ------
    RuntimeError
        Raised by this test to simulate caller failure.
    """

    fake_conn = _FakeConnection()

    def _fake_connect(_: str) -> _FakeConnection:
        return fake_conn

    monkeypatch.setattr(psycopg_adapter, "psycopg", type("_P", (), {"connect": _fake_connect}))

    with pytest.raises(RuntimeError):
        with connect("host=h dbname=db user=u"):
            raise RuntimeError("boom")

    assert fake_conn.closed is True


def test_tx_runs_inside_connection_transaction_and_commits_on_success() -> None:
    """
    tx enters conn.transaction() and commits on successful exit.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Assertions validate transaction context usage.
    """

    conn = _FakeConnection()
    with tx(conn):
        pass

    assert conn.last_transaction is not None
    assert conn.last_transaction.entered is True
    assert conn.last_transaction.committed is True
    assert conn.last_transaction.rolled_back is False


def test_tx_reraises_errors_and_rolls_back_via_transaction_context() -> None:
    """
    tx re-raises caller exceptions and the underlying transaction context records
    a rollback exit.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Assertions validate error propagation and rollback signaling.

    Raises
    ------
    ValueError
        Raised by the test body to simulate a failing unit of work.
    """

    conn = _FakeConnection()

    with pytest.raises(ValueError):
        with tx(conn):
            raise ValueError("fail")

    assert conn.last_transaction is not None
    assert conn.last_transaction.entered is True
    assert conn.last_transaction.committed is False
    assert conn.last_transaction.rolled_back is True


def test_dict_rows_sets_row_factory_to_dict_row(monkeypatch: Any) -> None:
    """
    dict_rows sets conn.row_factory to psycopg.rows.dict_row.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        Assertions validate row_factory mutation.
    """

    conn = _FakeConnection()
    sentinel = object()

    monkeypatch.setattr(psycopg_adapter, "dict_row", sentinel)
    dict_rows(conn)  # type: ignore[arg-type]

    assert conn.row_factory is sentinel


def test_dbconfig_is_frozen_dataclass() -> None:
    """
    DBConfig is a frozen dataclass and cannot be mutated.

    Parameters
    ----------
    None

    Returns
    -------
    None
        The test asserts immutability via FrozenInstanceError.

    Raises
    ------
    FrozenInstanceError
        Raised when attempting to mutate a frozen dataclass.
    """

    cfg = DBConfig(dsn="postgresql://u:p@h/db")
    with pytest.raises(FrozenInstanceError):
        cfg.dsn = None  # type: ignore[misc]
