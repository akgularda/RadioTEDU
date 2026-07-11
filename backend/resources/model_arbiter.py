"""Serialize use of the low-RAM Qwen and Ollama model resource."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Condition
from time import monotonic
from typing import Callable, Deque, Literal, TypeVar


ModelKind = Literal["qwen", "ollama"]
_Result = TypeVar("_Result")


class LeaseUnavailableError(TimeoutError):
    """The shared model is currently leased."""


class LeaseQueueFullError(LeaseUnavailableError):
    """The bounded wait queue cannot accept another model request."""


class LeaseTimeoutError(LeaseUnavailableError):
    """A request reached its waiting deadline before a model became free."""


@dataclass(frozen=True)
class ModelLease:
    kind: ModelKind
    owner: str
    acquired_at: float
    deadline: float


class ModelArbiter:
    """Hold at most one model lease, irrespective of its model kind."""

    def __init__(
        self,
        *,
        max_queue: int = 8,
        default_timeout: float = 5.0,
        lease_seconds: float = 30.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_queue < 0:
            raise ValueError("max_queue must be non-negative")
        if default_timeout < 0:
            raise ValueError("default_timeout must be non-negative")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._max_queue = max_queue
        self._default_timeout = default_timeout
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._condition = Condition()
        self._waiters: Deque[object] = deque()
        self._active: ModelLease | None = None

    @property
    def active_lease(self) -> ModelLease | None:
        with self._condition:
            self._expire_active_lease()
            return self._active

    @property
    def queue_depth(self) -> int:
        with self._condition:
            return len(self._waiters)

    def acquire(
        self,
        kind: ModelKind,
        owner: str,
        *,
        timeout: float | None = None,
    ) -> ModelLease:
        self._validate_request(kind, owner, timeout)
        wait_limit = self._default_timeout if timeout is None else timeout
        request = object()
        with self._condition:
            self._expire_active_lease()
            if self._active is None and not self._waiters:
                return self._grant(kind, owner)
            if self._max_queue == 0 or len(self._waiters) >= self._max_queue:
                raise LeaseQueueFullError("the shared model wait queue is full")

            self._waiters.append(request)
            deadline = self._clock() + wait_limit
            while True:
                self._expire_active_lease()
                if self._active is None and self._waiters[0] is request:
                    self._waiters.popleft()
                    lease = self._grant(kind, owner)
                    self._condition.notify_all()
                    return lease
                now = self._clock()
                remaining = deadline - now
                if remaining <= 0:
                    self._waiters.remove(request)
                    self._condition.notify_all()
                    raise LeaseTimeoutError("timed out waiting for the shared model")
                active_deadline = self._active.deadline if self._active else deadline
                self._condition.wait(min(remaining, max(0.0, active_deadline - now)))

    def release(self, lease: ModelLease) -> bool:
        with self._condition:
            self._expire_active_lease()
            if self._active is not lease:
                return False
            self._active = None
            self._condition.notify_all()
            return True

    def run(
        self,
        kind: ModelKind,
        owner: str,
        operation: Callable[[], _Result],
        *,
        timeout: float | None = None,
    ) -> _Result:
        """Run model work and release the scarce resource even on failure."""

        lease = self.acquire(kind, owner, timeout=timeout)
        try:
            return operation()
        finally:
            self.release(lease)

    def _grant(self, kind: ModelKind, owner: str) -> ModelLease:
        now = self._clock()
        lease = ModelLease(kind, owner, now, now + self._lease_seconds)
        self._active = lease
        return lease

    def _expire_active_lease(self) -> None:
        if self._active is not None and self._clock() >= self._active.deadline:
            self._active = None
            self._condition.notify_all()

    @staticmethod
    def _validate_request(kind: ModelKind, owner: str, timeout: float | None) -> None:
        if kind not in ("qwen", "ollama"):
            raise ValueError("kind must be 'qwen' or 'ollama'")
        if not owner.strip():
            raise ValueError("owner must not be blank")
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")
