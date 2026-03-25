#!/usr/bin/env python3
"""
Ludex Demo Seed Script
======================
Seeds the database with realistic demo data so the app looks alive
for the OneHack 3.0 submission. Safe to run multiple times -- it
wipes and re-seeds the player/badge/completion/team/chat tables
while leaving quests intact.

Usage:
    python seed_demo.py
"""

import json
import os
import random
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ludex.db")

# ── Demo players ──────────────────────────────────────────────

DEMO_PLAYERS = [
    {
        "wallet_address": "0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
        "username": "CryptoValeria",
        "xp": 45,
        "level": 5,
        "total_quests_completed": 12,
        "daily_streak": 7,
        "longest_streak": 14,
    },
    {
        "wallet_address": "0x2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c",
        "username": "FinanceCarlos",
        "xp": 80,
        "level": 3,
        "total_quests_completed": 8,
        "daily_streak": 3,
        "longest_streak": 9,
    },
    {
        "wallet_address": "0x3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d",
        "username": "LunaLearner",
        "xp": 20,
        "level": 7,
        "total_quests_completed": 22,
        "daily_streak": 15,
        "longest_streak": 30,
    },
    {
        "wallet_address": "0x4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e",
        "username": "MarketMiguel",
        "xp": 10,
        "level": 1,
        "total_quests_completed": 2,
        "daily_streak": 1,
        "longest_streak": 2,
    },
    {
        "wallet_address": "0x5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f",
        "username": "SavvySofia",
        "xp": 60,
        "level": 4,
        "total_quests_completed": 10,
        "daily_streak": 5,
        "longest_streak": 12,
    },
    {
        "wallet_address": "0x6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a",
        "username": "DefiDaniela",
        "xp": 30,
        "level": 3,
        "total_quests_completed": 6,
        "daily_streak": 2,
        "longest_streak": 5,
    },
    {
        "wallet_address": "0x7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b",
        "username": "BudgetBruno",
        "xp": 95,
        "level": 2,
        "total_quests_completed": 5,
        "daily_streak": 4,
        "longest_streak": 7,
    },
    {
        "wallet_address": "0x8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c",
        "username": "TokenTomas",
        "xp": 15,
        "level": 1,
        "total_quests_completed": 1,
        "daily_streak": 1,
        "longest_streak": 1,
    },
]

# Category names for lesson_progress keys
CATEGORY_KEYS = ["0", "1", "2", "3", "4", "5"]

