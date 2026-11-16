"""A source refresh, run in its own short-lived process.

Why a process: parsing a source's whole channel list builds hundreds of
thousands of short-lived objects. Python frees them, but keeps the memory they
took, so one live-channel refresh left the app ~260 MB larger for good
(measured 2026-11-16: 494 -> 754 MB, with only ~30 MB of it still in use). A
process returns everything to the system when it exits, so an app idling in
the tray stays at its resting size however often it refreshes.

The child runs the SAME :class:`~streamselect.core.provider_loader.ProviderLoadThread`
code the app used in-thread, synchronously, against the same database file:
the refresh's own logic is untouched, only where it runs. It reports over a
one-way pipe:

- ``("progress", current, total, message)`` as the loader reports it;
- ``("finished", ok, message, prefix_stats)`` once, last.

The window's side is :class:`streamselect.gui.provider_load_process.ProviderLoadProcess`.
"""

from __future__ import annotations

from loguru import logger


def build_request(provider_id: str, db_url: str, kind: str, loader_kwargs: dict) -> dict:
    """Everything the child needs, as plain picklable data (no Config, no ORM)."""
    from dataclasses import asdict

    from streamselect.core.app_logging import active_log_file
    from streamselect.core.url_policy import get_url_ranking_policy

    return {
        "log_file": active_log_file(),
        "provider_id": provider_id,
        "db_url": db_url,
        "kind": kind,
        "loader": dict(loader_kwargs),
        "url_policy": asdict(get_url_ranking_policy()),
    }


def run_refresh(request: dict, conn) -> None:
    """Child-process entry: refresh one source, report over *conn*, return.

    Never raises: any failure is reported as ``("finished", False, reason, None)``
    so the window always hears how the refresh ended.
    """
    from streamselect.core.app_logging import configure_logging

    configure_logging(request.get("log_file"))
    db = None
    outcome: list = [False, "The refresh ended without reporting a result", None]
    try:
        from PyQt6.QtCore import QCoreApplication

        from streamselect.core.database import Database
        from streamselect.core.provider_loader import ProviderLoadThread
        from streamselect.core.repositories import RepositoryFactory
        from streamselect.core.url_policy import UrlRankingPolicy, set_url_ranking_policy

        set_url_ranking_policy(UrlRankingPolicy(**request["url_policy"]))
        _app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 — QObjects need one
        db = Database(request["db_url"])
        with db.session_scope() as session:
            repos = RepositoryFactory(session)
            row = repos.providers.get_by_id(request["provider_id"])
            provider = repos.providers.to_model(row) if row is not None else None
        if provider is None:
            outcome[:2] = [False, "Provider not found"]
            return
        logger.info("refresh worker: {} refresh of {!r} (pid {})",
                    request["kind"], provider.name, _pid())
        loader = ProviderLoadThread(provider, db, kind=request["kind"], **request["loader"])
        loader.progress.connect(lambda cur, tot, msg: conn.send(("progress", cur, tot, msg)))
        loader.finished.connect(lambda ok, msg: outcome.__setitem__(slice(0, 2), [ok, msg]))
        loader.run()        # in THIS thread: the process is the isolation
        outcome[2] = loader.prefix_stats
    except Exception as exc:  # reported, never raised: the window must hear the end
        logger.exception("refresh worker failed")
        outcome[:2] = [False, str(exc)]
    finally:
        try:
            conn.send(("finished", *outcome))
        finally:
            conn.close()
            if db is not None:
                db.engine.dispose()


def _pid() -> int:
    import os

    return os.getpid()
