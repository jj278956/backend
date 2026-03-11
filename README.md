# Neptune Shopping Backend

FastAPI backend with Google OAuth authentication, user/group management, and shared shopping carts.

## Features

- **Google OAuth 2.0** authentication (login/signup via Google)
- **User management** — view profile, update, deactivate
- **Group management** — create groups, add/remove members, role-based access (owner/admin/member)
- **Shopping carts** — CRUD for carts and items with check-off support
- **Cart sharing** — share carts with groups (read-only or edit permissions)
- **PostgreSQL** database with async SQLAlchemy and Alembic migrations

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A Google Cloud project with OAuth 2.0 credentials ([instructions](https://console.cloud.google.com/apis/credentials))

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your Google OAuth credentials
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

The API is available at **http://localhost:8000**. Interactive docs at **http://localhost:8000/docs**.

### 3. Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth 2.0 Client ID (Web application)
3. Set **Authorized redirect URIs** to: `http://localhost:8000/api/auth/google/callback`
4. Copy the Client ID and Secret into your `.env` file

## API Overview

| Method | Endpoint | Description |
|--------|--------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/auth/google/login` | Get Google OAuth URL |
| `GET` | `/api/auth/google/callback` | OAuth callback (returns JWT) |
| `GET` | `/api/users/me` | Current user profile |
| `PATCH` | `/api/users/me` | Update profile |
| `DELETE` | `/api/users/me` | Deactivate account |
| `GET` | `/api/users/` | List users |
| `GET` | `/api/users/{id}` | Get user by ID |
| `POST` | `/api/groups/` | Create group |
| `GET` | `/api/groups/` | List my groups |
| `GET` | `/api/groups/{id}` | Group detail with members |
| `PATCH` | `/api/groups/{id}` | Update group |
| `DELETE` | `/api/groups/{id}` | Delete group |
| `POST` | `/api/groups/{id}/members` | Add member |
| `DELETE` | `/api/groups/{id}/members/{user_id}` | Remove member |
| `POST` | `/api/carts/` | Create cart |
| `GET` | `/api/carts/` | List my carts (owned + shared) |
| `GET` | `/api/carts/{id}` | Cart detail with items |
| `PATCH` | `/api/carts/{id}` | Update cart |
| `DELETE` | `/api/carts/{id}` | Delete cart |
| `POST` | `/api/carts/{id}/share` | Share cart with group |
| `DELETE` | `/api/carts/{id}/share/{group_id}` | Unshare cart |
| `POST` | `/api/carts/{id}/items` | Add item to cart |
| `PATCH` | `/api/carts/{id}/items/{item_id}` | Update item |
| `DELETE` | `/api/carts/{id}/items/{item_id}` | Remove item |

## Authentication

All endpoints (except `/health` and `/api/auth/*`) require a Bearer token:

```
Authorization: Bearer <jwt_token>
```

Obtain a token by completing the Google OAuth flow.

## Development

### Run migrations (inside the api container)

```bash
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
```

### Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Set DATABASE_URL to point to a local Postgres
uvicorn app.main:app --reload
```

## Project Structure

```
app/
├── api/
│   ├── router.py          # Top-level API router
│   └── routes/
│       ├── auth.py         # Google OAuth endpoints
│       ├── users.py        # User management
│       ├── groups.py       # Group management
│       └── carts.py        # Shopping cart & items
├── core/
│   ├── config.py           # Settings (env vars)
│   ├── deps.py             # FastAPI dependencies (auth)
│   └── security.py         # JWT creation/validation
├── db/
│   ├── base.py             # SQLAlchemy declarative base
│   └── session.py          # Async engine & session
├── models/
│   ├── user.py             # User model
│   ├── group.py            # Group & GroupMembership models
│   └── cart.py             # ShoppingCart, CartItem, CartGroupShare
├── schemas/
│   ├── auth.py             # Auth response schemas
│   ├── user.py             # User schemas
│   ├── group.py            # Group schemas
│   └── cart.py             # Cart & item schemas
└── main.py                 # FastAPI app entrypoint
```
