# Ograničavanje broja HTTP zahteva u sekundi (--rate-limit), da fuzzer ne
# preoptereti ciljni API.

import asyncio
import time


# Globalni token-bucket limiter — ograničava UKUPAN broj zahteva u sekundi,
# bez obzira na concurrency. Bucket kreće pun (requests_per_second tokena),
# svaki zahtev troši jedan token, a tokeni se dopunjuju proporcionalno
# proteklom vremenu, najviše do punog bucket-a.
class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.requests_per_second = requests_per_second
        self.tokens = requests_per_second
        self.max_tokens = requests_per_second
        self.last_refill = time.perf_counter()
        self.lock = asyncio.Lock()

    # Čeka dok ne bude dostupan token za jedan zahtev; lock obezbeđuje da
    # paralelni zadaci ne troše isti token istovremeno
    async def acquire(self):
        if self.requests_per_second <= 0:
            return  # rate limiting isključen
        async with self.lock:
            # Dopunjavanje tokena za vreme proteklo od poslednjeg poziva
            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.max_tokens,
                self.tokens + elapsed * self.requests_per_second
            )
            self.last_refill = now
            # Nema celog tokena — čeka se tačno onoliko koliko treba da se dopuni
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
