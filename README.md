# ⚡ Entangle

**High-Performance Distributed Matchmaking & Real-Time Game Synchronization Engine**

Entangle is a backend engine designed for low-latency, concurrent multiplayer environments. It decouples **player matchmaking** from **live session state** using asynchronous event loops and an in-memory Redis layer, delivering consistent session management and fault-tolerant network presence.

> **Status:** 🚧 Active Development — v1.0.0 Foundation

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **Ticket-Based Matchmaking** | Concurrent matchmaking queues powered by Redis Sorted Sets, ranked by skill rating, with latency-aware matching planned. |
| ⚡ **Real-Time State Synchronization** | Low-latency WebSocket connections with authoritative server-side validation and real-time state broadcasting. |
| 🔄 **Heartbeat & Reconnection** | A 30-second graceful reconnection window allows disconnected players to rejoin without immediately losing their sessions. |
| 📊 **Observability Ready** | Designed for monitoring active rooms, connection health, matchmaking queue depth, and latency. |
| 🧵 **Asynchronous Processing** | Built on FastAPI and Asyncio to handle concurrent connections efficiently. |
| 🐳 **Containerized Infrastructure** | Docker Compose simplifies local development and Redis infrastructure management. |

---

## 🏗️ Architecture Overview

Entangle separates matchmaking operations from active game sessions, using Redis as the centralized state store and event communication layer.

```text
                 ┌──────────────────────────┐
                 │      Game Clients        │
                 │                          │
                 │   Player 1   Player 2    │
                 └────────────┬─────────────┘
                              │
                         WebSockets
                              │
                 ┌────────────▼─────────────┐
                 │       FastAPI            │
                 │       Asyncio            │
                 │                          │
                 │  /ws/matchmaker          │
                 │  /ws/game/{room_id}      │
                 └────────────┬─────────────┘
                              │
                       Async Redis
                              │
                 ┌────────────▼─────────────┐
                 │         Redis 7          │
                 │                          │
                 │  • Sorted Sets           │
                 │  • Pub/Sub               │
                 │  • Hashes (Room State)   │
                 │  • Key Expiration (TTL)  │
                 └──────────────────────────┘
```

### Core Workflow

1. **Player Connection** — A player connects to `/ws/matchmaker` with a `player_id` and skill `rating`.
2. **Ticket Creation** — The matchmaking ticket is inserted into a Redis Sorted Set (`entangle:matchmaking_queue`).
3. **Matchmaking** — A background worker continuously processes the queue and pairs players within a skill-rating difference of ±100.
4. **Match Notification** — Matched players receive a unique `room_id` through their private Redis Pub/Sub channels.
5. **Session Transition** — Both clients connect to `/ws/game/{room_id}` to enter their active game session.
6. **Disconnection Recovery** — If a player disconnects, a 30-second recovery window begins. Reconnecting within this period restores the session.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, FastAPI |
| **Asynchronous Runtime** | Asyncio |
| **Real-Time Communication** | WebSockets |
| **State Management** | Redis 7 |
| **Event Communication** | Redis Pub/Sub |
| **Data Structures** | Redis Sorted Sets, Hashes |
| **Validation** | Pydantic |
| **Infrastructure** | Docker, Docker Compose |

### Dependencies

Located in `backend/requirements.txt`:

```txt
fastapi==0.111.0
uvicorn[standard]==0.30.1
redis==5.0.4
websockets==12.0
pydantic==2.7.2
```

---

## 📁 Project Structure

```text
Entangle/
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── redis_config.py       # Async Redis connection pool manager
│   │   │
│   │   ├── matchmaker/
│   │   │   ├── queue.py              # Ticket ingestion and removal
│   │   │   ├── rooms.py              # Room management and reconnection logic
│   │   │   └── worker.py             # Background matchmaking loop
│   │   │
│   │   └── main.py                   # FastAPI application and WebSocket endpoints
│   │
│   └── requirements.txt
│
├── docker-compose.yml                # Redis infrastructure
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

Follow these steps to run Entangle locally.

### Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Docker
- Docker Compose
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/zelalem3/Entangle.git

cd Entangle
```

### 2. Start Redis

Start the Redis service using Docker Compose:

```bash
docker compose up -d
```

This starts Redis 7 with AOF persistence enabled and exposes it on port `6379`.

### 3. Set Up the Python Environment

Navigate to the backend directory:

```bash
cd backend
```

Create and activate a virtual environment:

```bash
python -m venv env
```

**Linux / macOS:**

```bash
source env/bin/activate
```

**Windows:**

