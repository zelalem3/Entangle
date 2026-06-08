from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from app.core.redis_config import redis_manager
from app.matchmaker.worker import matchmaking_worker_loop
from app.matchmaker.queue import redist_ticket_queue, remove_player_from_queue
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize global high-performance connection pool
    redis_manager.initialize()
    print("⚡ Entangle Redis pool initialized successfully.")
    yield
    asyncio.create_task(matchmaking_worker_loop())  # Start the matchmaking worker loop in the background
    



    # Shutdown: Clean up connections safely
    await redis_manager.close()
    print("🔌 Entangle Redis pool closed cleanly.")

app = FastAPI(title="Entangle Engine", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "online", "engine": "Entangle v1.0.0"}

@app.websocket("/ws/session/{room_id}")
async def game_session_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    client_host = websocket.client.host
    print(f"Client, {client_host} connected to Room {room_id}")
    
    try:
        # Core real-time stream loop
        while True:
            # Wait for data sent from the player client
            data = await websocket.receive_text()
            
            # TODO: Add authoritative server validation and Redis sync here
            
            # Echo back for immediate sync visualization
            await websocket.send_text(f"Room {room_id} state updated with: {data}")
            
    except WebSocketDisconnect:
        print(f"❌ Client {client_host} disconnected from Room {room_id}")
        # TODO: Trigger heartbeat tracker matrix to allow seamless reconnection