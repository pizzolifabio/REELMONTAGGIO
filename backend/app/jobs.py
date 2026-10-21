"""Coda di job su SQLite con un worker in background (render e trascrizioni) e uno scheduler."""
import logging
import threading
import time
import traceback
from typing import Any, Callable

from sqlmodel import select

from .db import session_scope
from .models import Job, ScheduledPost, now

log = logging.getLogger("reel_studio.jobs")

HANDLERS: dict[str, Callable[..., Any]] = {}
_stop = threading.Event()
_wake = threading.Event()


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def enqueue(kind: str, project_id: int | None = None, **payload) -> Job:
    if project_id is not None:
        payload["project_id"] = project_id
    with session_scope() as s:
        job = Job(kind=kind, project_id=project_id, payload=payload)
        s.add(job)
        s.commit()
        s.refresh(job)
    _wake.set()
    return job


class JobContext:
    def __init__(self, job_id: int):
        self.job_id = job_id
        self._last = 0.0

    def progress(self, value: float, message: str | None = None) -> None:
        # limita le scritture su DB
        if message is None and time.monotonic() - self._last < 0.5:
            return
        self._last = time.monotonic()
        with session_scope() as s:
            job = s.get(Job, self.job_id)
            if job:
                job.progress = round(max(0.0, min(value, 1.0)), 3)
                if message is not None:
                    job.message = message
                s.add(job)
                s.commit()


def _next_job() -> Job | None:
    with session_scope() as s:
        job = s.exec(select(Job).where(Job.status == "queued").order_by(Job.id)).first()
        if job:
            job.status, job.started_at = "running", now()
            s.add(job)
            s.commit()
            s.refresh(job)
        return job


def _run(job: Job) -> None:
    fn = HANDLERS.get(job.kind)
    status, error = "done", ""
    try:
        if fn is None:
            raise RuntimeError(f"Nessun handler per {job.kind}")
        fn(JobContext(job.id), **job.payload)
    except Exception as e:  # noqa: BLE001
        status, error = "failed", str(e)
        log.error("Job %s (%s) fallito:\n%s", job.id, job.kind, traceback.format_exc())
    with session_scope() as s:
        j = s.get(Job, job.id)
        j.status, j.error, j.finished_at = status, error[:4000], now()
        if status == "done":
            j.progress = 1
        s.add(j)
        s.commit()


def _worker_loop() -> None:
    while not _stop.is_set():
        job = _next_job()
        if job is None:
            _wake.wait(2)
            _wake.clear()
            continue
        _run(job)


def _scheduler_loop() -> None:
    while not _stop.is_set():
        try:
            with session_scope() as s:
                due = s.exec(
                    select(ScheduledPost).where(ScheduledPost.status == "scheduled", ScheduledPost.scheduled_at <= now())
                ).all()
                for post in due:
                    post.status = "publishing"
                    s.add(post)
                s.commit()
                ids = [p.id for p in due]
            for pid in ids:
                enqueue("publish", post_id=pid)
        except Exception:  # noqa: BLE001
            log.exception("Errore nello scheduler")
        _stop.wait(20)


def start() -> None:
    with session_scope() as s:
        for job in s.exec(select(Job).where(Job.status == "running")).all():
            job.status = "queued"  # job interrotti da un riavvio
            s.add(job)
        s.commit()
    threading.Thread(target=_worker_loop, name="rs-worker", daemon=True).start()
    threading.Thread(target=_scheduler_loop, name="rs-scheduler", daemon=True).start()


def stop() -> None:
    _stop.set()
    _wake.set()