```powershell
env\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 4. Run the Engine

Start the FastAPI application:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server starts the FastAPI application, initializes the Redis connection pool, and launches the matchmaking worker.

### 5. Verify the Application

Open the following URL:

```text
http://localhost:8000/
```

You should receive a response similar to:

```json
{
  "status": "online",
  "engine": "Entangle v1.0.0"
}
```

---

## 🔌 API & WebSocket Endpoints

### 1. Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Returns the engine's operational status. |

**Example response:**

```json
{
  "status": "online",
  "engine": "Entangle v1.0.0"
}
```

### 2. Matchmaking Lobby

**Endpoint:**

```text
WS /ws/matchmaker?player_id=<id>&rating=<int>
```

**Responsibilities:**

- Adds the connected player to the skill-based matchmaking queue.
- Stores matchmaking tickets in a Redis Sorted Set.
- Listens for match notifications through a private Redis Pub/Sub channel.
- Matches players based on their skill-rating difference.
- Removes matchmaking tickets after disconnection or successful matching.

**Match notification:**

```json
{
  "status": "matched",
  "room_id": "room_xxxxxxxxxxxx"
}
```

### 3. Active Game Room

**Endpoint:**

```text
WS /ws/game/{room_id}?player_id=<id>
```

**Responsibilities:**

- Validates player access against the corresponding Redis room hash.
- Supports reconnection within a 30-second recovery window.
- Maintains room session information.
- Currently echoes received messages; authoritative game-state mutation and broadcasting are planned.

---

## 🧠 How Matchmaking Works

Entangle uses Redis Sorted Sets to maintain an ordered matchmaking queue based on player skill ratings.

### 1. Enqueue

When a player connects, their matchmaking ticket is added to the Redis Sorted Set:

```redis
ZADD entangle:matchmaking_queue <rating> <player_id>
```

The player's rating determines their position in the sorted queue.

### 2. Background Worker

A background matchmaking worker continuously monitors the queue and searches for compatible players.

### 3. Skill-Based Pairing

Two players are considered compatible when their skill-rating difference is within the configured threshold:

```python
abs(rating1 - rating2) <= 100
```

### 4. Atomic Ticket Removal

Once a valid pair is identified, both matchmaking tickets are removed through a Redis transaction to help maintain queue consistency.

### 5. Room Creation

A unique game room is created and initialized with the initial session state:

```json
{
  "player_white": "...",
  "player_black": "...",
  "turn": "white",
  "board_state": "startpos",
  "status": "active"
}
```

### 6. Match Notification

Both players receive their assigned room ID through their respective private Redis Pub/Sub channels.

### 7. Room Persistence

Room data is stored using Redis hashes under the following key pattern:

```text
entangle:room:{room_id}
```

Each room has a default **2-hour TTL**, which can be extended when activity occurs.

---

## 🔄 Reconnection Matrix

Entangle provides a temporary recovery mechanism to prevent immediate session loss when a player disconnects.

| Event | Behavior |
|-------|----------|
| Player disconnects | Room status changes to `disconnected:{player_id}` and a 30-second recovery window begins. |
| Player reconnects within the window | The session is restored to `active`, and the room TTL is reapplied. |
| Recovery window expires | The disconnected session is no longer recoverable through the configured window. |
| Room expires | Redis automatically evicts the room after its TTL expires. |

This approach helps balance session continuity with bounded in-memory storage.

---

## 🗺️ Roadmap

Entangle is actively evolving. The following features are planned for future releases:

- [ ] Full authoritative game-state mutation and broadcasting.
- [ ] Latency-aware matchmaking using network latency measurements.
- [ ] Heartbeat and player-presence tracking.
- [ ] Advanced reconnection and session recovery mechanisms.
- [ ] Observability dashboard for active rooms, queue depth, and latency metrics.
- [ ] Horizontal scaling with multiple matchmaking workers.
- [ ] Improved fault tolerance and distributed coordination.
- [ ] Client SDK and example game integration.
- [ ] Automated testing and performance benchmarking.

---

## 👨‍💻 Author

**Zelalem Getnet**

Full-Stack Software Engineer · Backend-Focused · Computer Science Graduate

- **GitHub:** [@zelalem3](https://github.com/zelalem3)
- **LinkedIn:** [Zelalem Getnet](https://linkedin.com/in/zelalem-getnet-533326246)
- **Location:** Addis Ababa, Ethiopia

---

## 📄 License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for details.

---

<div align="center">

### ⚡ Entangle

**Built for the real-time multiplayer edge.**

*Decouple matchmaking. Synchronize sessions. Scale connections.*

</div>
