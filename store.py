"""
Session storage module. Handles the "memory" for each user session.
"""
from __future__ import annotations
import json, os, uuid, time, tempfile, logging
import settings

log = logging.getLogger("domain-agent.store")

class SessionStore:
    def __init__(self):
        self._cache: dict[str, dict] = {}
        if settings.PERSIST_SESSIONS_TO_FILE and not os.path.exists(settings.SESSION_FILE_DIR):
            os.makedirs(settings.SESSION_FILE_DIR)
            log.info(f"Created session directory: {settings.SESSION_FILE_DIR}")

    def new(self) -> str:
        sid = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self._write(sid, {"suggested": [], "history": {}})
        log.info(f"New session started: {sid}")
        return sid

    def seen(self, sid: str) -> set[str]:
        return set(self._read(sid).get("suggested", []))

    def add(self, sid: str, names: list[str]) -> None:
        blob = self._read(sid)
        if "suggested" not in blob:
            blob["suggested"] = []
        for n in names:
            if n not in blob["suggested"]:
                blob["suggested"].append(n)
        self._write(sid, blob)

    def record_results(self, sid: str, available: dict, taken: dict) -> None:
        """Store availability results for later retrieval."""
        blob = self._read(sid)
        history = blob.setdefault("history", {})
        for name, source in available.items():
            if name not in history:
                history[name] = {"status": "AVAILABLE", "source": source}
        for name, source in taken.items():
            if name not in history:
                history[name] = {"status": "TAKEN", "source": source}
        blob["history"] = history
        self._write(sid, blob)

    def history(self, sid: str) -> dict:
        return self._read(sid).get("history", {})

    def _path(self, sid: str) -> str:
        root = settings.SESSION_FILE_DIR or tempfile.gettempdir()
        return os.path.join(root, f"session_{sid}.json")

    def _read(self, sid: str) -> dict:
        if sid not in self._cache and not settings.PERSIST_SESSIONS_TO_FILE:
            self._cache[sid] = {"suggested": [], "history": {}}
        if settings.PERSIST_SESSIONS_TO_FILE:
            try:
                with open(self._path(sid)) as fp:
                    return json.load(fp)
            except FileNotFoundError:
                return {"suggested": [], "history": {}}
        return self._cache[sid]

    def _write(self, sid: str, blob: dict):
        if settings.PERSIST_SESSIONS_TO_FILE:
            with open(self._path(sid), "w") as fp: json.dump(blob, fp, indent=2)
        else:
            self._cache[sid] = blob
