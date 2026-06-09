from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from contextlib import asynccontextmanager
from app.core.redis_config import redis_manager
from app.matchmaker.worker import matchmaking_worker_loop
from app.matchmaker.queue import redist_ticket_queue, remove_player_from_queue
from app.matchmaker.rooms import verify_room_access, handle_room_disconnect, handle_room_reconnect
import asyncio
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize global high-performance connection pool with correct method
    redis_manager.initialize_pool()
    print("⚡ Entangle Redis pool initialized successfully.")
    
    # Start the matchmaking worker loop safely in the background before yielding
    asyncio.create_task(matchmaking_worker_loop())  
    
    yield
    
    # Shutdown: Clean up connections safely with correct method
    await redis_manager.close_pool()
    print("🔌 Entangle Redis pool closed cleanly.")

app = FastAPI(title="Entangle Engine", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "online", "engine": "Entangle v1.0.0"}

# =====================================================================
# MODULE 1: MATCHMAKING LOBBY GATEWAY
# =====================================================================
@app.websocket("/ws/matchmaker")
async def matchmaking_endpoint(websocket: WebSocket, player_id: str, rating: int):
    """
    Handles connection ingestion, adds players to the sorted set queue,
    and listens on a private Redis Pub/Sub channel for match allocation notifications.
    """
    await websocket.accept()
    client_host = websocket.client.host
    print(f"📡 Player {player_id} ({rating}) connected to matchmaking lobby.")
    
    # 1. Ingest player into the Redis matchmaking queue
    await redist_ticket_queue(player_id, rating)
    
    try:
        # 2. Bind a dedicated Pub/Sub listener context manager
        async with redis_manager.get_client() as redis:
            pubsub = redis.pubsub()
            player_channel = f"channel:player:{player_id}"
            
            await pubsub.subscribe(player_channel)
            
            # 3. Match Verification Stream Loop
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message:
                    payload_data = json.loads(message["data"])
                    if payload_data.get("status") == "matched":
                        # Forward match room tokens down the socket wire to client front-end
                        await websocket.send_json(payload_data)
                        print(f"🚀 Dispatched match token to {player_id}. Transitioning client.")
                        break  
                
                # Active connection drop detection via empty frame receipt polling
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass 
                    
    except WebSocketDisconnect:
        print(f"❌ Player {player_id} disconnected from matchmaking lobby.")
    finally:
        # Deterministic cleanup: Ensure queue records are cleared upon disconnect or match success
        await remove_player_from_queue(player_id)


# =====================================================================
# MODULE 2: AUTHORITATIVE ACTIVE GAME SESSIONS
# =====================================================================
@app.websocket("/ws/game/{room_id}")
async def active_game_room_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    """
    Manages active, stateful game sessions. Performs strict security access controls,
    handles real-time messaging, and implements the 30-second graceful reconnection matrix.
    """
    # 1. Authoritative access validation check before accepting websocket upgrade
    access_granted = await verify_room_access(room_id, player_id)
    if not access_granted:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        print(f"🛑 Security Alert: Access denied to {player_id} attempting to access {room_id}")
        return

    await websocket.accept()
    print(f"🎮 Player {player_id} entered Active Game Room: {room_id}")
    
    # 2. Run the self-healing reconnection logic if a countdown was running
    await handle_room_reconnect(room_id, player_id)
    
    try:
        # 3. Core Game Loop State Stream
        while True:
            # Wait for structured client packets (e.g., player moves, chat, syncing coordinates)
            data = await websocket.receive_text()
            
            # TODO: Integrate game state mutations and Broadcasters here
            
            # Temporary echo wrapper for active network link validation
            await websocket.send_text(f"Authoritative Echo from {room_id}: {data}")
            
    except WebSocketDisconnect:
        print(f"⚠️ Connection broken for Player {player_id} in Room {room_id}")
        # 4. Fire off our self-healing disconnection matrix tracking rules
        await handle_room_disconnect(room_id, player_id)