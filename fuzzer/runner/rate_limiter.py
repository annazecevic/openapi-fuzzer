import asyncio
import time


class RateLimiter:
    """Globalni token-bucket limiter — ograničava UKUPAN broj zahteva
    u sekundi, bez obzira na concurrency."""

    def __init__(self, requests_per_second: float):
        self.requests_per_second = requests_per_second
        self.tokens = requests_per_second
        self.max_tokens = requests_per_second
        self.last_refill = time.perf_counter()
        self.lock = asyncio.Lock()

    async def acquire(self):
        if self.requests_per_second <= 0:
            return  # rate limiting isključen
        async with self.lock:
            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.max_tokens,
                self.tokens + elapsed * self.requests_per_second
            )
            self.last_refill = now
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
