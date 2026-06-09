import uuid
import json
import asyncio
from app.core.redis_config import redis_manager


async def matchmaking_worker_loop():
    while True:  # The infinite loop lives on the absolute outside
        try:
            async with redis_manager.get_client() as redis:
                # 1. Fetch top players
                players = await redis.zrange("entangle:matchmaking_queue", 0, 1, withscores=True)
                
                # 2. Check if we have a match
                if len(players) >= 2 and abs(players[0][1] - players[1][1]) <= 100:
                    player1, skill1 = players[0]
                    player2, skill2 = players[1]
                    
                    async with redis.pipeline(transaction=True) as pipe:
                        pipe.zrem("entangle:matchmaking_queue", player1)
                        pipe.zrem("entangle:matchmaking_queue", player2)
                        results = await pipe.execute()
                        if all(results):
                                # 1. Generate a completely unique cryptographic room ID for their new match
                                match_room_id = f"room_{uuid.uuid4().hex[:12]}"
                                print(f"🎯 Matched {player1} with {player2} -> Assigned Room: {match_room_id}")
                                
                                # 2. Package the match metadata payload
                                match_payload = {
                                    "status": "matched",
                                    "room_id": match_room_id
                                }

                                initial_state ={
                                    "player_white":player1,
                                    "player_black":player2,
                                    "turn": "white",
                                    "board_state":"startpos",
                                    "status": "active"
                                }
                                await redis.hset(f"match:{match_room_id}", mapping=initial_state)
                                await redis.expire(f"match:{match_room_id}", 3600)  # Match data expires in 1 hour  
                                match_payload={
                                    "status": "matched",
                                    "room_id": match_room_id,
                                  
                                }
                                
                                # 3. Broadcast the payload to each individual player's channel
                                await redis.publish(f"channel:player:{player1}", json.dumps(match_payload))
                                await redis.publish(f"channel:player:{player2}", json.dumps(match_payload))
                else:
                    # No match found or not enough players. Rest before checking again.
                    await asyncio.sleep(1)
                    
        except Exception as e:
            # If Redis goes offline, we log the error here...
            print(f"!!! Matchmaker connection drop caught: {e}")
            # ...and sleep briefly to avoid hammering an offline database with retries
            await asyncio.sleep(2)
            # The loop hits the bottom, cycles back up to "while True", 
            # and tries to grab a fresh client connection pool to heal itself!