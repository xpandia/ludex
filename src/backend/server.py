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
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Optional

import os
import re
import secrets

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
    staking: dict[str, Any] | None = None


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
#  SQLite Database Layer
# ──────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ludex.db")

def _get_db() -> sqlite3.Connection:
    """Get a new SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db() -> None:
    """Create all tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            wallet_address TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            total_quests_completed INTEGER NOT NULL DEFAULT 0,
            daily_streak INTEGER NOT NULL DEFAULT 0,
            longest_streak INTEGER NOT NULL DEFAULT 0,
            last_activity_ts REAL NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL,
            team_id TEXT,
            staking_amount INTEGER,
            staking_staked_at TEXT,
            staking_unlock_at TEXT,
            staking_bonus_multiplier INTEGER,
            lesson_progress TEXT NOT NULL DEFAULT '{}',
            chat_xp_today INTEGER NOT NULL DEFAULT 0,
            chat_xp_last_reset TEXT NOT NULL DEFAULT '',
            friends TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS quests (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category INTEGER NOT NULL,
            category_name TEXT NOT NULL,
            difficulty INTEGER NOT NULL,
            xp_reward INTEGER NOT NULL,
            token_reward INTEGER NOT NULL,
            required_level INTEGER NOT NULL DEFAULT 1,
            expires_at TEXT,
            is_daily INTEGER NOT NULL DEFAULT 0,
            is_team_quest INTEGER NOT NULL DEFAULT 0,
            questions TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quest_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address TEXT NOT NULL,
            quest_id TEXT NOT NULL,
            score REAL NOT NULL,
            xp_earned INTEGER NOT NULL,
            token_reward INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (wallet_address) REFERENCES players(wallet_address),
            FOREIGN KEY (quest_id) REFERENCES quests(id)
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address TEXT NOT NULL,
            npc_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (wallet_address) REFERENCES players(wallet_address)
        );

        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            leader TEXT NOT NULL,
            total_xp INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (leader) REFERENCES players(wallet_address)
        );

        CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            PRIMARY KEY (team_id, wallet_address),
            FOREIGN KEY (team_id) REFERENCES teams(id),
            FOREIGN KEY (wallet_address) REFERENCES players(wallet_address)
        );

        CREATE TABLE IF NOT EXISTS staking (
            wallet_address TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            staked_at TEXT NOT NULL,
            unlock_at TEXT NOT NULL,
            bonus_multiplier INTEGER NOT NULL,
            FOREIGN KEY (wallet_address) REFERENCES players(wallet_address)
        );

        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address TEXT NOT NULL,
            badge_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            rarity INTEGER NOT NULL DEFAULT 0,
            earned_at TEXT NOT NULL,
            FOREIGN KEY (wallet_address) REFERENCES players(wallet_address),
            UNIQUE(wallet_address, badge_id)
        );

        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            data TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
#  DB helper functions
# ──────────────────────────────────────────────

def _db_get_player(wallet: str) -> dict[str, Any] | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM players WHERE wallet_address = ?", (wallet,)).fetchone()
    conn.close()
    if row is None:
        return None
    p = dict(row)
    p["lesson_progress"] = json.loads(p["lesson_progress"])
    p["friends"] = json.loads(p["friends"])
    # Reconstruct staking dict
    if p["staking_amount"] is not None:
        p["staking"] = {
            "amount": p["staking_amount"],
            "staked_at": p["staking_staked_at"],
            "unlock_at": p["staking_unlock_at"],
            "bonus_multiplier": p["staking_bonus_multiplier"],
        }
    else:
        p["staking"] = None
    # Get badges
    conn2 = _get_db()
    badge_rows = conn2.execute("SELECT badge_id, name, description, rarity, earned_at FROM badges WHERE wallet_address = ?", (wallet,)).fetchall()
    conn2.close()
    p["badges"] = [{"id": b["badge_id"], "name": b["name"], "description": b["description"], "rarity": b["rarity"], "earned_at": b["earned_at"]} for b in badge_rows]
    # Get completed quests
    conn3 = _get_db()
    comp_rows = conn3.execute("SELECT quest_id FROM quest_completions WHERE wallet_address = ?", (wallet,)).fetchall()
    conn3.close()
    p["completed_quests"] = [r["quest_id"] for r in comp_rows]
    return p


def _db_create_player(wallet: str, username: str) -> dict[str, Any]:
    now = _now_iso()
    lesson_progress = {str(cat.value): 0 for cat in LessonCategory}
    conn = _get_db()
    conn.execute(
        """INSERT INTO players (wallet_address, username, xp, level, total_quests_completed,
            daily_streak, longest_streak, last_activity_ts, registered_at, lesson_progress,
            chat_xp_today, chat_xp_last_reset, friends)
            VALUES (?, ?, 0, 1, 0, 0, 0, ?, ?, ?, 0, ?, '[]')""",
        (wallet, username, time.time(), now, json.dumps(lesson_progress), now),
    )
    conn.commit()
    conn.close()
    return _db_get_player(wallet)


def _db_update_player(player: dict[str, Any]) -> None:
    conn = _get_db()
    staking = player.get("staking")
    conn.execute(
        """UPDATE players SET username=?, xp=?, level=?, total_quests_completed=?,
            daily_streak=?, longest_streak=?, last_activity_ts=?,
            team_id=?, staking_amount=?, staking_staked_at=?, staking_unlock_at=?,
            staking_bonus_multiplier=?, lesson_progress=?, chat_xp_today=?,
            chat_xp_last_reset=?, friends=?
            WHERE wallet_address=?""",
        (
            player["username"], player["xp"], player["level"],
            player["total_quests_completed"], player["daily_streak"],
            player["longest_streak"], player["last_activity_ts"],
            player.get("team_id"),
            staking["amount"] if staking else None,
            staking["staked_at"] if staking else None,
            staking["unlock_at"] if staking else None,
            staking["bonus_multiplier"] if staking else None,
            json.dumps(player["lesson_progress"]),
            player.get("chat_xp_today", 0),
            player.get("chat_xp_last_reset", ""),
            json.dumps(player.get("friends", [])),
            player["wallet_address"],
        ),
    )
    conn.commit()
    conn.close()


def _db_get_quest(quest_id: str) -> dict[str, Any] | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    q = dict(row)
    q["questions"] = json.loads(q["questions"])
    q["is_daily"] = bool(q["is_daily"])
    q["is_team_quest"] = bool(q["is_team_quest"])
    return q


