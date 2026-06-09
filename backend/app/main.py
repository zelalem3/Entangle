from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from app.core.redis_config import redis_manager
from app.matchmaker.worker import matchmaking_worker_loop
from app.matchmaker.queue import redist_ticket_queue, remove_player_from_queue
import asyncio
import json  # Added missing json import

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize global high-performance connection pool
    redis_manager.initialize()
    print("⚡ Entangle Redis pool initialized successfully.")
    
    # Start the matchmaking worker loop in the background *before* the application yields
    asyncio.create_task(matchmaking_worker_loop())  
    
    yield
    
    # Shutdown: Clean up connections safely
    await redis_manager.close()
    print("🔌 Entangle Redis pool closed cleanly.")

app = FastAPI(title="Entangle Engine", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "online", "engine": "Entangle v1.0.0"}

@app.websocket("/ws/session/{room_id}")
async def game_session_endpoint(websocket: WebSocket, room_id: str, player_id: str, rating: int):
    await websocket.accept()
    client_host = websocket.client.host
    print(f"Client {client_host} ({player_id}) connected to lobby.")
    
    # 1. Add the player to the queue
    await redist_ticket_queue(player_id, rating)
    
    try:
        # 2. Open a dedicated Pub/Sub connection from our client manager
        async with redis_manager.get_client() as redis:
            pubsub = redis.pubsub()
            player_channel = f"channel:player:{player_id}"
            
            # Subscribe to the player's custom channel
            await pubsub.subscribe(player_channel)
            print(f"📡 Subscribed {player_id} to personal channel: {player_channel}")
            
            # 3. Match Detection Loop
            while True:
                # Read incoming messages from our Redis subscription channel
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message:
                    # Extract the payload string sent by our matchmaker background worker
                    payload_data = json.loads(message["data"])
                    
                    if payload_data.get("status") == "matched":
                        # Forward the room data straight down the WebSocket line to the browser client!
                        await websocket.send_json(payload_data)
                        print(f"🚀 Sent match room update down the wire to {player_id}.")
                        break  # Break out of the loop to close this temporary matchmaking socket cleanly!
                
                # Keep-alive heartbeat check: make sure the client is still physically there
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass # Timeout is expected since they aren't sending messages while searching
                    
    except WebSocketDisconnect:
        print(f"❌ Client {client_host} ({player_id}) disconnected during matchmaking.")
    finally:
        # Clean up memory: always purge them from the queue if they leave or match successfully
        await remove_player_from_queue(player_id)