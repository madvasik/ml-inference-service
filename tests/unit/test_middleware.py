from backend.app.middleware import RedisRateLimitStore


class FakePipeline:
    def __init__(self, storage: dict[str, int]):
        self._storage = storage
        self._operations: list[tuple[str, str, int | None]] = []

    def incr(self, key: str):
        self._operations.append(("incr", key, None))
        return self

    def expire(self, key: str, ttl: int):
        self._operations.append(("expire", key, ttl))
        return self

    def execute(self):
        results = []
        for operation, key, value in self._operations:
            if operation == "incr":
                self._storage[key] = self._storage.get(key, 0) + 1
                results.append(self._storage[key])
            else:
                results.append(True)
        return results


class FakeRedis:
    def __init__(self):
        self.storage: dict[str, int] = {}

    def pipeline(self):
        return FakePipeline(self.storage)


def test_redis_rate_limit_store_uses_shared_backend(monkeypatch):
    fake_redis = FakeRedis()
    store_a = RedisRateLimitStore(redis_client=fake_redis)
    store_b = RedisRateLimitStore(redis_client=fake_redis)
    monkeypatch.setattr("backend.app.middleware.time.time", lambda: 125)

    assert store_a.increment("user:1", limit=2, window=60) == (True, 1, 180)
    assert store_b.increment("user:1", limit=2, window=60) == (True, 0, 180)
    assert store_a.increment("user:1", limit=2, window=60) == (False, 0, 180)
