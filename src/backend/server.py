"""
Ludex — Play-to-Learn GameFi Backend
OneHack 3.0 | AI & GameFi Edition

FastAPI server handling game state, AI NPC interactions, lesson progression,
leaderboards, analytics, challenge generation, and social features.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Optional

import os
import re
import secrets

import anthropic
import httpx
import structlog
from cachetools import TTLCache
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# ──────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────

logger = structlog.get_logger()


class Settings(BaseSettings):
    app_name: str = "Ludex"
    debug: bool = False

    # Blockchain
    onechain_rpc_url: str = "https://rpc.onechain.network"
    game_contract_address: str = ""
    admin_private_key: str = ""

    # AI
    anthropic_api_key: str = ""

    # Database (SQLite for hackathon, swap to Postgres in prod)
    database_url: str = "sqlite+aiosqlite:///./ludex.db"

    # Redis (optional for hackathon)
    redis_url: str = "redis://localhost:6379/0"

    # JWT — secret is generated at startup if not provided via env / .env
    jwt_secret: str = os.environ.get("LUDEX_JWT_SECRET", secrets.token_urlsafe(64))
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 72

    # CORS — comma-separated allowed origins (default: localhost only)
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    class Config:
        env_file = ".env"
        env_prefix = "LUDEX_"


settings = Settings()


# ──────────────────────────────────────────────
#  Domain enums & constants
# ──────────────────────────────────────────────

class LessonCategory(IntEnum):
    BUDGETING = 0
    INVESTING = 1
    SAVING = 2
    CREDIT = 3
    CRYPTO = 4
    TAXES = 5


class QuestDifficulty(IntEnum):
    BEGINNER = 0
    EASY = 1
    MEDIUM = 2
    HARD = 3
    EXPERT = 4


CATEGORY_NAMES = {
    LessonCategory.BUDGETING: "Budgeting & Money Management",
    LessonCategory.INVESTING: "Investing & Markets",
    LessonCategory.SAVING: "Saving & Emergency Funds",
    LessonCategory.CREDIT: "Credit & Debt Management",
    LessonCategory.CRYPTO: "Crypto & DeFi",
    LessonCategory.TAXES: "Taxes & Financial Planning",
}

DIFFICULTY_XP_MULTIPLIER = {
    QuestDifficulty.BEGINNER: 1.0,
    QuestDifficulty.EASY: 1.25,
    QuestDifficulty.MEDIUM: 1.5,
    QuestDifficulty.HARD: 2.0,
    QuestDifficulty.EXPERT: 3.0,
}

NPC_PERSONAS = {
    "professor_luna": {
        "name": "Professor Luna",
        "role": "Financial Literacy Mentor",
        "personality": (
            "Warm, patient, and encouraging. Uses real-world analogies to "
            "explain concepts. Celebrates small wins. Never condescending."
        ),
        "specialty": "General financial literacy, budgeting, saving",
    },
    "trader_rex": {
        "name": "Trader Rex",
        "role": "Investment & Market Guide",
        "personality": (
            "Energetic and street-smart. Uses sports and gaming metaphors. "
            "Emphasizes risk management. Keeps it real about losses."
        ),
        "specialty": "Investing, portfolio theory, market analysis",
    },
    "crypto_sage": {
        "name": "Crypto Sage",
        "role": "DeFi & Blockchain Educator",
        "personality": (
            "Chill, futuristic thinker. Breaks down complex DeFi concepts "
            "into digestible bites. Warns about scams without being preachy."
        ),
        "specialty": "Cryptocurrency, DeFi, blockchain, web3",
    },
    "credit_fox": {
        "name": "Credit Fox",
        "role": "Credit & Debt Strategist",
        "personality": (
            "Witty and strategic. Treats credit like a game to be mastered. "
            "Gives actionable tips. Motivates without shaming."
        ),
        "specialty": "Credit scores, debt payoff strategies, loans",
    },
}

# ──────────────────────────────────────────────
#  Pydantic models
# ──────────────────────────────────────────────

class PlayerCreate(BaseModel):
    wallet_address: str
    username: str = Field(min_length=3, max_length=24)


class PlayerResponse(BaseModel):
    wallet_address: str
    username: str
    xp: int = 0
    level: int = 1
    total_quests_completed: int = 0
    daily_streak: int = 0
    longest_streak: int = 0
    badges: list[dict[str, Any]] = []
    team_id: str | None = None
    registered_at: str = ""


class QuestCreate(BaseModel):
    title: str
    description: str
    category: int = Field(ge=0, le=5)
    difficulty: int = Field(ge=0, le=4)
    xp_reward: int = Field(gt=0)
    token_reward: int = Field(ge=0)
    required_level: int = Field(ge=1, default=1)
    expires_at: str | None = None
    is_daily: bool = False
    is_team_quest: bool = False


class QuestResponse(BaseModel):
    id: str
    title: str
    description: str
    category: int
    category_name: str
    difficulty: int
    xp_reward: int
    token_reward: int
    required_level: int
    expires_at: str | None
    is_daily: bool
    is_team_quest: bool
    questions: list[dict[str, Any]] = []


class QuizAnswer(BaseModel):
    quest_id: str
    answers: list[int]  # indices of chosen answers


class NPCChatRequest(BaseModel):
    npc_id: str
    message: str
    context: dict[str, Any] = {}


class NPCChatResponse(BaseModel):
    npc_id: str
    npc_name: str
    message: str
    suggested_actions: list[str] = []
    xp_earned: int = 0
    lesson_hint: str | None = None


class LeaderboardResponse(BaseModel):
    season: int
    entries: list[dict[str, Any]]
    updated_at: str


class TeamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=32)


class TeamResponse(BaseModel):
    id: str
    name: str
    leader: str
    members: list[str]
    total_xp: int


class ChallengeGenerateRequest(BaseModel):
    category: int = Field(ge=0, le=5)
    difficulty: int = Field(ge=0, le=4)
    player_level: int = Field(ge=1)
    num_questions: int = Field(ge=1, le=10, default=5)


class StakeRequest(BaseModel):
    amount: int = Field(gt=0)
    duration_days: int = Field(ge=1, le=365)


class FriendRequest(BaseModel):
    friend_address: str


class AnalyticsResponse(BaseModel):
    total_players: int
    total_quests_completed: int
    total_tokens_distributed: int
    active_players_24h: int
    avg_level: float
    top_category: str
    retention_7d: float


# ──────────────────────────────────────────────
#  In-memory stores (swap for DB in production)
# ──────────────────────────────────────────────

players: dict[str, dict[str, Any]] = {}
quests: dict[str, dict[str, Any]] = {}
teams: dict[str, dict[str, Any]] = {}
leaderboard_cache = TTLCache(maxsize=1, ttl=60)
chat_histories: dict[str, list[dict[str, str]]] = {}  # player+npc -> messages
analytics_events: list[dict[str, Any]] = []


# ──────────────────────────────────────────────
#  AI client
# ──────────────────────────────────────────────

ai_client: anthropic.AsyncAnthropic | None = None

security_scheme = HTTPBearer(auto_error=False)

# Wallet address regex — 0x followed by 64 hex chars (Aptos / Move style)
WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")


def _validate_wallet(wallet: str) -> str:
    """Validate and normalise a wallet address."""
    wallet = wallet.strip().lower()
    if not WALLET_RE.match(wallet):
        raise HTTPException(status_code=422, detail="Invalid wallet address format. Expected 0x-prefixed hex string.")
    return wallet


def _create_jwt(wallet: str) -> str:
    """Issue a JWT for the given wallet address."""
    payload = {
        "sub": wallet,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jose_jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def _get_current_wallet(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str:
    """Dependency: extract and verify the wallet address from a Bearer JWT."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header. Use Bearer <token>.")
    try:
        payload = jose_jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        wallet: str | None = payload.get("sub")
        if wallet is None:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        return wallet
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return uuid.uuid4().hex[:16]