def _db_create_quest(quest: dict[str, Any]) -> None:
    conn = _get_db()
    conn.execute(
        """INSERT INTO quests (id, title, description, category, category_name, difficulty,
            xp_reward, token_reward, required_level, expires_at, is_daily, is_team_quest,
            questions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            quest["id"], quest["title"], quest["description"], quest["category"],
            quest["category_name"], quest["difficulty"], quest["xp_reward"],
            quest["token_reward"], quest["required_level"], quest.get("expires_at"),
            int(quest.get("is_daily", False)), int(quest.get("is_team_quest", False)),
            json.dumps(quest.get("questions", [])), quest["created_at"],
        ),
    )
    conn.commit()
    conn.close()


def _db_list_quests(category: int | None = None, difficulty: int | None = None, level: int | None = None) -> list[dict[str, Any]]:
    conn = _get_db()
    query = "SELECT * FROM quests WHERE 1=1"
    params: list[Any] = []
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if difficulty is not None:
        query += " AND difficulty = ?"
        params.append(difficulty)
    if level is not None:
        query += " AND required_level <= ?"
        params.append(level)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for row in rows:
        q = dict(row)
        q["questions"] = json.loads(q["questions"])
        q["is_daily"] = bool(q["is_daily"])
        q["is_team_quest"] = bool(q["is_team_quest"])
        result.append(q)
    return result


def _db_record_completion(wallet: str, quest_id: str, score: float, xp_earned: int, token_reward: int) -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO quest_completions (wallet_address, quest_id, score, xp_earned, token_reward, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (wallet, quest_id, score, xp_earned, token_reward, _now_iso()),
    )
    conn.commit()
    conn.close()


def _db_has_completed_quest(wallet: str, quest_id: str) -> bool:
    conn = _get_db()
    row = conn.execute("SELECT 1 FROM quest_completions WHERE wallet_address = ? AND quest_id = ?", (wallet, quest_id)).fetchone()
    conn.close()
    return row is not None


def _db_save_badge(wallet: str, badge: dict[str, Any]) -> None:
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO badges (wallet_address, badge_id, name, description, rarity, earned_at) VALUES (?, ?, ?, ?, ?, ?)",
            (wallet, badge["id"], badge["name"], badge["description"], badge["rarity"], badge["earned_at"]),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _db_get_badges(wallet: str) -> list[dict[str, Any]]:
    conn = _get_db()
    rows = conn.execute("SELECT badge_id, name, description, rarity, earned_at FROM badges WHERE wallet_address = ?", (wallet,)).fetchall()
    conn.close()
    return [{"id": r["badge_id"], "name": r["name"], "description": r["description"], "rarity": r["rarity"], "earned_at": r["earned_at"]} for r in rows]


def _db_save_chat(wallet: str, npc_id: str, role: str, content: str) -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO chat_history (wallet_address, npc_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (wallet, npc_id, role, content, _now_iso()),
    )
    conn.commit()
    conn.close()


def _db_get_chat_history(wallet: str, npc_id: str, limit: int = 20) -> list[dict[str, str]]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE wallet_address = ? AND npc_id = ? ORDER BY id DESC LIMIT ?",
        (wallet, npc_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _db_get_team(team_id: str) -> dict[str, Any] | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    t = dict(row)
    members = conn.execute("SELECT wallet_address FROM team_members WHERE team_id = ?", (team_id,)).fetchall()
    conn.close()
    t["members"] = [m["wallet_address"] for m in members]
    return t


def _db_create_team(team_id: str, name: str, leader: str, leader_xp: int) -> dict[str, Any]:
    conn = _get_db()
    conn.execute("INSERT INTO teams (id, name, leader, total_xp) VALUES (?, ?, ?, ?)", (team_id, name, leader, leader_xp))
    conn.execute("INSERT INTO team_members (team_id, wallet_address, joined_at) VALUES (?, ?, ?)", (team_id, leader, _now_iso()))
    conn.commit()
    conn.close()
    return _db_get_team(team_id)


def _db_list_all_players() -> list[dict[str, Any]]:
    conn = _get_db()
    rows = conn.execute("SELECT wallet_address, username, xp, level, total_quests_completed, daily_streak, longest_streak, last_activity_ts, lesson_progress FROM players ORDER BY level DESC, xp DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        p = dict(row)
        p["lesson_progress"] = json.loads(p["lesson_progress"])
        result.append(p)
    return result


def _track_event(event_type: str, data: dict[str, Any]) -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO analytics_events (event_type, data, timestamp) VALUES (?, ?, ?)",
        (event_type, json.dumps(data), _now_iso()),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
#  Seed data
# ──────────────────────────────────────────────

def _seed_quests() -> None:
    """Seed sample quests if the quests table is empty."""
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM quests").fetchone()["c"]
    conn.close()
    if count > 0:
        return

    seed_quests = [
        {
            "id": _gen_id(),
            "title": "Budget Like a Boss",
            "description": "Learn the 50/30/20 rule and create your first personal budget. Master the fundamentals of money management that separate the financially free from the paycheck-to-paycheck crowd.",
            "category": LessonCategory.BUDGETING,
            "category_name": CATEGORY_NAMES[LessonCategory.BUDGETING],
            "difficulty": QuestDifficulty.BEGINNER,
            "xp_reward": 50,
            "token_reward": 10_000_000,
            "required_level": 1,
            "expires_at": None,
            "is_daily": False,
            "is_team_quest": False,
            "questions": [
                {"question": "What does the 50/30/20 rule suggest?", "options": ["A) 50% needs, 30% wants, 20% savings", "B) 50% savings, 30% needs, 20% wants", "C) 50% wants, 30% savings, 20% needs", "D) 50% investments, 30% needs, 20% fun"], "correct_index": 0, "explanation": "The 50/30/20 rule allocates 50% of after-tax income to needs, 30% to wants, and 20% to savings.", "concept": "budgeting basics"},
                {"question": "What is zero-based budgeting?", "options": ["A) Having zero savings", "B) Every dollar is assigned a purpose", "C) Spending nothing for a month", "D) Starting fresh each year"], "correct_index": 1, "explanation": "Zero-based budgeting means every dollar of income is assigned to a category so income minus expenses equals zero.", "concept": "budgeting methods"},
                {"question": "Which is considered a 'need' in budgeting?", "options": ["A) Streaming subscriptions", "B) Restaurant meals", "C) Rent or mortgage", "D) New shoes"], "correct_index": 2, "explanation": "Rent/mortgage is a basic need. Streaming, dining out, and discretionary shopping are wants.", "concept": "needs vs wants"},
            ],
            "created_at": _now_iso(),
        },
        {
            "id": _gen_id(),
            "title": "Investing 101: Your Money's First Job",
            "description": "Understand compound interest, risk vs return, and why starting early is the biggest advantage you have. Turn your savings into a wealth-building machine.",
            "category": LessonCategory.INVESTING,
            "category_name": CATEGORY_NAMES[LessonCategory.INVESTING],
            "difficulty": QuestDifficulty.EASY,
            "xp_reward": 75,
            "token_reward": 15_000_000,
            "required_level": 1,
            "expires_at": None,
            "is_daily": False,
            "is_team_quest": False,
            "questions": [
                {"question": "What is compound interest?", "options": ["A) Interest on the principal only", "B) Interest on both principal and accumulated interest", "C) A fixed interest rate", "D) Interest paid monthly"], "correct_index": 1, "explanation": "Compound interest earns on both initial principal and previously accumulated interest, creating exponential growth.", "concept": "compound interest"},
                {"question": "What does diversification help reduce?", "options": ["A) Returns", "B) Risk", "C) Taxes", "D) Fees"], "correct_index": 1, "explanation": "Diversification spreads investments across assets to reduce impact of any single poor performer.", "concept": "diversification"},
                {"question": "What is an ETF?", "options": ["A) Electronic Transfer Fund", "B) Exchange-Traded Fund", "C) Extra Tax Filing", "D) Estimated Total Fees"], "correct_index": 1, "explanation": "An ETF (Exchange-Traded Fund) is a basket of securities that trades on a stock exchange like a single stock.", "concept": "investment vehicles"},
            ],
            "created_at": _now_iso(),
        },
        {
            "id": _gen_id(),
            "title": "Emergency Fund Essentials",
            "description": "Build your financial safety net. Learn how much to save, where to keep it, and why an emergency fund is the foundation of financial stability.",
            "category": LessonCategory.SAVING,
            "category_name": CATEGORY_NAMES[LessonCategory.SAVING],
            "difficulty": QuestDifficulty.BEGINNER,
            "xp_reward": 50,
            "token_reward": 10_000_000,
            "required_level": 1,
            "expires_at": None,
            "is_daily": False,
            "is_team_quest": False,
            "questions": [
                {"question": "How many months of expenses should an emergency fund cover?", "options": ["A) 1 month", "B) 3-6 months", "C) 12 months", "D) It doesn't matter"], "correct_index": 1, "explanation": "Experts recommend 3-6 months of living expenses in an easily accessible emergency fund.", "concept": "emergency fund"},
                {"question": "What is a high-yield savings account?", "options": ["A) A checking account with rewards", "B) A savings account offering above-average interest rates", "C) A stock brokerage account", "D) A certificate of deposit"], "correct_index": 1, "explanation": "High-yield savings accounts pay significantly more interest than traditional ones while keeping funds accessible.", "concept": "savings vehicles"},
                {"question": "What is the 'pay yourself first' strategy?", "options": ["A) Buy yourself gifts", "B) Save a portion before spending on anything else", "C) Pay off all debts first", "D) Invest in your own business"], "correct_index": 1, "explanation": "Pay yourself first means automatically setting aside savings before spending on other expenses.", "concept": "saving habits"},
            ],
            "created_at": _now_iso(),
        },
        {
            "id": _gen_id(),
            "title": "Credit Score Decoded",
            "description": "Your credit score is your financial reputation. Learn how it works, what affects it, and strategies to build and maintain excellent credit.",
            "category": LessonCategory.CREDIT,
            "category_name": CATEGORY_NAMES[LessonCategory.CREDIT],
            "difficulty": QuestDifficulty.MEDIUM,
            "xp_reward": 100,
            "token_reward": 20_000_000,
            "required_level": 1,
            "expires_at": None,
            "is_daily": False,
            "is_team_quest": False,
            "questions": [
                {"question": "What is a credit utilization ratio?", "options": ["A) Your total debt amount", "B) Percentage of available credit you're using", "C) Number of credit cards you own", "D) Monthly payment amount"], "correct_index": 1, "explanation": "Credit utilization is the percentage of total credit limit in use. Keep it below 30% for a healthy score.", "concept": "credit utilization"},
                {"question": "Which debt payoff method targets highest interest first?", "options": ["A) Snowball method", "B) Avalanche method", "C) Consolidation", "D) Minimum payment"], "correct_index": 1, "explanation": "The avalanche method prioritizes highest-interest debts first, saving the most money over time.", "concept": "debt strategies"},
                {"question": "What is the biggest factor in your FICO score?", "options": ["A) Credit mix", "B) Payment history", "C) Length of credit history", "D) New credit inquiries"], "correct_index": 1, "explanation": "Payment history makes up 35% of your FICO score, making it the single most important factor.", "concept": "credit scores"},
            ],
            "created_at": _now_iso(),
        },
        {
            "id": _gen_id(),
            "title": "Crypto Safety & DeFi Basics",
            "description": "Navigate the world of cryptocurrency safely. Learn about wallets, private keys, common scams, and the basics of decentralized finance.",
            "category": LessonCategory.CRYPTO,
            "category_name": CATEGORY_NAMES[LessonCategory.CRYPTO],
            "difficulty": QuestDifficulty.MEDIUM,
            "xp_reward": 100,
            "token_reward": 20_000_000,
            "required_level": 1,
            "expires_at": None,
            "is_daily": False,
            "is_team_quest": False,
            "questions": [
                {"question": "What is a private key in crypto?", "options": ["A) Your username", "B) A password to your exchange", "C) A cryptographic key that controls your assets", "D) Your wallet address"], "correct_index": 2, "explanation": "A private key is a cryptographic secret that proves ownership. Never share it.", "concept": "wallet security"},
                {"question": "What does 'DYOR' stand for in crypto?", "options": ["A) Do Your Own Research", "B) Double Your Own Returns", "C) Deposit Your Own Resources", "D) Digital Yield On Request"], "correct_index": 0, "explanation": "DYOR means Do Your Own Research. Always investigate before investing in any crypto project.", "concept": "crypto safety"},
                {"question": "What is a DEX?", "options": ["A) Digital Exchange Index", "B) Decentralized Exchange", "C) Derivative Exchange", "D) Deposit Exchange"], "correct_index": 1, "explanation": "A DEX (Decentralized Exchange) lets you trade crypto directly from your wallet without a central intermediary.", "concept": "DeFi basics"},
            ],
            "created_at": _now_iso(),
        },
    ]

    for quest in seed_quests:
        _db_create_quest(quest)

    logger.info("seed_quests_inserted", count=len(seed_quests))


# ──────────────────────────────────────────────
#  NPC Fallback Responses
# ──────────────────────────────────────────────

NPC_FALLBACK_RESPONSES = {
    "professor_luna": [
        "Great question! One of the most important budgeting principles is the 50/30/20 rule: allocate 50% of your income to needs, 30% to wants, and 20% to savings. It sounds simple, but it's incredibly powerful when applied consistently. Start by tracking your spending for just one week and you'll be amazed at what you discover!",
        "I love your curiosity! Here's something most people don't realize: the difference between being broke and being wealthy often isn't income, it's habits. Small daily choices like bringing lunch from home, automating your savings, or waiting 24 hours before impulse purchases can add up to tens of thousands over a few years.",
        "Let me share a key insight about saving: the 'pay yourself first' strategy is a game-changer. Before you pay bills or spend on anything else, automatically transfer a portion of every paycheck to savings. Even starting with just 5% makes a huge difference over time thanks to compound growth!",
        "Here's a tip that changed my students' lives: create a 'fun fund' in your budget! Many people fail at budgeting because they cut out ALL enjoyment. That's not sustainable. Budgeting isn't about restriction, it's about intentional spending. Allocate money for fun guilt-free, and you'll actually stick to your plan.",
        "Emergency funds are your financial superhero cape! Aim for 3-6 months of essential expenses in a high-yield savings account. I know that sounds like a lot, but start with a mini goal of just $500 to $1,000. That alone can cover most unexpected car repairs or medical bills without reaching for a credit card.",
    ],
    "trader_rex": [
        "Yo, great question! Think of investing like building a sports team. You wouldn't put all your players in one position, right? That's diversification! Spread your investments across stocks, bonds, and maybe some index funds. A diversified portfolio is like having a well-rounded team that can handle any opponent the market throws at you.",
        "Here's the real MVP play in investing: compound interest. Einstein supposedly called it the eighth wonder of the world. If you invest $200 a month starting at age 20 with an average 7% return, you'd have over $500,000 by age 60. Start late at 30 and it's only about $240,000. Time is your biggest asset!",
        "Let me keep it real about risk: every investment has it. But here's the cheat code, your time horizon matters most. If you're investing for 20+ years, short-term dips don't matter much. It's like losing one game in a season. What matters is the championship, the long game. Don't panic-sell during market drops!",
        "Dollar-cost averaging is like training consistently instead of cramming before the big game. Invest a fixed amount regularly regardless of market conditions. Sometimes you buy low, sometimes high, but over time you average out to a solid price. It removes emotion from investing and that's when you win.",
        "ETFs are the ultimate beginner play. Think of them like a highlight reel of the best stocks bundled together. One ETF can give you exposure to 500+ companies! Low fees, instant diversification, and you can start with just a few bucks. S&P 500 index funds have averaged about 10% annual returns historically. Not bad for a set-it-and-forget-it strategy!",
    ],
    "crypto_sage": [
        "Welcome to the decentralized future! First rule of crypto: not your keys, not your coins. Always secure your private keys and never share them with anyone. Use a hardware wallet for significant holdings. Think of your private key as the master password to your entire financial vault. Lose it and your funds are gone forever.",
        "DeFi is fascinating but tread carefully. Decentralized exchanges let you trade directly from your wallet, no middleman needed. But always DYOR, Do Your Own Research. Check if smart contracts are audited, look at the team behind the project, and never invest more than you can afford to lose. The crypto space has amazing opportunities and dangerous scams in equal measure.",
        "Let me break down blockchain simply: imagine a shared Google Doc that everyone can read but nobody can secretly edit. That's basically a blockchain. Every transaction is recorded permanently and transparently. This is why it's revolutionary for finance: it creates trust without needing a central authority like a bank.",
        "Gas fees are the toll you pay to use a blockchain network. When the network is busy, fees go up, just like surge pricing for ride-shares. To save on gas: transact during off-peak hours, use Layer 2 solutions like rollups, or consider blockchains with lower fees for smaller transactions. Smart timing can save you a lot!",
        "Here's my take on NFTs and digital ownership: the technology is powerful even if some use cases seem silly. NFTs can represent ownership of real estate, music royalties, gaming items, or identity credentials. The key is understanding what you're actually buying. Is there real utility? Is the community strong? Art is subjective but fundamentals are universal.",
    ],
    "credit_fox": [
        "Let's talk strategy! Your credit score is basically your financial reputation in a three-digit number. The biggest factor? Payment history at 35%. Even one missed payment can tank your score by 100+ points. Set up autopay for at least the minimum on every account. It's the simplest hack to protect your score!",
        "Here's a pro move: keep your credit utilization below 30%, but ideally under 10%. If your credit limit is $1,000, try to keep your balance under $100 when the statement closes. Some people strategically pay down their balance before the statement date. The lower your utilization, the higher your score climbs!",
        "The debt avalanche vs snowball debate is classic! Avalanche (paying highest interest first) saves the most money mathematically. But snowball (paying smallest balance first) gives you quick psychological wins that keep you motivated. Pick the one that fits your personality. The best strategy is the one you'll actually stick with!",
        "Credit cards aren't evil, they're tools. Used wisely, they build your credit history, offer purchase protection, and earn rewards. The golden rule: never carry a balance you can't pay in full each month. That 20%+ APR will eat your rewards alive. If you can't trust yourself yet, start with a secured card and set a spending limit.",
        "Want to level up your credit game? Become an authorized user on a family member's old, well-maintained credit card. Their positive payment history gets added to your credit report. Also, having a mix of credit types like a credit card plus an installment loan shows lenders you can handle different kinds of debt responsibly.",
    ],
}


# ──────────────────────────────────────────────
#  AI client
# ──────────────────────────────────────────────

ai_client: Any = None

security_scheme = HTTPBearer(auto_error=False)

# Wallet address regex — 0x followed by 64 hex chars (Aptos / Move style)
WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{1,64}$")

leaderboard_cache = TTLCache(maxsize=1, ttl=60)


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
    player = _db_get_player(wallet)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


def _build_leaderboard() -> list[dict[str, Any]]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT wallet_address, username, xp, level FROM players ORDER BY level DESC, xp DESC LIMIT 100"
    ).fetchall()
    conn.close()
    result = []
    for i, row in enumerate(rows):
        p = dict(row)
        badge_count_conn = _get_db()
        bc = badge_count_conn.execute("SELECT COUNT(*) as c FROM badges WHERE wallet_address = ?", (p["wallet_address"],)).fetchone()["c"]
        badge_count_conn.close()
        result.append({
            "rank": i + 1,
            "wallet_address": p["wallet_address"],
            "username": p["username"],
            "xp": p["xp"],
            "level": p["level"],
            "badges_count": bc,
        })
    return result


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
    # Initialize database
    _init_db()
    _seed_quests()
    # Try to import and init anthropic, but don't fail if unavailable
    if settings.anthropic_api_key:
        try:
            import anthropic
            ai_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        except Exception:
            logger.warning("anthropic_unavailable", msg="Claude AI features disabled")
            ai_client = None
    conn = _get_db()
    player_count = conn.execute("SELECT COUNT(*) as c FROM players").fetchone()["c"]
    quest_count = conn.execute("SELECT COUNT(*) as c FROM quests").fetchone()["c"]
    conn.close()
    logger.info("ludex_started", players=player_count, quests=quest_count, db=DB_PATH)
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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════
#  Health
# ══════════════════════════════════════════════

@app.get("/health")
async def health():
    try:
        conn = _get_db()
        player_count = conn.execute("SELECT COUNT(*) as c FROM players").fetchone()["c"]
        quest_count = conn.execute("SELECT COUNT(*) as c FROM quests").fetchone()["c"]
        completion_count = conn.execute("SELECT COUNT(*) as c FROM quest_completions").fetchone()["c"]
        badge_count = conn.execute("SELECT COUNT(*) as c FROM badges").fetchone()["c"]
        team_count = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]
        chat_count = conn.execute("SELECT COUNT(*) as c FROM chat_history").fetchone()["c"]
        conn.close()
        db_status = "connected"
    except Exception as e:
        player_count = quest_count = completion_count = badge_count = team_count = chat_count = 0
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "ludex",
        "timestamp": _now_iso(),
        "database": db_status,
        "ai_available": ai_client is not None,
        "counts": {
            "players": player_count,
            "quests": quest_count,
            "completions": completion_count,
            "badges": badge_count,
            "teams": team_count,
            "chat_messages": chat_count,
        },
    }


# ══════════════════════════════════════════════
#  Global stats
# ══════════════════════════════════════════════

@app.get("/stats")
async def global_stats():
    conn = _get_db()
    player_count = conn.execute("SELECT COUNT(*) as c FROM players").fetchone()["c"]
    quest_count = conn.execute("SELECT COUNT(*) as c FROM quests").fetchone()["c"]
    completions = conn.execute("SELECT COUNT(*) as c FROM quest_completions").fetchone()["c"]
    total_tokens = conn.execute("SELECT COALESCE(SUM(token_reward), 0) as t FROM quest_completions").fetchone()["t"]
    total_xp = conn.execute("SELECT COALESCE(SUM(xp_earned), 0) as t FROM quest_completions").fetchone()["t"]
    badge_count = conn.execute("SELECT COUNT(*) as c FROM badges").fetchone()["c"]
    team_count = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]
    conn.close()
    return {
        "total_players": player_count,
        "total_quests_available": quest_count,
        "total_quests_completed": completions,
        "total_tokens_distributed": total_tokens,
        "total_xp_earned": total_xp,
        "total_badges_earned": badge_count,
        "total_teams": team_count,
    }


# ══════════════════════════════════════════════
#  Player registration & profiles
# ══════════════════════════════════════════════

@app.post("/players", status_code=201)
async def register_player(body: PlayerCreate):
    wallet = _validate_wallet(body.wallet_address)

    existing = _db_get_player(wallet)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Player already registered")

    player = _db_create_player(wallet, body.username)
    _track_event("player_registered", {"wallet": wallet})
    logger.info("player_registered", wallet=wallet, username=body.username)

    token = _create_jwt(wallet)

    return {
        "player": PlayerResponse(**{k: v for k, v in player.items() if k in PlayerResponse.model_fields}),
        "token": token,
    }


@app.post("/auth/login")
async def login(body: PlayerCreate):
    """Authenticate an existing player and return a fresh JWT."""
    wallet = _validate_wallet(body.wallet_address)
    player = _db_get_player(wallet)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found. Register first.")
    if player["username"] != body.username:
        raise HTTPException(status_code=401, detail="Username does not match wallet.")
    return {"token": _create_jwt(wallet)}


@app.get("/players/{wallet}", response_model=PlayerResponse)
async def get_player(wallet: str, _caller: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    return PlayerResponse(**{k: v for k, v in player.items() if k in PlayerResponse.model_fields})


@app.get("/players/{wallet}/badges")
async def get_player_badges(wallet: str):
    """List all badges earned by a player."""
    badges = _db_get_badges(wallet)
    return {"wallet": wallet, "badges": badges, "count": len(badges)}


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

    # Calculate total tokens earned from quest completions
    conn = _get_db()
    tokens_row = conn.execute(
        "SELECT COALESCE(SUM(token_reward), 0) as t FROM quest_completions WHERE wallet_address = ?",
        (wallet,),
    ).fetchone()
    tokens_earned = tokens_row["t"]
    conn.close()

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
        "badges_count": len(player.get("badges", [])),
        "staking_active": player["staking"] is not None,
        "tokens_earned": tokens_earned,
    }


# ══════════════════════════════════════════════
#  Quest / Challenge system
# ══════════════════════════════════════════════

@app.post("/quests", response_model=QuestResponse, status_code=201)
async def create_quest(body: QuestCreate, wallet: str = Depends(_get_current_wallet)):
    quest_id = _gen_id()
    quest = {
        "id": quest_id,
        **body.model_dump(),
        "category_name": CATEGORY_NAMES.get(LessonCategory(body.category), "Unknown"),
        "questions": [],
        "created_at": _now_iso(),
    }
    _db_create_quest(quest)

    logger.info("quest_created", quest_id=quest_id, title=body.title)
    return QuestResponse(**quest)


@app.get("/quests", response_model=list[QuestResponse])
async def list_quests(
    category: int | None = None,
    difficulty: int | None = None,
    level: int | None = None,
):
    result = _db_list_quests(category=category, difficulty=difficulty, level=level)
    return [QuestResponse(**q) for q in result]


@app.get("/quests/{quest_id}", response_model=QuestResponse)
async def get_quest(quest_id: str):
    quest = _db_get_quest(quest_id)
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    return QuestResponse(**quest)


@app.post("/quests/{quest_id}/submit")
async def submit_quest_answers(quest_id: str, body: QuizAnswer, wallet: str = Depends(_get_current_wallet)):
    """Validate quiz answers, award XP and tokens."""
    quest = _db_get_quest(quest_id)
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")

    player = _get_player_or_404(wallet)

    if quest["required_level"] > player["level"]:
        raise HTTPException(status_code=403, detail="Level too low for this quest")

    if _db_has_completed_quest(wallet, quest_id) and not quest["is_daily"]:
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

    # Update lesson progress.
    cat_key = str(quest["category"])
    player["lesson_progress"][cat_key] = player["lesson_progress"].get(cat_key, 0) + 1

    # Save player state
    _db_update_player(player)

    # Record completion
    _db_record_completion(wallet, quest_id, score_pct, xp_earned, token_reward)

    _track_event("quest_completed", {
        "wallet": wallet,
        "quest_id": quest_id,
        "score": score_pct,
        "xp_earned": xp_earned,
    })

    # Auto-badge checks.
    badges_earned = _check_badge_eligibility(player)

    # Invalidate leaderboard cache so rankings reflect new XP immediately.
    leaderboard_cache.pop("lb", None)

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
        "player": {
            "xp": player["xp"],
            "level": player["level"],
            "total_quests_completed": player["total_quests_completed"],
            "daily_streak": player["daily_streak"],
        },
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
    existing_ids = {b["id"] for b in player.get("badges", [])}

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
        {"id": "social_5", "name": "Networker", "desc": "Added 5 friends", "rarity": 1, "check": lambda p: len(p.get("friends", [])) >= 5},
    ]

    wallet = player["wallet_address"]
    for rule in badge_rules:
        if rule["id"] not in existing_ids and rule["check"](player):
            badge = {
                "id": rule["id"],
                "name": rule["name"],
                "description": rule["desc"],
                "rarity": rule["rarity"],
                "earned_at": _now_iso(),
            }
            _db_save_badge(wallet, badge)
            earned.append(badge)

    return earned


# ══════════════════════════════════════════════
#  Challenge generation engine (AI-powered)
# ══════════════════════════════════════════════

@app.post("/challenges/generate")
async def generate_challenge(body: ChallengeGenerateRequest, wallet: str = Depends(_get_current_wallet)):
    """Use Claude to generate contextual financial literacy challenges."""
    category_name = CATEGORY_NAMES.get(LessonCategory(body.category), "Finance")
    difficulty_label = QuestDifficulty(body.difficulty).name.title()

    # Find relevant curriculum context.
    cat_lessons = CURRICULUM.get(LessonCategory(body.category), [])
    relevant_lessons = [l for l in cat_lessons if l["level"] <= body.player_level]
    concepts = []
    for lesson in relevant_lessons:
        concepts.extend(lesson["key_concepts"])

    # Try AI first, fall back to templates
    if ai_client is not None:
        try:
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
            _db_create_quest(quest)

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

    # Fallback: return template questions when no API key or AI failed.
    return _fallback_questions(body.category, body.difficulty, body.num_questions)


def _fallback_questions(category: int, difficulty: int, num: int) -> dict[str, Any]:
    """Template questions when AI is unavailable."""
    templates = {
        0: [  # Budgeting
            {"question": "What does the 50/30/20 rule suggest?", "options": ["A) 50% needs, 30% wants, 20% savings", "B) 50% savings, 30% needs, 20% wants", "C) 50% wants, 30% savings, 20% needs", "D) 50% investments, 30% needs, 20% fun"], "correct_index": 0, "explanation": "The 50/30/20 rule allocates 50% of after-tax income to needs, 30% to wants, and 20% to savings and debt repayment.", "concept": "budgeting basics"},
            {"question": "What is zero-based budgeting?", "options": ["A) Having zero savings", "B) Every dollar is assigned a purpose", "C) Spending nothing for a month", "D) Starting fresh each year"], "correct_index": 1, "explanation": "Zero-based budgeting means allocating every dollar of income to a specific category so income minus expenses equals zero.", "concept": "budgeting methods"},
            {"question": "What is the first step in creating a budget?", "options": ["A) Cut all expenses", "B) Track your current spending", "C) Open a savings account", "D) Cancel subscriptions"], "correct_index": 1, "explanation": "Before you can budget effectively, you need to understand where your money is currently going by tracking spending.", "concept": "budgeting basics"},
        ],
        1: [  # Investing
            {"question": "What is compound interest?", "options": ["A) Interest on the principal only", "B) Interest on both principal and accumulated interest", "C) A fixed interest rate", "D) Interest paid monthly"], "correct_index": 1, "explanation": "Compound interest is earned on both the initial principal and previously accumulated interest, creating exponential growth over time.", "concept": "compound interest"},
            {"question": "What does diversification help reduce?", "options": ["A) Returns", "B) Risk", "C) Taxes", "D) Fees"], "correct_index": 1, "explanation": "Diversification spreads investments across different assets to reduce the impact of any single investment's poor performance.", "concept": "diversification"},
            {"question": "What is dollar-cost averaging?", "options": ["A) Buying stocks at the lowest price", "B) Investing a fixed amount at regular intervals", "C) Converting currency at the best rate", "D) Averaging your portfolio returns"], "correct_index": 1, "explanation": "Dollar-cost averaging means investing a fixed amount regularly, which reduces the impact of market volatility over time.", "concept": "investment strategies"},
        ],
        2: [  # Saving
            {"question": "How many months of expenses should an emergency fund cover?", "options": ["A) 1 month", "B) 3-6 months", "C) 12 months", "D) It doesn't matter"], "correct_index": 1, "explanation": "Financial experts recommend saving 3-6 months of living expenses in an easily accessible emergency fund to cover unexpected costs.", "concept": "emergency fund"},
            {"question": "What is a high-yield savings account?", "options": ["A) A checking account with rewards", "B) A savings account that offers above-average interest rates", "C) A stock brokerage account", "D) A certificate of deposit"], "correct_index": 1, "explanation": "High-yield savings accounts pay significantly more interest than traditional savings accounts while keeping your money accessible.", "concept": "high-yield savings"},
            {"question": "What does 'pay yourself first' mean?", "options": ["A) Spend on things you enjoy", "B) Save before spending on anything else", "C) Pay off debt first", "D) Invest in yourself"], "correct_index": 1, "explanation": "Pay yourself first means automatically setting aside savings from each paycheck before paying bills or other expenses.", "concept": "saving strategies"},
        ],
        3: [  # Credit
            {"question": "What is a credit utilization ratio?", "options": ["A) Your total debt amount", "B) The percentage of available credit you are using", "C) The number of credit cards you own", "D) Your monthly payment amount"], "correct_index": 1, "explanation": "Credit utilization is the percentage of your total credit limit that you're using. Keeping it below 30% is generally recommended for a healthy credit score.", "concept": "credit utilization"},
            {"question": "Which debt payoff method targets the highest interest rate first?", "options": ["A) Snowball method", "B) Avalanche method", "C) Consolidation", "D) Minimum payment"], "correct_index": 1, "explanation": "The avalanche method prioritises debts with the highest interest rates first, saving you the most money in interest over time.", "concept": "debt payoff strategies"},
            {"question": "What makes up the largest portion of your FICO score?", "options": ["A) Credit mix", "B) Payment history (35%)", "C) Length of credit history", "D) New credit inquiries"], "correct_index": 1, "explanation": "Payment history accounts for 35% of your FICO score, making it the most important factor to maintain.", "concept": "credit scores"},
        ],
        4: [  # Crypto
            {"question": "What is a private key in crypto?", "options": ["A) Your username", "B) A password to your exchange", "C) A cryptographic key that controls your assets", "D) Your wallet address"], "correct_index": 2, "explanation": "A private key is a cryptographic secret that proves ownership of blockchain assets. Never share it — whoever has it controls your funds.", "concept": "wallet security"},
            {"question": "What does DYOR stand for?", "options": ["A) Do Your Own Research", "B) Double Your Own Returns", "C) Deposit Your Own Resources", "D) Diversify Your Ongoing Revenue"], "correct_index": 0, "explanation": "DYOR means Do Your Own Research. Always investigate before investing in any cryptocurrency or DeFi project.", "concept": "crypto safety"},
            {"question": "What is a DEX?", "options": ["A) Digital Exchange Index", "B) Decentralized Exchange", "C) Derivative Exchange", "D) Debit Exchange"], "correct_index": 1, "explanation": "A DEX (Decentralized Exchange) allows peer-to-peer crypto trading directly from your wallet without a central intermediary.", "concept": "DeFi basics"},
        ],
        5: [  # Taxes
            {"question": "What is the difference between a tax deduction and a tax credit?", "options": ["A) They are the same thing", "B) A deduction reduces taxable income; a credit reduces tax owed dollar-for-dollar", "C) A credit reduces income; a deduction reduces tax owed", "D) Neither affects how much you pay"], "correct_index": 1, "explanation": "A tax deduction lowers your taxable income, while a tax credit directly reduces the amount of tax you owe, making credits generally more valuable.", "concept": "deductions vs credits"},
            {"question": "What is a 401(k)?", "options": ["A) A type of bank account", "B) An employer-sponsored retirement savings plan with tax advantages", "C) A government bond", "D) A type of insurance policy"], "correct_index": 1, "explanation": "A 401(k) is a tax-advantaged retirement savings plan offered by employers, often with matching contributions that are essentially free money.", "concept": "tax-advantaged accounts"},
            {"question": "What is tax-loss harvesting?", "options": ["A) Avoiding taxes illegally", "B) Selling losing investments to offset capital gains", "C) Harvesting crops for tax deductions", "D) Filing taxes early for a discount"], "correct_index": 1, "explanation": "Tax-loss harvesting involves selling investments at a loss to offset capital gains taxes on winning investments.", "concept": "tax optimization"},
        ],
    }

    cat_questions = templates.get(category, templates[0])
    selected = (cat_questions * ((num // len(cat_questions)) + 1))[:num]

    quest_id = _gen_id()
    xp_reward = int(50 * DIFFICULTY_XP_MULTIPLIER.get(QuestDifficulty(difficulty), 1.0))
    token_reward = int(10_000_000 * DIFFICULTY_XP_MULTIPLIER.get(QuestDifficulty(difficulty), 1.0))

    quest = {
        "id": quest_id,
        "title": f"{CATEGORY_NAMES.get(LessonCategory(category), 'Finance')} Quiz",
        "description": "Test your knowledge",
        "category": category,
        "category_name": CATEGORY_NAMES.get(LessonCategory(category), "Finance"),
        "difficulty": difficulty,
        "xp_reward": xp_reward,
        "token_reward": token_reward,
        "required_level": 1,
        "expires_at": None,
        "is_daily": False,
        "is_team_quest": False,
        "questions": selected,
        "created_at": _now_iso(),
    }
    _db_create_quest(quest)

    return {
        "quest_id": quest_id,
        "questions": [{"question": q["question"], "options": q["options"], "concept": q.get("concept", "")} for q in selected],
        "xp_reward": xp_reward,
        "token_reward": token_reward,
    }


# ══════════════════════════════════════════════
#  AI NPC interactions
# ══════════════════════════════════════════════

def _get_npc_fallback_response(npc_id: str, player: dict[str, Any], message: str) -> str:
    """Return a contextual pre-written response based on the NPC and user message."""
    responses = NPC_FALLBACK_RESPONSES.get(npc_id, NPC_FALLBACK_RESPONSES["professor_luna"])

    # Try to match keywords to pick a relevant response
    message_lower = message.lower()
    keyword_map = {
        "professor_luna": [
            (["budget", "50/30/20", "spend", "expense", "money management"], 0),
            (["save", "saving", "habit", "wealth", "rich", "broke"], 1),
            (["pay yourself", "first", "automatic", "automate"], 2),
            (["fun", "enjoy", "restrict", "deprive", "guilt"], 3),
            (["emergency", "safety", "unexpected", "rainy day"], 4),
        ],
        "trader_rex": [
            (["diversif", "portfolio", "spread", "asset"], 0),
            (["compound", "interest", "grow", "time", "early", "start"], 1),
            (["risk", "loss", "lose", "crash", "drop", "bear"], 2),
            (["dca", "dollar cost", "regular", "consistent"], 3),
            (["etf", "index", "fund", "beginner", "start invest"], 4),
        ],
        "crypto_sage": [
            (["key", "private", "wallet", "secure", "seed"], 0),
            (["defi", "dex", "decentralized", "scam", "rug"], 1),
            (["blockchain", "how", "work", "what is", "explain"], 2),
            (["gas", "fee", "expensive", "cost", "transaction"], 3),
            (["nft", "token", "digital", "ownership"], 4),
        ],
        "credit_fox": [
            (["score", "fico", "credit score", "payment", "history"], 0),
            (["utilization", "limit", "balance", "ratio"], 1),
            (["debt", "payoff", "avalanche", "snowball", "owe"], 2),
            (["card", "credit card", "apr", "interest", "reward"], 3),
            (["build", "improve", "authorized", "mix", "level up"], 4),
        ],
    }

    npc_keywords = keyword_map.get(npc_id, [])
    for keywords, idx in npc_keywords:
        if any(kw in message_lower for kw in keywords):
            return responses[idx]

    # Default: pick a random response
    return random.choice(responses)


@app.post("/npc/chat", response_model=NPCChatResponse)
async def npc_chat(body: NPCChatRequest, wallet: str = Depends(_get_current_wallet)):
    """Chat with an AI NPC mentor. Earns small XP for educational interactions."""
    player = _get_player_or_404(wallet)

    if body.npc_id not in NPC_PERSONAS:
        raise HTTPException(status_code=404, detail="NPC not found")

    npc = NPC_PERSONAS[body.npc_id]

    # Retrieve chat history from DB
    history = _db_get_chat_history(wallet, body.npc_id, limit=20)

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

    # Save user message to DB
    _db_save_chat(wallet, body.npc_id, "user", body.message)

    # Add user message to history for AI call
    history.append({"role": "user", "content": body.message})

    if ai_client is None:
        # Fallback response using pre-written content
        reply = _get_npc_fallback_response(body.npc_id, player, body.message)
        xp_earned = 5
    else:
        try:
            response = await ai_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system=system_prompt,
                messages=history,
            )
            reply = response.content[0].text
            xp_earned = _calculate_chat_xp(body.message, reply)
        except Exception as e:
            logger.error("npc_chat_failed", error=str(e))
            reply = _get_npc_fallback_response(body.npc_id, player, body.message)
            xp_earned = 5

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

    # Save player state and assistant reply
    _db_update_player(player)
    _db_save_chat(wallet, body.npc_id, "assistant", reply)

    # Invalidate leaderboard cache so rankings reflect new XP.
    if xp_earned > 0:
        leaderboard_cache.pop("lb", None)

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
    if len(player.get("friends", [])) == 0:
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
    cached = leaderboard_cache.get("lb")
    if cached is not None:
        entries = cached
    else:
        entries = _build_leaderboard()
        leaderboard_cache["lb"] = entries
    return LeaderboardResponse(season=1, entries=entries, updated_at=_now_iso())


@app.get("/leaderboard/teams")
async def get_team_leaderboard():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM teams ORDER BY total_xp DESC LIMIT 50").fetchall()
    result = []
    for i, row in enumerate(rows):
        t = dict(row)
        member_count = conn.execute("SELECT COUNT(*) as c FROM team_members WHERE team_id = ?", (t["id"],)).fetchone()["c"]
        result.append({
            "rank": i + 1,
            "id": t["id"],
            "name": t["name"],
            "total_xp": t["total_xp"],
            "member_count": member_count,
        })
    conn.close()
    return {
        "teams": result,
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

    _db_update_player(player)
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
    _db_update_player(player)

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
    friend = _get_player_or_404(body.friend_address)  # ensure friend exists

    if body.friend_address in player.get("friends", []):
        raise HTTPException(status_code=409, detail="Already friends")

    if body.friend_address == wallet:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a friend")

    # Add friend to player
    friends = player.get("friends", [])
    friends.append(body.friend_address)
    player["friends"] = friends
    _db_update_player(player)

    # Reciprocal friendship
    friend_friends = friend.get("friends", [])
    if wallet not in friend_friends:
        friend_friends.append(wallet)
        friend["friends"] = friend_friends
        _db_update_player(friend)

    _check_badge_eligibility(player)

    return {"status": "friend_added", "friends_count": len(player["friends"])}


@app.get("/social/friends")
async def list_friends(wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    friends_data = []
    for f_addr in player.get("friends", []):
        f = _db_get_player(f_addr)
        if f:
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
    if player.get("team_id") is not None:
        raise HTTPException(status_code=409, detail="Already in a team. Leave first.")

    team_id = _gen_id()
    team = _db_create_team(team_id, body.name, wallet, player["xp"])

    player["team_id"] = team_id
    _db_update_player(player)

    return TeamResponse(**team)


@app.post("/teams/{team_id}/join")
async def join_team(team_id: str, wallet: str = Depends(_get_current_wallet)):
    player = _get_player_or_404(wallet)
    if player.get("team_id") is not None:
        raise HTTPException(status_code=409, detail="Already in a team")

    team = _db_get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    if len(team["members"]) >= 5:
        raise HTTPException(status_code=409, detail="Team is full (max 5)")

    conn = _get_db()
    conn.execute("INSERT INTO team_members (team_id, wallet_address, joined_at) VALUES (?, ?, ?)", (team_id, wallet, _now_iso()))
    conn.execute("UPDATE teams SET total_xp = total_xp + ? WHERE id = ?", (player["xp"], team_id))
    conn.commit()
    conn.close()

    player["team_id"] = team_id
    _db_update_player(player)

    team = _db_get_team(team_id)
    return {"status": "joined", "team": team}


@app.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(team_id: str):
    team = _db_get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamResponse(**team)


# ══════════════════════════════════════════════
#  Player analytics
# ══════════════════════════════════════════════

@app.get("/analytics/overview", response_model=AnalyticsResponse)
async def get_analytics():
    now = time.time()
    all_players = _db_list_all_players()

    active_24h = sum(1 for p in all_players if now - p.get("last_activity_ts", 0) < 86400)
    avg_level = sum(p["level"] for p in all_players) / max(len(all_players), 1)

    # Most popular category.
    cat_counts: dict[str, int] = {}
    for p in all_players:
        for cat_key, count in p["lesson_progress"].items():
            cat_counts[cat_key] = cat_counts.get(cat_key, 0) + count
    top_cat_key = max(cat_counts, key=cat_counts.get, default="0") if cat_counts else "0"
    top_cat = CATEGORY_NAMES.get(LessonCategory(int(top_cat_key)), "Budgeting")

    # 7-day retention (players active in last 7 days / total).
    active_7d = sum(1 for p in all_players if now - p.get("last_activity_ts", 0) < 604800)
    retention = active_7d / max(len(all_players), 1)

    total_quests = sum(p["total_quests_completed"] for p in all_players)
    total_tokens = total_quests * 10_000_000  # approximate

    return AnalyticsResponse(
        total_players=len(all_players),
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
    chat_xp = player.get("chat_xp_today", 0)

    return {
        "wallet": wallet,
        "username": player["username"],
        "level": player["level"],
        "total_xp_earned": player["xp"] + sum(_xp_for_level(l) for l in range(1, player["level"])),
        "quests_completed": player["total_quests_completed"],
        "category_breakdown": category_breakdown,
        "badges_earned": len(player.get("badges", [])),
        "current_streak": player["daily_streak"],
        "longest_streak": player["longest_streak"],
        "friends_count": len(player.get("friends", [])),
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
    player = _db_get_player(wallet) if wallet else None

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
