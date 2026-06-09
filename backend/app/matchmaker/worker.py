import uuid
import json
import asyncio
from app.core.redis_config import redis_manager

async def matchmaking_worker_loop():
    """
    Independent background worker tracking the matchmaking queue.
    Atomically extracts closely-ranked players, initializes authoritative states,
    and dispatches secure session routing tokens.
    """
    print("🚀 Entangle matchmaking worker loop started running...")
    
    while True:
        try:
            async with redis_manager.get_client() as redis:
                # 1. Fetch the top two waiting player tokens
                players = await redis.zrange("entangle:matchmaking_queue", 0, 1, withscores=True)
                
                # 2. Evaluate pairing viability
                if len(players) >= 2:
                    # Explicitly decode binary data from Redis into strings
                    player1 = players[0][0].decode('utf-8') if isinstance(players[0][0], bytes) else players[0][0]
                    skill1 = players[0][1]
                    
                    player2 = players[1][0].decode('utf-8') if isinstance(players[1][0], bytes) else players[1][0]
                    skill2 = players[1][1]
                    
                    # Confirm players fall within the designated skill threshold
                    if abs(skill1 - skill2) <= 100:
                        
                        # 3. Open an atomic transaction transaction pipeline
                        async with redis.pipeline(transaction=True) as pipe:
                            pipe.zrem("entangle:matchmaking_queue", player1)
                            pipe.zrem("entangle:matchmaking_queue", player2)
                            results = await pipe.execute()
                            
                            # Only proceed if both players were successfully popped by THIS worker thread
                            if all(results):
                                match_room_id = f"room_{uuid.uuid4().hex[:12]}"
                                room_key = f"entangle:room:{match_room_id}"
                                print(f"🎯 Matched {player1} ({skill1}) with {player2} ({skill2}) -> Room: {match_room_id}")
                                
                                # 4. Seed the Authoritative State Hash
                                initial_state = {
                                    "player_white": player1,
                                    "player_black": player2,
                                    "turn": "white",
                                    "board_state": "startpos",
                                    "status": "active"
                                }
                                await redis.hset(room_key, mapping=initial_state)
                                await redis.expire(room_key, 7200) # Balanced 2-hour lifecycle target
                                
                                # 5. Package routing packet
                                match_payload = {
                                    "status": "matched",
                                    "room_id": match_room_id
                                }
                                
                                # 6. Broadcast matching frames to individual pub/sub channels
                                await redis.publish(f"channel:player:{player1}", json.dumps(match_payload))
                                await redis.publish(f"channel:player:{player2}", json.dumps(match_payload))
                        continue # Re-evaluate instantly without sleeping if a match was processed
                        
                # No matches found or queue empty; rest to avoid thrashing CPU resources
                await asyncio.sleep(1)
                    
        except Exception as e:
            print(f"!!! Matchmaker connection drop caught: {e}")
            await asyncio.sleep(2) # Self-healing cooling step before reconnection attempt