def _xp_for_level(level: int) -> int:
    """Mirror the on-chain XP formula."""
    return 100 * level * (100 + 15 * level) // 100


def _process_level_ups(player: dict[str, Any]) -> list[int]:
    """Process level-ups for a player and return list of new levels reached."""
    new_levels = []
    while player["level"] < 100:
        needed = _xp_for_level(player["level"])
        if player["xp"] < needed:
            break
        player["xp"] -= needed
        player["level"] += 1
        new_levels.append(player["level"])
    return new_levels


def _update_streak(player: dict[str, Any]) -> None:
    now = time.time()
    elapsed = now - player.get("last_activity_ts", 0)
    if elapsed < 172800:  # 48h
        if elapsed >= 72000:  # 20h
            player["daily_streak"] += 1
            if player["daily_streak"] > player["longest_streak"]:
                player["longest_streak"] = player["daily_streak"]
    else:
        player["daily_streak"] = 1
    player["last_activity_ts"] = now


def _get_player_or_404(wallet: str) -> dict[str, Any]:
    if wallet not in players:
        raise HTTPException(status_code=404, detail="Player not found")
    return players[wallet]


def _build_leaderboard() -> list[dict[str, Any]]:
    sorted_players = sorted(
        players.values(),
        key=lambda p: (p["level"], p["xp"]),
        reverse=True,
    )
    return [
        {
            "rank": i + 1,
            "wallet_address": p["wallet_address"],
            "username": p["username"],
            "xp": p["xp"],
            "level": p["level"],
            "badges_count": len(p.get("badges", [])),
        }
        for i, p in enumerate(sorted_players[:100])
    ]


# ──────────────────────────────────────────────
#  Lesson & curriculum data
# ──────────────────────────────────────────────

CURRICULUM = {
    LessonCategory.BUDGETING: [
        {"level": 1, "title": "The 50/30/20 Rule", "key_concepts": ["needs vs wants", "income allocation", "tracking expenses"]},
        {"level": 2, "title": "Building Your First Budget", "key_concepts": ["zero-based budgeting", "expense categories", "budget apps"]},
        {"level": 5, "title": "Advanced Cash Flow", "key_concepts": ["irregular income", "sinking funds", "annual planning"]},
        {"level": 10, "title": "Behavioral Budgeting", "key_concepts": ["spending triggers", "automation", "accountability systems"]},
    ],
    LessonCategory.INVESTING: [
        {"level": 1, "title": "What Is Investing?", "key_concepts": ["compound interest", "risk vs return", "time horizon"]},
        {"level": 3, "title": "Stock Market Basics", "key_concepts": ["stocks", "bonds", "ETFs", "diversification"]},
        {"level": 7, "title": "Portfolio Construction", "key_concepts": ["asset allocation", "rebalancing", "dollar-cost averaging"]},
        {"level": 15, "title": "Options & Derivatives", "key_concepts": ["calls", "puts", "hedging", "leverage"]},
    ],
    LessonCategory.SAVING: [
        {"level": 1, "title": "Pay Yourself First", "key_concepts": ["emergency fund", "3-6 months rule", "high-yield savings"]},
        {"level": 3, "title": "Saving Goals Framework", "key_concepts": ["SMART goals", "short vs long term", "automation"]},
        {"level": 8, "title": "Optimizing Your Savings", "key_concepts": ["CD ladders", "money market accounts", "I-bonds"]},
    ],
    LessonCategory.CREDIT: [
        {"level": 1, "title": "Understanding Credit Scores", "key_concepts": ["FICO score", "credit bureaus", "score factors"]},
        {"level": 3, "title": "Credit Cards 101", "key_concepts": ["APR", "grace period", "utilization ratio", "rewards"]},
        {"level": 6, "title": "Debt Payoff Strategies", "key_concepts": ["avalanche method", "snowball method", "consolidation"]},
        {"level": 12, "title": "Credit Mastery", "key_concepts": ["authorized users", "credit mix", "mortgage readiness"]},
    ],
    LessonCategory.CRYPTO: [
        {"level": 1, "title": "Blockchain Basics", "key_concepts": ["decentralization", "consensus", "wallets", "keys"]},
        {"level": 3, "title": "Understanding DeFi", "key_concepts": ["DEX", "lending protocols", "yield farming", "impermanent loss"]},
        {"level": 8, "title": "Smart Contract Safety", "key_concepts": ["audit checks", "rug pull signals", "DYOR framework"]},
        {"level": 15, "title": "Advanced DeFi Strategies", "key_concepts": ["liquidity provision", "leveraged yield", "governance"]},
    ],
    LessonCategory.TAXES: [
        {"level": 1, "title": "Tax Basics", "key_concepts": ["brackets", "deductions vs credits", "W-2 vs 1099"]},
        {"level": 5, "title": "Tax-Advantaged Accounts", "key_concepts": ["401k", "IRA", "HSA", "529 plans"]},
        {"level": 10, "title": "Tax Optimization", "key_concepts": ["tax-loss harvesting", "Roth conversion", "capital gains"]},
    ],
}


