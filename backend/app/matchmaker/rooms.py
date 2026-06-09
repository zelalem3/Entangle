from app.core.redis_config import redis_manager

async def verify_room_access(room_id: str, player_id: str) -> bool:
    """
    Authoritative security check. Assures a requesting client's identity token
    matches the locked metadata stored in the private Redis session hash.
    """
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        white = await redis.hget(room_key, "player_white")
        black = await redis.hget(room_key, "player_black")
        
        # Safe string decoding from raw binary formats
        white = white.decode('utf-8') if isinstance(white, bytes) else white
        black = black.decode('utf-8') if isinstance(black, bytes) else black
        
        return player_id in (white, black)

async def handle_room_disconnect(room_id: str, player_id: str):
    """
    Gracefully transitions active sessions into a 30-second recovery phase
    upon websocket termination, preventing immediate data loss.
    """
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        
        status = await redis.hget(room_key, "status")
        status = status.decode('utf-8') if isinstance(status, bytes) else status
        
        # Ensure we don't overwrite completed games (e.g., checkmate, draw)
        terminal_states = ["checkmate", "draw", "abandoned"]
        if status not in terminal_states:
            # Set the room state to flag the disconnected client
            await redis.hset(room_key, "status", f"disconnected:{player_id}")
            
            # Bound the memory lifecycle to exactly 30 seconds for self-healing eviction
            await redis.expire(room_key, 30)
            print(f"⚠️ Player {player_id} dropped from {room_id}. 30s reconnection window triggered.")

async def handle_room_reconnect(room_id: str, player_id: str):
    """
    Intercepts client reconnection handshakes, cancels ticking expiration
    clocks, and seamlessly restores session vitality states.
    """
    async with redis_manager.get_client() as redis:
        room_key = f"entangle:room:{room_id}"
        
        # Remove the volatile 30-second TTL countdown completely
        await redis.persist(room_key)
        
        # Restore long-term 2-hour persistence safety buffer
        await redis.expire(room_key, 7200)
        
        # Set the server state back to active
        await redis.hset(room_key, "status", "active")
        print(f"🔄 Player {player_id} reconnected to {room_id}. Match state stabilized.")