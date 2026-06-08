import redis.asyncio as aioredis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class RedisManager:
    def __init__(self):
        self.pool = None

    def initialize(self):
        # Create a connection pool that handles high concurrency
        self.pool = aioredis.ConnectionPool.from_url(
            REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True,
            max_connections=20
        )

    def get_client(self) -> aioredis.Redis:
        if not self.pool:
            self.initialize()
        return aioredis.Redis(connection_pool=self.pool)

    async def close(self):
        if self.pool:
            await self.pool.disconnect()

redis_manager = RedisManager()