# ──────────────────────────────────────────────
#  Application lifecycle
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ai_client
    if settings.anthropic_api_key:
        ai_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    logger.info("ludex_started", players=len(players))
    yield
    logger.info("ludex_shutdown")


app = FastAPI(
    title="Ludex — Play-to-Learn GameFi",
    description="Backend API for the Ludex financial literacy game on OneChain",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════
#  Health
# ══════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ludex",
        "timestamp": _now_iso(),
        "players": len(players),
        "quests": len(quests),
    }


# ══════════════════════════════════════════════
#  Player registration & profiles
# ══════════════════════════════════════════════

@app.post("/players", status_code=201)
async def register_player(body: PlayerCreate):
    wallet = _validate_wallet(body.wallet_address)

    if wallet in players:
        raise HTTPException(status_code=409, detail="Player already registered")

    now = _now_iso()
    player = {
        "wallet_address": wallet,
        "username": body.username,
        "xp": 0,
        "level": 1,
        "total_quests_completed": 0,
        "daily_streak": 0,
        "longest_streak": 0,
        "last_activity_ts": time.time(),
        "registered_at": now,
        "badges": [],
        "completed_quests": [],
        "active_quests": [],
        "friends": [],
        "team_id": None,
        "staking": None,
        "lesson_progress": {cat.value: 0 for cat in LessonCategory},
        "chat_xp_today": 0,
        "chat_xp_last_reset": now,
    }
    players[wallet] = player

    _track_event("player_registered", {"wallet": wallet})
    logger.info("player_registered", wallet=wallet, username=body.username)

    # Issue a JWT so the player can authenticate subsequent requests.
    token = _create_jwt(wallet)

    return {
        "player": PlayerResponse(**{k: v for k, v in player.items() if k in PlayerResponse.model_fields}),
        "token": token,
    }


@app.post("/auth/login")
async def login(body: PlayerCreate):
    """Authenticate an existing player and return a fresh JWT."""
    wallet = _validate_wallet(body.wallet_address)
    if wallet not in players:
        raise HTTPException(status_code=404, detail="Player not found. Register first.")
    stored = players[wallet]
    if stored["username"] != body.username:
        raise HTTPException(status_code=401, detail="Username does not match wallet.")
    return {"token": _create_jwt(wallet)}