# Badge definitions matching server.py rules
BADGE_DEFS = {
    "first_quest":  {"name": "First Steps",          "desc": "Completed your first quest",           "rarity": 0},
    "quest_10":     {"name": "Knowledge Seeker",      "desc": "Completed 10 quests",                  "rarity": 1},
    "streak_7":     {"name": "Week Warrior",          "desc": "7-day learning streak",                "rarity": 1},
    "streak_30":    {"name": "Consistency King",      "desc": "30-day learning streak",               "rarity": 3},
    "level_10":     {"name": "Rising Star",           "desc": "Reached level 10",                     "rarity": 1},
    "staker":       {"name": "Diamond Hands",         "desc": "Staked LDX tokens",                    "rarity": 1},
    "all_categories": {"name": "Renaissance Investor","desc": "Completed quests in all categories",   "rarity": 3},
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _past_iso(days_ago: int):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _gen_id():
    return uuid.uuid4().hex[:16]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def clear_demo_data(conn: sqlite3.Connection):
    """Remove all player-related data so we can re-seed cleanly."""
    conn.executescript("""
        DELETE FROM quest_completions;
        DELETE FROM chat_history;
        DELETE FROM badges;
        DELETE FROM team_members;
        DELETE FROM teams;
        DELETE FROM analytics_events;
        DELETE FROM players;
    """)
    conn.commit()
    print("[*] Cleared existing demo data.")


def seed_players(conn: sqlite3.Connection):
    """Insert demo players with varied stats."""
    for p in DEMO_PLAYERS:
        # Build random but reasonable lesson_progress
        progress = {}
        for key in CATEGORY_KEYS:
            if p["total_quests_completed"] > 5:
                progress[key] = random.randint(0, min(p["total_quests_completed"] // 3, 4))
            elif p["total_quests_completed"] > 0:
                progress[key] = random.choice([0, 0, 1])
            else:
                progress[key] = 0

        days_ago = random.randint(3, 30)
        registered_at = _past_iso(days_ago)

        conn.execute(
            """INSERT INTO players (
                wallet_address, username, xp, level, total_quests_completed,
                daily_streak, longest_streak, last_activity_ts, registered_at,
                lesson_progress, chat_xp_today, chat_xp_last_reset, friends
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p["wallet_address"],
                p["username"],
                p["xp"],
                p["level"],
                p["total_quests_completed"],
                p["daily_streak"],
                p["longest_streak"],
                time.time() - random.randint(0, 86400),  # active within last day
                registered_at,
                json.dumps(progress),
                random.randint(0, 30),
                _now_iso(),
                "[]",
            ),
        )
    conn.commit()
    print(f"[+] Seeded {len(DEMO_PLAYERS)} players.")


def seed_quest_completions(conn: sqlite3.Connection):
    """Record quest completions for players who have quests_completed > 0."""
    quest_ids = [row["id"] for row in conn.execute("SELECT id FROM quests").fetchall()]
    if not quest_ids:
        print("[!] No quests in DB -- skipping completions. Start the server first to seed quests.")
        return

    count = 0
    for p in DEMO_PLAYERS:
        n = p["total_quests_completed"]
        used_quests = set()
        for _ in range(n):
            qid = random.choice(quest_ids)
            # Allow repeats (simulates daily quests or generated challenges)
            score = random.uniform(65, 100)
            xp_earned = random.randint(40, 150)
            token_reward = random.choice([10_000_000, 15_000_000, 20_000_000])
            days_ago = random.randint(0, 20)
            conn.execute(
                """INSERT INTO quest_completions
                   (wallet_address, quest_id, score, xp_earned, token_reward, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (p["wallet_address"], qid, round(score, 1), xp_earned, token_reward, _past_iso(days_ago)),
            )
            count += 1
    conn.commit()
    print(f"[+] Seeded {count} quest completions.")


def seed_badges(conn: sqlite3.Connection):
    """Award badges based on player stats."""
    count = 0
    for p in DEMO_PLAYERS:
        wallet = p["wallet_address"]

        # first_quest: everyone with >= 1 quest
        if p["total_quests_completed"] >= 1:
            _award_badge(conn, wallet, "first_quest")
            count += 1

        # quest_10
        if p["total_quests_completed"] >= 10:
            _award_badge(conn, wallet, "quest_10")
            count += 1

        # streak_7
        if p["longest_streak"] >= 7:
            _award_badge(conn, wallet, "streak_7")
            count += 1

        # streak_30
        if p["longest_streak"] >= 30:
            _award_badge(conn, wallet, "streak_30")
            count += 1

    conn.commit()
    print(f"[+] Seeded {count} badges.")


def _award_badge(conn, wallet, badge_id):
    b = BADGE_DEFS[badge_id]
    conn.execute(
        "INSERT OR IGNORE INTO badges (wallet_address, badge_id, name, description, rarity, earned_at) VALUES (?, ?, ?, ?, ?, ?)",
        (wallet, badge_id, b["name"], b["desc"], b["rarity"], _past_iso(random.randint(0, 15))),
    )


def seed_chat_history(conn: sqlite3.Connection):
    """Add a handful of NPC chat messages so the chat UI is not empty."""
    npc_ids = ["professor_luna", "trader_rex", "crypto_sage", "credit_fox"]
    conversations = [
        ("user", "Hey, can you explain the 50/30/20 rule?"),
        ("assistant", "Great question! The 50/30/20 rule is a simple budgeting framework: allocate 50% of your after-tax income to needs like rent and groceries, 30% to wants like entertainment, and 20% to savings and debt repayment. It is one of the easiest ways to start managing your money!"),
        ("user", "What about compound interest?"),
        ("assistant", "Compound interest is when you earn interest on your interest! If you invest $1,000 at 7% annual return, after 10 years you would have about $1,967 -- nearly double -- without adding a single extra dollar. Start early and let time do the heavy lifting."),
        ("user", "How do I protect my crypto wallet?"),
        ("assistant", "Rule number one: never share your private keys or seed phrase with anyone. Use a hardware wallet for significant holdings. Enable 2FA on all exchange accounts. And always double-check wallet addresses before sending transactions. Your keys, your coins!"),
        ("user", "What is a good credit score?"),
        ("assistant", "A FICO score of 670-739 is considered 'good', 740-799 is 'very good', and 800+ is 'exceptional'. The biggest factor is payment history at 35%, so always pay at least the minimum on time. Keep credit utilization below 30% and you are on the right track!"),
    ]

    count = 0
    # Give top 4 players some chat history
    for i, p in enumerate(DEMO_PLAYERS[:4]):
        npc_id = npc_ids[i % len(npc_ids)]
        for role, content in conversations[i * 2 : i * 2 + 2]:
            conn.execute(
                "INSERT INTO chat_history (wallet_address, npc_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (p["wallet_address"], npc_id, role, content, _past_iso(random.randint(0, 7))),
            )
            count += 1
    conn.commit()
    print(f"[+] Seeded {count} chat messages.")


def seed_team(conn: sqlite3.Connection):
    """Create the 'LATAM Learners' team with 4 members."""
    team_id = _gen_id()
    leader = DEMO_PLAYERS[0]["wallet_address"]  # CryptoValeria

    # Calculate total XP of members
    member_indices = [0, 1, 2, 4]  # CryptoValeria, FinanceCarlos, LunaLearner, SavvySofia
    total_xp = sum(DEMO_PLAYERS[i]["xp"] for i in member_indices)

    conn.execute(
        "INSERT INTO teams (id, name, leader, total_xp) VALUES (?, ?, ?, ?)",
        (team_id, "LATAM Learners", leader, total_xp),
    )

    for idx in member_indices:
        wallet = DEMO_PLAYERS[idx]["wallet_address"]
        conn.execute(
            "INSERT INTO team_members (team_id, wallet_address, joined_at) VALUES (?, ?, ?)",
            (team_id, wallet, _past_iso(random.randint(1, 14))),
        )
        conn.execute(
            "UPDATE players SET team_id = ? WHERE wallet_address = ?",
            (team_id, wallet),
        )

    conn.commit()
    print(f"[+] Created team 'LATAM Learners' ({team_id}) with {len(member_indices)} members.")


def seed_staking(conn: sqlite3.Connection):
    """Give CryptoValeria an active stake for demo purposes."""
    wallet = DEMO_PLAYERS[0]["wallet_address"]  # CryptoValeria
    now = datetime.now(timezone.utc)
    staked_at = (now - timedelta(days=5)).isoformat()
    unlock_at = (now + timedelta(days=9)).isoformat()  # 14-day stake, 5 days in

    conn.execute(
        """UPDATE players SET
            staking_amount = ?,
            staking_staked_at = ?,
            staking_unlock_at = ?,
            staking_bonus_multiplier = ?
           WHERE wallet_address = ?""",
        (50_000_000, staked_at, unlock_at, 140, wallet),
    )
    conn.commit()
    print("[+] CryptoValeria is now staking 50 LDX (1.4x multiplier).")


def seed_friends(conn: sqlite3.Connection):
    """Wire up some friend connections."""
    pairs = [
        (0, 1), (0, 2), (1, 2), (2, 4), (0, 4), (4, 5),
    ]
    for a, b in pairs:
        wa = DEMO_PLAYERS[a]["wallet_address"]
        wb = DEMO_PLAYERS[b]["wallet_address"]
        # Add b to a's friends
        row = conn.execute("SELECT friends FROM players WHERE wallet_address = ?", (wa,)).fetchone()
        friends_a = json.loads(row["friends"])
        if wb not in friends_a:
            friends_a.append(wb)
            conn.execute("UPDATE players SET friends = ? WHERE wallet_address = ?", (json.dumps(friends_a), wa))
        # Reciprocal
        row = conn.execute("SELECT friends FROM players WHERE wallet_address = ?", (wb,)).fetchone()
        friends_b = json.loads(row["friends"])
        if wa not in friends_b:
            friends_b.append(wa)
            conn.execute("UPDATE players SET friends = ? WHERE wallet_address = ?", (json.dumps(friends_b), wb))

    conn.commit()
    print(f"[+] Seeded {len(pairs)} friend connections.")


def print_leaderboard(conn: sqlite3.Connection):
    """Print the resulting leaderboard."""
    rows = conn.execute(
        "SELECT username, level, xp, total_quests_completed, daily_streak FROM players ORDER BY level DESC, xp DESC"
    ).fetchall()
    print("\n=== LEADERBOARD ===")
    print(f"{'#':<4} {'Username':<18} {'Level':<7} {'XP':<8} {'Quests':<8} {'Streak'}")
    print("-" * 60)
    for i, r in enumerate(rows):
        print(f"{i+1:<4} {r['username']:<18} {r['level']:<7} {r['xp']:<8} {r['total_quests_completed']:<8} {r['daily_streak']}d")
    print()


def main():
    print("=" * 50)
    print("  Ludex Demo Seed Script")
    print("  DB:", DB_PATH)
    print("=" * 50)

    if not os.path.exists(DB_PATH):
        print("[!] Database not found. Start the server once first to create tables:")
        print("    cd src/backend && python server.py")
        return

    conn = connect()

    # Verify tables exist
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    required = ["players", "quests", "quest_completions", "badges", "teams", "team_members", "chat_history"]
    missing = [t for t in required if t not in tables]
    if missing:
        print(f"[!] Missing tables: {missing}. Start the server once first.")
        conn.close()
        return

    clear_demo_data(conn)
    seed_players(conn)
    seed_quest_completions(conn)
    seed_badges(conn)
    seed_chat_history(conn)
    seed_team(conn)
    seed_staking(conn)
    seed_friends(conn)
    print_leaderboard(conn)

    # Final counts
    counts = {}
    for table in required:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print("=== FINAL COUNTS ===")
    for t, c in counts.items():
        print(f"  {t}: {c}")

    conn.close()
    print("\n[OK] Demo data seeded successfully! Start the server and open the app.")


if __name__ == "__main__":
    main()
