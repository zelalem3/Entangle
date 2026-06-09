from app.core.redis_config import redis_manager
import json

async def verify_room_access(room_id: str, player_id: str) -> bool:
    """Ensures a connecting player is actually assigned to the requested room."""
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        white = await redis.hget(room_key, "player_white")
        black = await redis.hget(room_key, "player_black")
        
        # Decode bytes if necessary
        white = white.decode('utf-8') if isinstance(white, bytes) else white
        black = black.decode('utf-8') if isinstance(black, bytes) else black
        
        return player_id in (white, black)

async def handle_room_disconnect(room_id: str, player_id: str):
    """Sets player to disconnected and initializes the 30-second countdown."""
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        
        # Verify the game is still active before executing cleanup steps
        status = await redis.hget(room_key, "status")
        status = status.decode('utf-8') if isinstance(status, bytes) else status
        
        if status == "active":
            # Set the room status to paused/disconnected
            await redis.hset(room_key, "status", f"disconnected:{player_id}")
            # Give the player exactly 30 seconds to reconnect before session wipes out
            await redis.expire(room_key, 30)
            print(f"⚠️ {player_id} dropped from {room_id}. Reconnection window triggered.")

async def handle_room_reconnect(room_id: str, player_id: str):
    """Cancels the expiration countdown and restores game state to active."""
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        
        # Remove the tight expiration limit and restore standard 2-hour buffer
        await redis.persist(room_key)
        await redis.expire(room_key, 7200)
        
        await redis.hset(room_key, "status", "active")
        print(f"🔄 {player_id} successfully reconnected to {room_id}. Match resumed.")