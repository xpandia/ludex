# LUDEX -- OneHack 3.0 Submission Package
### DoraHacks BUIDL Submission | AI & GameFi Track
### Deadline: March 27, 2026

---

## 1. DoraHacks Submission Text (Copy-Paste Ready)

---

### Ludex -- Play-to-Learn GameFi for Financial Literacy on OneChain

**Tagline:** Aprende jugando. Gana viviendo. (Learn by playing. Earn by living.)

**Problem**

Over 200 million young people across Latin America lack access to meaningful financial education. According to the S&P Global Financial Literacy Survey, 65% of adults in the region cannot answer basic financial literacy questions. Youth unemployment sits at 23% -- the highest in the world. Traditional financial education relies on textbooks nobody reads, courses nobody finishes, and lessons nobody remembers. Meanwhile, these same young people spend 3+ hours per day gaming. The gap between what they need to learn and how they want to learn it is massive and growing.

**Solution**

Ludex is a Play-to-Learn GameFi platform built on OneChain where every quest teaches a real financial concept and every achievement earns real on-chain rewards. Players open an interactive web app with quests across six financial categories: budgeting, investing, saving, credit, crypto, and taxes. Four AI-powered NPC mentors -- Professor Luna, Trader Rex, Crypto Sage, and Credit Fox -- built on Anthropic's Claude API, adapt every conversation to the player's knowledge level, creating personalized learning paths through narrative coaching.

The core loop is simple: Play, Learn, Earn. Accept quests, pass AI-generated quiz challenges, earn XP, level up, collect achievement badges, and receive LDX token rewards -- all designed to be recorded immutably on OneChain as verifiable soulbound credentials.

**What We Built (Hackathon Deliverables)**

- **Premium landing page** (`index.html`): Dark theme with particle animations, custom cursor, interactive NPC avatars, curriculum showcase with 6 categories and 23 lessons, live leaderboard from backend, and working registration form.
- **5-tab game app** (`app.html`): Home dashboard (player card, XP, streak, category grid), Quests (5 seeded quests with AI-generated challenges), NPCs (4 AI mentors with full chat interface), Ranking (podium leaderboard), Profile (badges, curriculum progress, staking).
- **FastAPI backend** (`server.py`): 21 REST endpoints, JWT authentication, SQLite persistence (8 tables, WAL mode), 5 seeded quests, 12 automatic badge rules, Claude API integration with fallback responses, daily XP caps.
- **Move smart contract** (`ludex_game.move`): 878 lines covering LDX token, player profiles, quests, badges, staking, leaderboard, teams, and admin controls.
- **Pitch materials**: Interactive HTML pitch deck, investor brief, demo script, video storyboard.

**OneChain Integration**

Our smart contract (`ludex_game.move`) is a comprehensive Move module targeting OneChain that handles:

- **LDX Token (Fungible Token):** Custom token with admin-controlled mint, burn, and freeze capabilities. Used as the reward currency throughout the game. 8 decimal places, monitored supply.
- **Player Profiles:** On-chain registration with XP tracking, leveling (up to level 100), daily streaks, and team membership.
- **Quest System:** Admin-created quests across 6 financial categories (budgeting, investing, saving, credit, crypto, taxes) with configurable difficulty, XP rewards, token rewards, level requirements, expiration, and daily/team flags.
- **NFT Achievement Badges:** Template-based badge system with 5 rarity tiers (common through legendary) and eligibility checks based on player level and quest completion count. Badges function as soulbound credentials verifying financial literacy competence.
- **Staking Mechanism:** Players lock LDX tokens for graduated reward multipliers (1.2x to 2x based on lock duration). Minimum 24-hour stake period. Stakers earn a 5% reward on unstake plus ongoing quest reward multipliers.
- **On-Chain Leaderboard:** Sorted by XP and level, capped at 100 entries, with seasonal resets every 30 days.
- **Teams and Social Features:** On-chain team creation (max 5 members), membership tracking, team XP aggregation, and friend lists.
- **Pause Mechanism:** Admin can pause all player-facing operations for maintenance or emergencies.

The contract uses OneChain's Move framework, importing from `aptos_framework` for coin operations, account management, event handling, and table storage. All player actions emit on-chain events for transparency and auditability.

The backend follows an oracle pattern: the FastAPI server validates quiz answers and player achievements off-chain, then calls the smart contract to record verified results on-chain. This keeps AI and game logic off-chain for performance while ensuring only proven achievements are immutably recorded.

