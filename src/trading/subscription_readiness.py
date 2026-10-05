"""gRPC continuity gate; no network or implicit state recovery."""
from threading import RLock

class CacheNotReadyError(ValueError):
    code = "CACHE_NOT_READY"
    def __init__(self, status):
        self.status = status
        super().__init__(status.get("reason") or "Cache is not ready or frozen continuity changed")

class SubscriptionReadiness:
    def __init__(self, fork_id, required_accounts):
        self._required = set(required_accounts)
        if not fork_id or not self._required or any(not k for k in self._required):
            raise ValueError("Provide selected fork and required account identities")
        self._fork_id = fork_id
        self._generation = 0
        self._state = "initializing"
        self._validated = set()
        self._reason = None
        self._lock = RLock()

    def status(self):
        with self._lock:
            return dict(state=self._state, generation=self._generation, fork_id=self._fork_id,
                        missing_accounts=sorted(self._required - self._validated), reason=self._reason)

    def interrupt(self, reason):
        with self._lock:
            self._generation += 1
            self._validated.clear()
            self._reason = reason
            self._state = "continuity-broken"

    def begin_recovery(self, fork_id):
        if not fork_id: raise ValueError("Select a fork explicitly")
        with self._lock:
            self._generation += 1
            self._fork_id = fork_id
            self._validated.clear()
            self._reason = None
            self._state = "recovering"
            return self._generation

    def require_accounts(self, keys):
        keys = set(keys)
        if any(not k for k in keys): raise ValueError("Missing required account identity")
        with self._lock:
            if keys - self._required:
                self._generation += 1
                self._validated.clear()
                self._required.update(keys)
                # Discovering another dependency cannot restore stream continuity.
                if self._state != "continuity-broken":
                    self._state = "recovering"
            return self._generation

    def mark_validated(self, keys, generation, fork_id):
        with self._lock:
            if generation != self._generation or fork_id != self._fork_id or self._state == "continuity-broken":
                return False
            self._validated.update(set(keys) & self._required)
            if self._validated == self._required: self._state = "ready"
            return self._state == "ready"

    def guard(self):
        with self._lock:
            generation = self._generation
        def check():
            with self._lock:
                if self._state == "ready" and self._generation == generation:
                    return
                # Materialize diagnostics only on the error path, not on every
                # account read/quote/signing readiness check.
                raise CacheNotReadyError(self.status())
        check()
        return check
