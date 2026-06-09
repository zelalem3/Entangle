from app.core.redis_config import redis_manager
import asyncio

async def redist_ticket_queue(player_id: str, skill_rating: int) -> bool:
    """
    Ingests a matchmaking ticket into the high-performance Redis sorted set.
    Uses the player's skill rating as the sorting score.
    """
    try:
        async with redis_manager.get_client() as redis:
            # Atomic ZADD insertion into the distributed queue
            await redis.zadd("entangle:matchmaking_queue", {player_id: skill_rating})
            return True  
    except Exception as e:
        print(f"Error in Redis connection during queue ingestion: {e}")
        return False
    
async def remove_player_from_queue(player_id: str) -> bool:
    """
    Atomically revokes a player's matchmaking ticket from the sorted set.
    Prevents stale tickets from being processed by background worker cycles.
    """
    try:
        async with redis_manager.get_client() as redis:
            # Atomic ZREM operation to instantly revoke the queue index
            await redis.zrem("entangle:matchmaking_queue", player_id)
            return True
    except Exception as e:
        print(f"Error in Redis connection during queue revocation: {e}")
        return False