**AI Integration**

The backend integrates Claude API (Anthropic) for two core functions:

1. **AI NPC Dialogue System:** Four distinct NPC personas (Professor Luna -- budgeting owl, Trader Rex -- investing bull, Crypto Sage -- DeFi wizard, Credit Fox -- credit strategist) each with unique personalities and specialties. Conversations maintain context, adapt difficulty based on player level, and weave financial concepts into narrative coaching. Claude's constitutional AI ensures all content remains educational, age-appropriate, and financially accurate. Fallback system provides 20 pre-written responses (5 per NPC) when Claude is unavailable.

2. **Challenge Generation Engine:** AI generates contextual multiple-choice quizzes tailored to the player's level, category, and difficulty. Questions are grounded in a structured curriculum spanning 6 categories and 23 lesson modules covering topics from the 50/30/20 rule to advanced DeFi strategies.

**Technical Architecture**

```
Player (Browser) --> Landing Page (index.html) --> Game App (app.html)
                                    |
                                    v
                         FastAPI Backend (Python/SQLite)
                              |              |
                              v              v
                       Claude API       OneChain (Move)
                    (AI NPCs, quizzes)   ludex_game.move
```

- Frontend: Vanilla HTML/CSS/JS -- premium landing page with particle animations, custom cursor, live backend data + 5-tab mobile-first game app with skeleton loaders, toast notifications, and confetti effects
- Backend: Python/FastAPI with JWT authentication, SQLite (WAL mode, 8 tables), seed data, and comprehensive REST API (21 endpoints)
- Blockchain: Single comprehensive Move contract (878 lines) covering all game logic
- AI: Anthropic Claude API with persona-based system prompts, conversation history tracking, adaptive difficulty, and offline fallback

**Business Model**

Three revenue streams aligned with the mission: (1) In-game cosmetic purchases and seasonal passes; (2) B2B/B2G educational licenses for schools, universities, and governments; (3) On-chain transaction fees on reward distributions and credential verification.

**Team**

A multidisciplinary team combining product design, blockchain development (Move on OneChain), full-stack engineering (Python/FastAPI), and AI integration (Claude API). We are builders from Latin America who know the problem because we lived it.

**Roadmap**

- Hackathon: Core loop with 5 quests, 4 AI NPCs, quiz challenges, leaderboard, badges, staking
- Month 1: Smart contract deployment on testnet, wallet integration (Petra/Martian), mobile PWA
- Month 3: Public beta in Colombia and Mexico, school partnerships
- Month 6: Full launch, DAO governance for curriculum updates, 50K players

**Links**

- GitHub: https://github.com/xpandia/ludex
- DoraHacks: https://dorahacks.io/hackathon/onehackathon/detail

---

## 2. Demo Video Script (3 Minutes Max)

---

### Setup Checklist (Before Recording)

1. Backend server running (`uvicorn server:app --reload --port 8000`)
2. Landing page open in browser (serve `src/frontend/index.html` via `python3 -m http.server 3000` from `src/frontend/`)
3. Game app ready (`http://localhost:3000/app.html`)
4. 2-3 players already registered so leaderboard has data
5. Screen recording software ready (1080p minimum, mic on)

---

### [0:00 - 0:20] THE HOOK -- Landing Page

> *Screen: Ludex landing page, particles animating in background, custom cursor visible.*

"Right now, 200 million young people in Latin America cannot answer a basic question about compound interest. Traditional education has failed them. Textbooks, PDFs, forty-minute lectures -- nobody finishes those.

But you know what they do finish? Games. Quests. Leaderboards.

This is Ludex -- Play-to-Learn GameFi for financial literacy, built on OneChain."

> *Scroll through the landing page. Show the NPC avatars, the curriculum tabs, the live leaderboard. Stop at the registration form.*

---

### [0:20 - 0:50] THE APP -- Registration & Dashboard

> *Register a new player from the landing page. App redirects to app.html.*

"I register with a wallet address and username. Now I am in the app."

> *Show the Home tab: player card with level, XP bar, streak. Scroll to show 6 category cards.*

"My dashboard shows my level, XP, streak, and six financial categories -- budgeting, investing, saving, credit, crypto, and taxes."

---

### [0:50 - 1:30] THE QUEST -- AI-Generated Challenge

> *Tap Quests tab. Open a quest. Click "Generar Desafio".*

