
from app.core.redis_config import redis_manager
import asyncio




async def redist_ticket_queue(player_id: str, skill_rating: int):
    try:
        async with redis_manager.get_client() as redis:
            await redis.zadd("entangle:matchmaking_queue", {player_id: skill_rating})
            return True  
    except Exception as e:
        print(f"Error in Redis connection: {e}")
        return False
    
async def remove_player_from_queue(player_id: str):
    try:
        async with redis_manager.get_client() as redis:
            result = await redis.zrem("entangle:matchmaking_queue", player_id)
            return True
    except Exception as e:
        print(f"Error in Redis connection: {e}")
        return False