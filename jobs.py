"""
Visotale — arka plan iş (job) takibi.

Basit, bellek-içi bir job deposu. Railway'de TEK instance çalıştığımız
sürece yeterli — birden fazla instance'a ölçeklenirsek (yatay ölçekleme)
bunun yerine Redis gibi paylaşımlı bir depo gerekir.
"""

import threading
import time
import uuid

JOBS = {}
_LOCK = threading.Lock()

JOB_TTL_S = 3600  # 1 saatten eski işleri bellekten temizle (basit sızıntı önlemi)


def create_job(meta: dict) -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        JOBS[job_id] = {
            "status": "pending",   # pending -> done | error
            "created_at": time.time(),
            "result": None,
            "error": None,
            "meta": meta,
        }
        _cleanup_old_locked()
    return job_id


def get_job(job_id: str):
    with _LOCK:
        return JOBS.get(job_id)


def set_job_done(job_id: str, result: dict):
    with _LOCK:
        if job_id in JOBS:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result


def set_job_error(job_id: str, error: str):
    with _LOCK:
        if job_id in JOBS:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = error


def _cleanup_old_locked():
    cutoff = time.time() - JOB_TTL_S
    stale = [jid for jid, j in JOBS.items() if j["created_at"] < cutoff]
    for jid in stale:
        JOBS.pop(jid, None)