"Let me take a budgeting quest. The AI generates a quiz tailored to my level."

> *Answer the multiple-choice questions. Submit. Show results with confetti and XP earned.*

"Three questions, generated by Claude in real-time. I passed -- 150 XP earned, tokens rewarded."

---

### [1:30 - 2:00] THE AI -- NPC Chat

> *Tap NPCs tab. Open Professor Luna. Send a message about budgeting.*

"Professor Luna is one of four AI mentors powered by Claude. Each has a unique personality and specialty."

> *Show the AI response appearing with typing indicator.*

"She adapts to my level, explains concepts conversationally, and stays in character. Every chat earns XP."

---

### [2:00 - 2:30] LEADERBOARD, PROFILE & SMART CONTRACT

> *Show Ranking tab with podium and ranked list. Then Profile tab with badges and curriculum progress.*

"The leaderboard ranks all players. My profile tracks badges, curriculum progress, and stats."

> *Quick cut to Move contract code in an editor -- scroll through key sections.*

"Under the hood: 878 lines of Move on OneChain -- LDX token, quests, badges, staking, leaderboard. All designed for on-chain verifiable credentials."

---

### [2:30 - 3:00] THE CLOSE

> *Return to landing page or pitch slide.*

"We sit at the intersection of EdTech and GameFi -- two markets worth $21 billion and growing. Nobody owns that intersection.

Ludex. Aprende jugando. Gana viviendo. Play to learn. Earn to grow.

Thank you."

> *Hold on landing page hero. End recording.*

---

## 3. OneChain Integration Documentation

---

### 3.1 Smart Contract Overview

**Contract:** `ludex_game.move`
**Module:** `ludex::ludex_game`
**Language:** Move (Aptos-compatible, OneChain)
**Size:** 878 lines
**Deployment target:** OneChain Testnet

### 3.2 OneChain Products and Framework Usage

| OneChain / Aptos Framework Module | Usage in Ludex |
|---|---|
| `aptos_framework::coin` | LDX token initialization, minting, burning, freezing, deposits, transfers, balance checks |
| `aptos_framework::managed_coin` | Player registration for LDX token (`register<LudexToken>`) |
| `aptos_framework::account` | Event handle creation for player activity tracking |
| `aptos_framework::event` | On-chain event emission (registration, level-ups, quest completion, badges, staking) |
| `aptos_framework::table` | Storage for quest registry, badge templates, and team registry |
| `std::timestamp` | Time-based logic: streak tracking, stake lock periods, quest expiration, season timing |
| `std::signer` | Address extraction and authorization checks |
| `std::string` | UTF-8 string handling for usernames, quest titles, badge names, image URIs |
| `std::vector` | Dynamic arrays for leaderboard entries, badges, friends, team members, quest lists |
| `std::option` | Optional fields (team membership, staking state) |

### 3.3 On-Chain Resources

| Resource | Stored At | Purpose |
|---|---|---|
| `GameState` | Admin account | Global stats: total players, quests completed, tokens distributed, pause flag |
| `TokenCaps` | Admin account | Mint, burn, freeze capabilities for LDX token |
| `QuestRegistry` | Admin account | All quest definitions with auto-incrementing IDs |
| `BadgeRegistry` | Admin account | Badge templates with eligibility criteria |
| `Leaderboard` | Admin account | Top 100 players, seasonal with 30-day periods |
| `TeamRegistry` | Admin account | Teams with members and aggregated XP |
| `PlayerState` | Player account | Individual profile, badges, quest progress, staking info, friends, event handle |

### 3.4 Entry Functions (Transactions)

| Function | Caller | Description |
|---|---|---|
| `initialize` | Admin (once) | Bootstrap game: create LDX token, registries, leaderboard |
| `register_player` | Player | Create on-chain profile, register for LDX token |
| `create_quest` | Admin | Add quest to registry with rewards and requirements |
| `complete_quest` | Admin/Oracle | Verify and reward quest completion (XP + tokens + streak) |
| `create_badge_template` | Admin | Define badge with rarity, level/quest requirements |
| `award_badge` | Admin/Oracle | Mint badge to player after eligibility check |
| `stake_tokens` | Player | Lock LDX for reward multiplier (1.2x-2x) |
| `unstake_tokens` | Admin | Return staked tokens + 5% reward after lock period |
| `update_leaderboard` | Anyone | Refresh player's leaderboard position |
| `new_season` | Admin | Reset leaderboard, start new 30-day season |
| `set_paused` | Admin | Pause/unpause all player-facing operations |
| `create_team` | Player | Create team, become leader |
| `join_team` | Player | Join existing team (max 5 members) |
| `add_friend` | Player | Add another registered player as friend |

