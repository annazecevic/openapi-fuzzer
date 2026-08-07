import asyncio
import time

from fuzzer.runner.rate_limiter import RateLimiter


def test_zero_rate_never_waits():
    limiter = RateLimiter(0)

    start = time.perf_counter()
    asyncio.run(limiter.acquire())
    elapsed = time.perf_counter() - start

    assert elapsed < 0.05


def test_low_rate_slows_down_bursts():
    # Bucket kreće pun (requests_per_second tokena), pa prva 2 poziva prolaze
    # odmah, a preostala 3 čekaju da se tokeni dopune po stopi od 2/s —
    # ukupno bar ~1s za 5 uzastopnih poziva.
    limiter = RateLimiter(2)

    async def acquire_five():
        for _ in range(5):
            await limiter.acquire()

    start = time.perf_counter()
    asyncio.run(acquire_five())
    elapsed = time.perf_counter() - start

    assert elapsed >= 0.9