@app.get("/players/{wallet}", response_model=PlayerResponse)
async def get_player(wallet: str, _caller: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    return PlayerResponse(**{k: v for k, v in player.items() if k in PlayerResponse.model_fields})


@app.get("/players/{wallet}/progress")
async def get_player_progress(wallet: str, _caller: str = Depends(_get_current_wallet)):
    """Full progress report: lesson advancement, XP breakdown, next milestones."""
    player = _get_player_or_404(wallet)

    xp_to_next = _xp_for_level(player["level"])
    progress_pct = round(player["xp"] / max(xp_to_next, 1) * 100, 1)

    # Find next available lessons per category.
    available_lessons = {}
    for cat in LessonCategory:
        cat_lessons = CURRICULUM.get(cat, [])
        for lesson in cat_lessons:
            if lesson["level"] <= player["level"]:
                if player["lesson_progress"].get(str(cat.value), 0) < cat_lessons.index(lesson) + 1:
                    available_lessons[CATEGORY_NAMES[cat]] = lesson["title"]
                    break

    return {
        "wallet": wallet,
        "level": player["level"],
        "xp": player["xp"],
        "xp_to_next_level": xp_to_next,
        "progress_percent": progress_pct,
        "daily_streak": player["daily_streak"],
        "longest_streak": player["longest_streak"],
        "total_quests_completed": player["total_quests_completed"],
        "lesson_progress": player["lesson_progress"],
        "available_lessons": available_lessons,
        "badges_count": len(player["badges"]),
        "staking_active": player["staking"] is not None,
    }


# ══════════════════════════════════════════════
#  Quest / Challenge system
# ══════════════════════════════════════════════

@app.post("/quests", response_model=QuestResponse, status_code=201)
async def create_quest(body: QuestCreate):
    quest_id = _gen_id()
    quest = {
        "id": quest_id,
        **body.model_dump(),
        "category_name": CATEGORY_NAMES.get(LessonCategory(body.category), "Unknown"),
        "questions": [],
        "created_at": _now_iso(),
    }
    quests[quest_id] = quest

    logger.info("quest_created", quest_id=quest_id, title=body.title)
    return QuestResponse(**quest)


@app.get("/quests", response_model=list[QuestResponse])
async def list_quests(
    category: int | None = None,
    difficulty: int | None = None,
    level: int | None = None,
):
    result = list(quests.values())
    if category is not None:
        result = [q for q in result if q["category"] == category]
    if difficulty is not None:
        result = [q for q in result if q["difficulty"] == difficulty]
    if level is not None:
        result = [q for q in result if q["required_level"] <= level]
    return [QuestResponse(**q) for q in result]


@app.get("/quests/{quest_id}", response_model=QuestResponse)
async def get_quest(quest_id: str):
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    return QuestResponse(**quests[quest_id])


@app.post("/quests/{quest_id}/submit")
async def submit_quest_answers(quest_id: str, body: QuizAnswer, wallet: str = Depends(_get_current_wallet)):
    """Validate quiz answers, award XP and tokens."""
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")

    player = _get_player_or_404(wallet)
    quest = quests[quest_id]

    if quest["required_level"] > player["level"]:
        raise HTTPException(status_code=403, detail="Level too low for this quest")

    if quest_id in player["completed_quests"] and not quest["is_daily"]:
        raise HTTPException(status_code=409, detail="Quest already completed")

    # Score the answers.
    questions = quest.get("questions", [])
    if not questions:
        # If no questions attached, treat as auto-pass (lesson completion).
        correct = 1
        total = 1
    else:
        correct = sum(
            1
            for i, q in enumerate(questions)
            if i < len(body.answers) and body.answers[i] == q.get("correct_index", -1)
        )
        total = len(questions)

    score_pct = correct / max(total, 1) * 100
    passed = score_pct >= 60  # 60% to pass

    if not passed:
        return {
            "passed": False,
            "score": round(score_pct, 1),
            "correct": correct,
            "total": total,
            "message": "Keep learning! Review the material and try again.",
        }

    # Calculate rewards.
    base_xp = quest["xp_reward"]
    multiplier = DIFFICULTY_XP_MULTIPLIER.get(QuestDifficulty(quest["difficulty"]), 1.0)
    xp_earned = int(base_xp * multiplier)

    # Streak bonus (5% per streak day, max 50%).
    streak_bonus = min(player["daily_streak"] * 5, 50) / 100
    xp_earned = int(xp_earned * (1 + streak_bonus))

    # Perfect score bonus.
    if score_pct == 100:
        xp_earned = int(xp_earned * 1.25)

    # Staking multiplier.
    token_reward = quest["token_reward"]
    if player["staking"]:
        token_reward = int(token_reward * player["staking"]["bonus_multiplier"] / 100)

    # Apply rewards.
    player["xp"] += xp_earned
    new_levels = _process_level_ups(player)
    _update_streak(player)
    player["total_quests_completed"] += 1
    player["completed_quests"].append(quest_id)

    # Update lesson progress.
    cat_key = str(quest["category"])
    player["lesson_progress"][cat_key] = player["lesson_progress"].get(cat_key, 0) + 1

    _track_event("quest_completed", {
        "wallet": wallet,
        "quest_id": quest_id,
        "score": score_pct,
        "xp_earned": xp_earned,
    })

    # Auto-badge checks.
    badges_earned = _check_badge_eligibility(player)

    return {
        "passed": True,
        "score": round(score_pct, 1),
        "correct": correct,
        "total": total,
        "xp_earned": xp_earned,
        "token_reward": token_reward,
        "new_levels": new_levels,
        "badges_earned": badges_earned,
        "daily_streak": player["daily_streak"],
        "message": _get_completion_message(score_pct, new_levels),
    }


def _get_completion_message(score: float, new_levels: list[int]) -> str:
    if new_levels:
        return f"LEVEL UP! You reached level {new_levels[-1]}! Score: {score:.0f}%"
    if score == 100:
        return "Perfect score! You're a financial wizard!"
    if score >= 80:
        return "Excellent work! You really understand this topic!"
    return "Good job! You passed! Keep building your knowledge."


def _check_badge_eligibility(player: dict[str, Any]) -> list[dict[str, Any]]:
    """Check and award automatic badges based on milestones."""
    earned = []
    existing_ids = {b["id"] for b in player["badges"]}

    badge_rules = [
        {"id": "first_quest", "name": "First Steps", "desc": "Completed your first quest", "rarity": 0, "check": lambda p: p["total_quests_completed"] >= 1},
        {"id": "quest_10", "name": "Knowledge Seeker", "desc": "Completed 10 quests", "rarity": 1, "check": lambda p: p["total_quests_completed"] >= 10},
        {"id": "quest_50", "name": "Scholar", "desc": "Completed 50 quests", "rarity": 2, "check": lambda p: p["total_quests_completed"] >= 50},
        {"id": "quest_100", "name": "Financial Sage", "desc": "Completed 100 quests", "rarity": 3, "check": lambda p: p["total_quests_completed"] >= 100},
        {"id": "streak_7", "name": "Week Warrior", "desc": "7-day learning streak", "rarity": 1, "check": lambda p: p["daily_streak"] >= 7},
        {"id": "streak_30", "name": "Consistency King", "desc": "30-day learning streak", "rarity": 3, "check": lambda p: p["daily_streak"] >= 30},
        {"id": "level_10", "name": "Rising Star", "desc": "Reached level 10", "rarity": 1, "check": lambda p: p["level"] >= 10},
        {"id": "level_25", "name": "Finance Pro", "desc": "Reached level 25", "rarity": 2, "check": lambda p: p["level"] >= 25},
        {"id": "level_50", "name": "Money Master", "desc": "Reached level 50", "rarity": 3, "check": lambda p: p["level"] >= 50},
        {"id": "all_categories", "name": "Renaissance Investor", "desc": "Completed quests in all categories", "rarity": 3, "check": lambda p: all(v > 0 for v in p["lesson_progress"].values())},
        {"id": "staker", "name": "Diamond Hands", "desc": "Staked LDX tokens", "rarity": 1, "check": lambda p: p["staking"] is not None},
        {"id": "social_5", "name": "Networker", "desc": "Added 5 friends", "rarity": 1, "check": lambda p: len(p["friends"]) >= 5},
    ]

    for rule in badge_rules:
        if rule["id"] not in existing_ids and rule["check"](player):
            badge = {
                "id": rule["id"],
                "name": rule["name"],
                "description": rule["desc"],
                "rarity": rule["rarity"],
                "earned_at": _now_iso(),
            }
            player["badges"].append(badge)
            earned.append(badge)

    return earned


# ══════════════════════════════════════════════
#  Challenge generation engine (AI-powered)
# ══════════════════════════════════════════════

@app.post("/challenges/generate")
async def generate_challenge(body: ChallengeGenerateRequest):
    """Use Claude to generate contextual financial literacy challenges."""
    category_name = CATEGORY_NAMES.get(LessonCategory(body.category), "Finance")
    difficulty_label = QuestDifficulty(body.difficulty).name.title()

    # Find relevant curriculum context.
    cat_lessons = CURRICULUM.get(LessonCategory(body.category), [])
    relevant_lessons = [l for l in cat_lessons if l["level"] <= body.player_level]
    concepts = []
    for lesson in relevant_lessons:
        concepts.extend(lesson["key_concepts"])

    prompt = f"""Generate exactly {body.num_questions} multiple-choice quiz questions about {category_name}.

Difficulty: {difficulty_label}
Player level: {body.player_level} (scale 1-100)
Key concepts to test: {', '.join(concepts) if concepts else 'general knowledge'}

Rules:
- Each question should teach something, not just test memorization.
- Include a brief explanation for the correct answer.
- Make wrong answers plausible but clearly distinguishable from correct ones.
- Adjust complexity to match the difficulty level.
- Use real-world scenarios when possible.
- For crypto questions, include safety/risk awareness.

Return valid JSON array:
[
  {{
    "question": "...",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_index": 0,
    "explanation": "...",
    "concept": "..."
  }}
]

Return ONLY the JSON array, no other text."""

    if ai_client is None:
        # Fallback: return template questions when no API key.
        return _fallback_questions(body.category, body.difficulty, body.num_questions)

    try:
        response = await ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()

        # Parse JSON from response.
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        questions = json.loads(content)

        # Create a quest with these questions.
        quest_id = _gen_id()
        xp_reward = int(50 * DIFFICULTY_XP_MULTIPLIER[QuestDifficulty(body.difficulty)])
        token_reward = int(10_000_000 * DIFFICULTY_XP_MULTIPLIER[QuestDifficulty(body.difficulty)])

        quest = {
            "id": quest_id,
            "title": f"{category_name} Challenge",
            "description": f"AI-generated {difficulty_label.lower()} challenge",
            "category": body.category,
            "category_name": category_name,
            "difficulty": body.difficulty,
            "xp_reward": xp_reward,
            "token_reward": token_reward,
            "required_level": body.player_level,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "is_daily": False,
            "is_team_quest": False,
            "questions": questions,
            "created_at": _now_iso(),
        }
        quests[quest_id] = quest

        return {
            "quest_id": quest_id,
            "questions": [
                {
                    "question": q["question"],
                    "options": q["options"],
                    "concept": q.get("concept", ""),
                }
                for q in questions
            ],
            "xp_reward": xp_reward,
            "token_reward": token_reward,
        }

    except Exception as e:
        logger.error("challenge_generation_failed", error=str(e))
        return _fallback_questions(body.category, body.difficulty, body.num_questions)


def _fallback_questions(category: int, difficulty: int, num: int) -> dict[str, Any]:
    """Template questions when AI is unavailable."""
    templates = {
        0: [  # Budgeting
            {"question": "What does the 50/30/20 rule suggest?", "options": ["A) 50% needs, 30% wants, 20% savings", "B) 50% savings, 30% needs, 20% wants", "C) 50% wants, 30% savings, 20% needs", "D) 50% investments, 30% needs, 20% fun"], "correct_index": 0, "explanation": "The 50/30/20 rule allocates 50% of after-tax income to needs, 30% to wants, and 20% to savings and debt repayment.", "concept": "budgeting basics"},
            {"question": "What is zero-based budgeting?", "options": ["A) Having zero savings", "B) Every dollar is assigned a purpose", "C) Spending nothing for a month", "D) Starting fresh each year"], "correct_index": 1, "explanation": "Zero-based budgeting means allocating every dollar of income to a specific category so income minus expenses equals zero.", "concept": "budgeting methods"},
        ],
        1: [  # Investing
            {"question": "What is compound interest?", "options": ["A) Interest on the principal only", "B) Interest on both principal and accumulated interest", "C) A fixed interest rate", "D) Interest paid monthly"], "correct_index": 1, "explanation": "Compound interest is earned on both the initial principal and previously accumulated interest, creating exponential growth over time.", "concept": "compound interest"},
            {"question": "What does diversification help reduce?", "options": ["A) Returns", "B) Risk", "C) Taxes", "D) Fees"], "correct_index": 1, "explanation": "Diversification spreads investments across different assets to reduce the impact of any single investment's poor performance.", "concept": "diversification"},
        ],
        2: [  # Saving
            {"question": "How many months of expenses should an emergency fund cover?", "options": ["A) 1 month", "B) 3-6 months", "C) 12 months", "D) It doesn't matter"], "correct_index": 1, "explanation": "Financial experts recommend saving 3-6 months of living expenses in an easily accessible emergency fund to cover unexpected costs.", "concept": "emergency fund"},
            {"question": "What is a high-yield savings account?", "options": ["A) A checking account with rewards", "B) A savings account that offers above-average interest rates", "C) A stock brokerage account", "D) A certificate of deposit"], "correct_index": 1, "explanation": "High-yield savings accounts pay significantly more interest than traditional savings accounts while keeping your money accessible.", "concept": "high-yield savings"},
        ],
        3: [  # Credit
            {"question": "What is a credit utilization ratio?", "options": ["A) Your total debt amount", "B) The percentage of available credit you are using", "C) The number of credit cards you own", "D) Your monthly payment amount"], "correct_index": 1, "explanation": "Credit utilization is the percentage of your total credit limit that you're using. Keeping it below 30% is generally recommended for a healthy credit score.", "concept": "credit utilization"},
            {"question": "Which debt payoff method targets the highest interest rate first?", "options": ["A) Snowball method", "B) Avalanche method", "C) Consolidation", "D) Minimum payment"], "correct_index": 1, "explanation": "The avalanche method prioritises debts with the highest interest rates first, saving you the most money in interest over time.", "concept": "debt payoff strategies"},
        ],
        4: [  # Crypto
            {"question": "What is a private key in crypto?", "options": ["A) Your username", "B) A password to your exchange", "C) A cryptographic key that controls your assets", "D) Your wallet address"], "correct_index": 2, "explanation": "A private key is a cryptographic secret that proves ownership of blockchain assets. Never share it — whoever has it controls your funds.", "concept": "wallet security"},
        ],
        5: [  # Taxes
            {"question": "What is the difference between a tax deduction and a tax credit?", "options": ["A) They are the same thing", "B) A deduction reduces taxable income; a credit reduces tax owed dollar-for-dollar", "C) A credit reduces income; a deduction reduces tax owed", "D) Neither affects how much you pay"], "correct_index": 1, "explanation": "A tax deduction lowers your taxable income, while a tax credit directly reduces the amount of tax you owe, making credits generally more valuable.", "concept": "deductions vs credits"},
            {"question": "What is a 401(k)?", "options": ["A) A type of bank account", "B) An employer-sponsored retirement savings plan with tax advantages", "C) A government bond", "D) A type of insurance policy"], "correct_index": 1, "explanation": "A 401(k) is a tax-advantaged retirement savings plan offered by employers, often with matching contributions that are essentially free money.", "concept": "tax-advantaged accounts"},
        ],
    }

    cat_questions = templates.get(category, templates[0])
    selected = (cat_questions * ((num // len(cat_questions)) + 1))[:num]

    quest_id = _gen_id()
    quest = {
        "id": quest_id,
        "title": f"{CATEGORY_NAMES.get(LessonCategory(category), 'Finance')} Quiz",
        "description": "Test your knowledge",
        "category": category,
        "category_name": CATEGORY_NAMES.get(LessonCategory(category), "Finance"),
        "difficulty": difficulty,
        "xp_reward": 50,
        "token_reward": 10_000_000,
        "required_level": 1,
        "expires_at": None,
        "is_daily": False,
        "is_team_quest": False,
        "questions": selected,
        "created_at": _now_iso(),
    }
    quests[quest_id] = quest

    return {
        "quest_id": quest_id,
        "questions": [{"question": q["question"], "options": q["options"], "concept": q.get("concept", "")} for q in selected],
        "xp_reward": 50,
        "token_reward": 10_000_000,
    }


# ══════════════════════════════════════════════
#  AI NPC interactions
# ══════════════════════════════════════════════

@app.post("/npc/chat", response_model=NPCChatResponse)
async def npc_chat(body: NPCChatRequest, wallet: str = Depends(_get_current_wallet)):
    """Chat with an AI NPC mentor. Earns small XP for educational interactions."""
    player = _get_player_or_404(wallet)

    if body.npc_id not in NPC_PERSONAS:
        raise HTTPException(status_code=404, detail="NPC not found")

    npc = NPC_PERSONAS[body.npc_id]
    chat_key = f"{wallet}:{body.npc_id}"

    # Retrieve or initialize chat history.
    if chat_key not in chat_histories:
        chat_histories[chat_key] = []

    history = chat_histories[chat_key]

    # Build system prompt.
    system_prompt = f"""You are {npc['name']}, a {npc['role']} in Ludex, a play-to-learn financial literacy game.

Personality: {npc['personality']}
Specialty: {npc['specialty']}

Player context:
- Username: {player['username']}
- Level: {player['level']}
- XP: {player['xp']}
- Streak: {player['daily_streak']} days
- Quests completed: {player['total_quests_completed']}

Rules:
1. Stay in character at all times.
2. Make every response educational — weave in financial concepts naturally.
3. Keep responses concise (2-4 paragraphs max).
4. If the player asks something off-topic, gently steer back to financial literacy.
5. Suggest relevant quests or lessons when appropriate.
6. Celebrate their progress and streak.
7. Use their username when addressing them.
8. End with a thought-provoking question or actionable tip when possible.
9. If they ask about a concept above their level, give a simplified preview and encourage them to level up.
10. NEVER give specific financial advice for real investments. Always remind them to do their own research."""

    # Add user message to history.
    history.append({"role": "user", "content": body.message})

    # Keep last 20 messages for context.
    recent_history = history[-20:]

    if ai_client is None:
        # Fallback response.
        reply = (
            f"Hey {player['username']}! Great question about that. "
            f"As your {npc['role']}, I'd love to dive deeper into this topic. "
            f"Make sure to check out the quests in my specialty area: {npc['specialty']}. "
            f"Keep that {player['daily_streak']}-day streak going!"
        )
        xp_earned = 5
    else:
        try:
            response = await ai_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system=system_prompt,
                messages=recent_history,
            )
            reply = response.content[0].text
            xp_earned = _calculate_chat_xp(body.message, reply)
        except Exception as e:
            logger.error("npc_chat_failed", error=str(e))
            reply = (
                f"Hmm, my thoughts got a bit scrambled there, {player['username']}. "
                f"Let me think about that and get back to you. "
                f"In the meantime, why not try a quest in {npc['specialty']}?"
            )
            xp_earned = 2

    # Cap daily chat XP at 100.
    today = datetime.now(timezone.utc).date().isoformat()
    if player.get("chat_xp_last_reset", "")[:10] != today:
        player["chat_xp_today"] = 0
        player["chat_xp_last_reset"] = _now_iso()

    if player["chat_xp_today"] + xp_earned > 100:
        xp_earned = max(0, 100 - player["chat_xp_today"])

    player["chat_xp_today"] += xp_earned
    player["xp"] += xp_earned
    _process_level_ups(player)

    # Save assistant reply.
    history.append({"role": "assistant", "content": reply})

    # Suggest relevant actions.
    suggested = _suggest_actions(player, npc)

    return NPCChatResponse(
        npc_id=body.npc_id,
        npc_name=npc["name"],
        message=reply,
        suggested_actions=suggested,
        xp_earned=xp_earned,
        lesson_hint=_get_next_lesson_hint(player, body.npc_id),
    )


def _calculate_chat_xp(user_msg: str, reply: str) -> int:
    """Award more XP for substantive educational conversations."""
    xp = 3  # base
    if len(user_msg) > 50:
        xp += 2  # asked a detailed question
    if "?" in user_msg:
        xp += 2  # asked a question
    if any(kw in user_msg.lower() for kw in ["how", "why", "explain", "what is", "difference"]):
        xp += 3  # educational intent
    return min(xp, 10)


def _suggest_actions(player: dict, npc: dict) -> list[str]:
    actions = []
    if player["total_quests_completed"] == 0:
        actions.append("Try your first quest to earn XP and LDX tokens!")
    if player["daily_streak"] == 0:
        actions.append("Complete a quest today to start a learning streak!")
    if len(player["friends"]) == 0:
        actions.append("Add friends to compete on the leaderboard!")
    if player["staking"] is None and player["level"] >= 5:
        actions.append("Stake LDX to unlock premium courses and earn bonus rewards!")
    actions.append(f"Explore {npc['specialty']} quests")
    return actions[:4]


def _get_next_lesson_hint(player: dict, npc_id: str) -> str | None:
    npc = NPC_PERSONAS.get(npc_id)
    if not npc:
        return None

    # Map NPC to primary category.
    npc_category_map = {
        "professor_luna": LessonCategory.BUDGETING,
        "trader_rex": LessonCategory.INVESTING,
        "crypto_sage": LessonCategory.CRYPTO,
        "credit_fox": LessonCategory.CREDIT,
    }

    cat = npc_category_map.get(npc_id)
    if cat is None:
        return None

    lessons = CURRICULUM.get(cat, [])
    progress = player["lesson_progress"].get(str(cat.value), 0)

    if progress < len(lessons):
        next_lesson = lessons[progress]
        if next_lesson["level"] <= player["level"]:
            return f"Next up: '{next_lesson['title']}' — covers {', '.join(next_lesson['key_concepts'][:3])}"
        return f"Reach level {next_lesson['level']} to unlock '{next_lesson['title']}'"

    return "You've completed all available lessons in this track!"


@app.get("/npc/list")
async def list_npcs():
    return [
        {"id": npc_id, "name": npc["name"], "role": npc["role"], "specialty": npc["specialty"]}
        for npc_id, npc in NPC_PERSONAS.items()
    ]


# ══════════════════════════════════════════════
#  Leaderboard
# ══════════════════════════════════════════════

@app.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard():
    entries = _build_leaderboard()
    return LeaderboardResponse(season=1, entries=entries, updated_at=_now_iso())


@app.get("/leaderboard/teams")
async def get_team_leaderboard():
    sorted_teams = sorted(teams.values(), key=lambda t: t["total_xp"], reverse=True)
    return {
        "teams": [
            {
                "rank": i + 1,
                "id": t["id"],
                "name": t["name"],
                "total_xp": t["total_xp"],
                "member_count": len(t["members"]),
            }
            for i, t in enumerate(sorted_teams[:50])
        ],
        "updated_at": _now_iso(),
    }


# ══════════════════════════════════════════════
#  Staking
# ══════════════════════════════════════════════

@app.post("/staking/stake")
async def stake_tokens(body: StakeRequest, wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)

    if player["staking"] is not None:
        raise HTTPException(status_code=409, detail="Already staking. Unstake first.")

    weeks = body.duration_days // 7
    multiplier = min(120 + weeks * 10, 200)

    now = datetime.now(timezone.utc)
    player["staking"] = {
        "amount": body.amount,
        "staked_at": now.isoformat(),
        "unlock_at": (now + timedelta(days=body.duration_days)).isoformat(),
        "bonus_multiplier": multiplier,
    }

    _check_badge_eligibility(player)
    _track_event("staked", {"wallet": wallet, "amount": body.amount, "days": body.duration_days})

    return {
        "status": "staked",
        "amount": body.amount,
        "unlock_at": player["staking"]["unlock_at"],
        "bonus_multiplier": f"{multiplier / 100:.2f}x",
        "message": f"Staked {body.amount} LDX for {body.duration_days} days. Earning {multiplier/100:.2f}x rewards!",
    }


@app.post("/staking/unstake")
async def unstake_tokens(wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)

    if player["staking"] is None:
        raise HTTPException(status_code=400, detail="Not currently staking")

    unlock_at = datetime.fromisoformat(player["staking"]["unlock_at"])
    if datetime.now(timezone.utc) < unlock_at:
        remaining = (unlock_at - datetime.now(timezone.utc)).days
        raise HTTPException(
            status_code=403,
            detail=f"Tokens locked for {remaining} more day(s). Unlock at {player['staking']['unlock_at']}",
        )

    amount = player["staking"]["amount"]
    reward = int(amount * 0.05)
    player["staking"] = None

    return {
        "status": "unstaked",
        "amount_returned": amount,
        "staking_reward": reward,
        "total": amount + reward,
        "message": f"Returned {amount} LDX + {reward} LDX staking reward!",
    }


# ══════════════════════════════════════════════
#  Social: Friends & Teams
# ══════════════════════════════════════════════

@app.post("/social/friends")
async def add_friend(body: FriendRequest, wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    _get_player_or_404(body.friend_address)  # ensure friend exists

    if body.friend_address in player["friends"]:
        raise HTTPException(status_code=409, detail="Already friends")

    if body.friend_address == wallet:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a friend")

    player["friends"].append(body.friend_address)

    # Reciprocal friendship.
    friend = players[body.friend_address]
    if wallet not in friend["friends"]:
        friend["friends"].append(wallet)

    _check_badge_eligibility(player)

    return {"status": "friend_added", "friends_count": len(player["friends"])}


@app.get("/social/friends")
async def list_friends(wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    friends_data = []
    for f_addr in player["friends"]:
        if f_addr in players:
            f = players[f_addr]
            friends_data.append({
                "wallet_address": f_addr,
                "username": f["username"],
                "level": f["level"],
                "daily_streak": f["daily_streak"],
            })
    return {"friends": friends_data}


@app.post("/teams", response_model=TeamResponse, status_code=201)
async def create_team(body: TeamCreate, wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    if player["team_id"] is not None:
        raise HTTPException(status_code=409, detail="Already in a team. Leave first.")

    team_id = _gen_id()
    team = {
        "id": team_id,
        "name": body.name,
        "leader": wallet,
        "members": [wallet],
        "total_xp": player["xp"],
    }
    teams[team_id] = team
    player["team_id"] = team_id

    return TeamResponse(**team)


@app.post("/teams/{team_id}/join")
async def join_team(team_id: str, wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    if player["team_id"] is not None:
        raise HTTPException(status_code=409, detail="Already in a team")

    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")

    team = teams[team_id]
    if len(team["members"]) >= 5:
        raise HTTPException(status_code=409, detail="Team is full (max 5)")

    team["members"].append(wallet)
    team["total_xp"] += player["xp"]
    player["team_id"] = team_id

    return {"status": "joined", "team": team}


@app.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(team_id: str):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamResponse(**teams[team_id])


# ══════════════════════════════════════════════
#  Player analytics
# ══════════════════════════════════════════════

def _track_event(event_type: str, data: dict[str, Any]) -> None:
    analytics_events.append({
        "type": event_type,
        "data": data,
        "timestamp": _now_iso(),
    })


@app.get("/analytics/overview", response_model=AnalyticsResponse)
async def get_analytics():
    now = time.time()
    active_24h = sum(1 for p in players.values() if now - p.get("last_activity_ts", 0) < 86400)
    avg_level = sum(p["level"] for p in players.values()) / max(len(players), 1)

    # Most popular category.
    cat_counts: dict[str, int] = {}
    for p in players.values():
        for cat_key, count in p["lesson_progress"].items():
            cat_counts[cat_key] = cat_counts.get(cat_key, 0) + count
    top_cat_key = max(cat_counts, key=cat_counts.get, default="0") if cat_counts else "0"
    top_cat = CATEGORY_NAMES.get(LessonCategory(int(top_cat_key)), "Budgeting")

    # 7-day retention (players active in last 7 days / total).
    active_7d = sum(1 for p in players.values() if now - p.get("last_activity_ts", 0) < 604800)
    retention = active_7d / max(len(players), 1)

    total_quests = sum(p["total_quests_completed"] for p in players.values())
    total_tokens = total_quests * 10_000_000  # approximate

    return AnalyticsResponse(
        total_players=len(players),
        total_quests_completed=total_quests,
        total_tokens_distributed=total_tokens,
        active_players_24h=active_24h,
        avg_level=round(avg_level, 1),
        top_category=top_cat,
        retention_7d=round(retention * 100, 1),
    )


@app.get("/analytics/player/{wallet}")
async def get_player_analytics(wallet: str):
    player = _get_player_or_404(wallet)

    # Category breakdown.
    category_breakdown = {
        CATEGORY_NAMES.get(LessonCategory(int(k)), f"Category {k}"): v
        for k, v in player["lesson_progress"].items()
    }

    # XP sources estimate.
    quest_xp = player["total_quests_completed"] * 50  # avg
    chat_xp = player["chat_xp_today"]

    return {
        "wallet": wallet,
        "username": player["username"],
        "level": player["level"],
        "total_xp_earned": player["xp"] + sum(_xp_for_level(l) for l in range(1, player["level"])),
        "quests_completed": player["total_quests_completed"],
        "category_breakdown": category_breakdown,
        "badges_earned": len(player["badges"]),
        "current_streak": player["daily_streak"],
        "longest_streak": player["longest_streak"],
        "friends_count": len(player["friends"]),
        "staking_active": player["staking"] is not None,
        "xp_sources": {"quests": quest_xp, "chat": chat_xp},
        "member_since": player["registered_at"],
    }


# ══════════════════════════════════════════════
#  Financial lesson progression
# ══════════════════════════════════════════════

@app.get("/lessons/curriculum")
async def get_curriculum(wallet: str | None = None):
    """Return the full curriculum tree with unlock status."""
    result = {}
    player = players.get(wallet) if wallet else None

    for cat in LessonCategory:
        lessons = CURRICULUM.get(cat, [])
        result[CATEGORY_NAMES[cat]] = []
        progress = 0
        if player:
            progress = player["lesson_progress"].get(str(cat.value), 0)

        for i, lesson in enumerate(lessons):
            status = "locked"
            if player:
                if i < progress:
                    status = "completed"
                elif i == progress and lesson["level"] <= player["level"]:
                    status = "available"
                elif lesson["level"] <= player["level"]:
                    status = "available"

            result[CATEGORY_NAMES[cat]].append({
                "index": i,
                "title": lesson["title"],
                "required_level": lesson["level"],
                "key_concepts": lesson["key_concepts"],
                "status": status,
            })

    return {"curriculum": result}


@app.post("/lessons/{category}/start")
async def start_lesson(category: int, wallet: str = Depends(_get_current_wallet)):
    """Begin the next lesson in a category. Returns AI-generated lesson content."""
    player = _get_player_or_404(wallet)
    cat = LessonCategory(category)
    lessons = CURRICULUM.get(cat, [])
    progress = player["lesson_progress"].get(str(category), 0)

    if progress >= len(lessons):
        return {"message": "You've completed all lessons in this category!", "completed": True}

    lesson = lessons[progress]
    if lesson["level"] > player["level"]:
        raise HTTPException(
            status_code=403,
            detail=f"Reach level {lesson['level']} to unlock this lesson. You're level {player['level']}.",
        )

    # Generate lesson content with AI.
    if ai_client:
        try:
            prompt = f"""Create a concise, engaging financial literacy lesson for a game called Ludex.

Topic: {lesson['title']}
Category: {CATEGORY_NAMES[cat]}
Key concepts: {', '.join(lesson['key_concepts'])}
Player level: {player['level']}

Format:
1. **Hook** (1 sentence — grab attention with a surprising fact or relatable scenario)
2. **Core Concept** (2-3 paragraphs — explain clearly with analogies)
3. **Real-World Example** (1 paragraph — practical application)
4. **Pro Tip** (1 sentence — actionable takeaway)
5. **Did You Know?** (1 fun fact related to the topic)

Keep it conversational, use second person (you/your), and make it feel like a game tutorial, not a textbook. Total length: ~300 words."""

            response = await ai_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
        except Exception:
            content = _fallback_lesson_content(lesson)
    else:
        content = _fallback_lesson_content(lesson)

    return {
        "lesson": {
            "title": lesson["title"],
            "category": CATEGORY_NAMES[cat],
            "key_concepts": lesson["key_concepts"],
            "content": content,
            "progress_index": progress,
            "total_lessons": len(lessons),
        },
        "completed": False,
    }


def _fallback_lesson_content(lesson: dict) -> str:
    return (
        f"# {lesson['title']}\n\n"
        f"In this lesson, you'll learn about: {', '.join(lesson['key_concepts'])}.\n\n"
        f"Understanding these concepts is a key step in your financial literacy journey. "
        f"Complete the quiz after this lesson to earn XP and LDX tokens!\n\n"
        f"**Pro Tip:** The best time to start managing your money is now. "
        f"Even small steps compound into big results over time."
    )


# ══════════════════════════════════════════════
#  WebSocket: live notifications
# ══════════════════════════════════════════════

connected_clients: dict[str, WebSocket] = {}


@app.websocket("/ws/{wallet}")
async def websocket_endpoint(websocket: WebSocket, wallet: str):
    await websocket.accept()
    connected_clients[wallet] = websocket
    logger.info("ws_connected", wallet=wallet)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": _now_iso()})

    except WebSocketDisconnect:
        connected_clients.pop(wallet, None)
        logger.info("ws_disconnected", wallet=wallet)


async def notify_player(wallet: str, event_type: str, data: dict[str, Any]) -> None:
    ws = connected_clients.get(wallet)
    if ws:
        try:
            await ws.send_json({"type": event_type, "data": data, "timestamp": _now_iso()})
        except Exception:
            connected_clients.pop(wallet, None)


# ══════════════════════════════════════════════
#  Entrypoint
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