### 3.5 View Functions (Read-Only)

| Function | Returns |
|---|---|
| `get_player_profile` | Full player profile (XP, level, streak, team) |
| `get_player_level` | Current level |
| `get_player_xp` | Current XP |
| `get_xp_to_next_level` | XP needed for next level |
| `get_player_badges` | All earned badges |
| `get_player_streak` | Current daily streak |
| `get_quest` | Quest details by ID |
| `get_stake_info` | Staking state (amount, unlock time, multiplier) |
| `get_game_stats` | Global stats (players, quests, tokens) |

### 3.6 Token Economics (LDX)

- **Name:** Ludex Token
- **Symbol:** LDX
- **Decimals:** 8
- **Base reward per quest:** 10,000,000 units (10 LDX)
- **Staking multiplier range:** 1.2x (1 week) to 2.0x (8+ weeks)
- **Staking reward on unstake:** 5% of staked amount
- **Streak bonus:** 5% XP per streak day, capped at 50%
- **Team bonus constant:** 10% (reserved for team quest rewards)

### 3.7 Backend-to-Chain Integration Pattern

The FastAPI backend acts as an oracle between players and the smart contract:

1. Player interacts with AI NPCs and completes quests via the REST API
2. Backend validates answers, calculates scores, and determines pass/fail (60% threshold)
3. On pass, backend calls `complete_quest` on-chain as the admin (oracle pattern)
4. Contract verifies admin authority, checks eligibility, awards XP, mints LDX tokens
5. Backend calls `award_badge` if milestone thresholds are met (12 automatic rules)
6. Leaderboard is updated via `update_leaderboard` after state changes

This oracle pattern ensures that only verified achievements are recorded on-chain while keeping the AI and game logic off-chain for performance and cost efficiency.

**Current status:** The backend runs the full game loop off-chain with SQLite persistence. The smart contract is complete and ready for deployment. On-chain integration (backend calling the Move contract via OneChain RPC) is the next development milestone.

---

## 4. Quick Start Commands

---

### Prerequisites

- Python 3.11+
- Anthropic API key (optional -- AI features fall back to template responses without it)

### 4.1 Backend Server

```bash
# Navigate to backend
cd src/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export LUDEX_ANTHROPIC_API_KEY="your-anthropic-api-key"  # optional
export LUDEX_DEBUG=true

# Start server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### 4.2 Frontend

```bash
# Serve frontend files
cd src/frontend
python3 -m http.server 3000
```

- Landing page: `http://localhost:3000/index.html`
- Game app: `http://localhost:3000/app.html`

Or open `src/frontend/index.html` and `src/frontend/app.html` directly in a browser.

### 4.3 Pitch Deck

```bash
# Open pitch deck HTML in browser
open pitch/pitch_deck.html
```

### 4.4 All Services at Once (Demo Day)

```bash
# Terminal 1: Backend
cd src/backend && source venv/bin/activate && \
  LUDEX_ANTHROPIC_API_KEY="your-key" uvicorn server:app --reload --port 8000

# Terminal 2: Frontend
cd src/frontend && python3 -m http.server 3000
```

Then open `http://localhost:3000/index.html` in browser.

---

## Submission Checklist

- [ ] DoraHacks BUIDL page created -- paste Section 1 as project description
- [ ] GitHub repo public at https://github.com/xpandia/ludex
- [ ] Demo video recorded (max 3 min) -- follow Section 2 script
- [ ] Demo video uploaded to YouTube/Loom and linked on DoraHacks
- [x] Smart contract code in repo (`src/contracts/ludex_game.move`)
- [x] Backend running for demo (`src/backend/server.py`)
- [x] Landing page accessible (`src/frontend/index.html`)
- [x] Game app accessible (`src/frontend/app.html`)
- [x] Pitch deck available (`pitch/pitch_deck.html`)
- [ ] Team members registered on DoraHacks (max 4, one project per participant)
- [ ] Track selected: GameFi (primary) + AI (secondary)

---

*Generated for OneHack 3.0 | AI & GameFi Edition | Deadline: March 27, 2026*
