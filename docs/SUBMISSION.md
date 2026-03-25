# LUDEX -- OneHack 3.0 Submission
### DoraHacks BUIDL Submission | AI & GameFi Track
### Deadline: March 27, 2026

---

## 1. DoraHacks Submission Text (Copy-Paste Ready)

---

### Ludex -- Play-to-Learn GameFi for Financial Literacy on OneChain

**Tagline:** Learn by Playing. Earn by Living.

**The Problem**

Over 200 million young people across Latin America lack access to meaningful financial education. The S&P Global Financial Literacy Survey shows that 65% of adults in the region cannot answer basic questions about compound interest or inflation. Youth unemployment sits at 23%, the highest in the world. Traditional approaches -- textbooks, PDFs, mandatory courses -- have a completion rate under 5%. Meanwhile, these same young people spend 3+ hours per day gaming. The gap between what they need to learn and how they want to learn it is massive.

**What We Built**

Ludex is a working Play-to-Learn GameFi platform on OneChain where every quest teaches a real financial concept and every achievement earns on-chain rewards. Here is what is functional and demo-ready today:

- **21-endpoint REST API** (FastAPI/Python) with JWT authentication, SQLite persistence across 8 tables, and full game loop
- **5 seeded quests** covering budgeting, investing, saving, credit, and crypto -- each with 3 expert-written quiz questions
- **4 AI NPC mentors** (Professor Luna, Trader Rex, Crypto Sage, Credit Fox) powered by Claude API with 20 pre-written fallback responses for offline operation
- **AI challenge generation engine** that creates contextual multiple-choice quizzes tailored to player level and category
- **6-category curriculum** with 23 lesson modules spanning the 50/30/20 rule to advanced DeFi strategies
- **12 automatic badge rules** awarding achievements for quests, streaks, levels, staking, and social activity
- **Staking system** with graduated multipliers (1.2x to 2.0x) based on lock duration
- **Real-time leaderboard** ranked by level and XP with badge counts
- **Team system** supporting up to 5 members with aggregated XP tracking
- **Premium landing page** with particle animations, interactive NPC avatars, curriculum showcase, and live leaderboard data from the backend
- **5-tab game app** with dashboard, quests, NPC chat, rankings, and profile/staking
- **878-line Move smart contract** for OneChain covering LDX token, player profiles, quests, badges, staking, leaderboard, teams, and admin controls

**How the Demo Works**

1. Player registers with a wallet address and username -- receives a JWT
2. Dashboard shows level, XP, streak, and 6 financial category cards
3. Player accepts a quest, answers AI-generated quiz questions (60% pass threshold)
4. Correct answers award XP (with streak/difficulty/perfect-score bonuses) and LDX tokens
5. System checks 12 badge rules and awards any newly earned achievements
6. Player chats with AI NPC mentors who adapt to their level and earn bonus XP (capped at 100/day)
7. Leaderboard updates in real-time after every XP change
8. Player can stake LDX tokens for reward multipliers on future quests

Every feature above runs without external API keys. The AI features gracefully fall back to curated template responses when Claude API is unavailable.

**OneChain Integration**

Our smart contract (`src/contracts/ludex_game.move`) is a comprehensive Move module targeting OneChain:

| Feature | Implementation |
|---|---|
| LDX Token | Fungible token with admin mint/burn/freeze, 8 decimals |
| Player Profiles | On-chain registration, XP tracking, leveling (up to 100), streaks |
| Quest System | 6 categories, configurable difficulty/rewards/expiration/daily flags |
| NFT Badges | Template-based with 5 rarity tiers, soulbound credentials |
| Staking | Lock LDX for 1.2x-2.0x multipliers, 5% unstake reward |
| Leaderboard | Top 100 by XP, 30-day seasonal resets |
| Teams | On-chain creation, max 5 members, aggregated XP |

The backend follows an **oracle pattern**: FastAPI validates quiz answers off-chain, then calls the smart contract to record only verified achievements on-chain. This keeps AI and game logic performant while ensuring immutable, verifiable credentials.

The contract uses OneChain's Move framework, importing `aptos_framework::coin`, `aptos_framework::account`, `aptos_framework::event`, `aptos_framework::table`, and `std::timestamp` for time-based logic.

**AI Integration**

Two AI-powered systems, both with offline fallbacks:

1. **NPC Dialogue System:** 4 personas with unique personalities/specialties. Conversations maintain history, adapt to player level, and weave financial concepts into coaching. Keyword-matched fallback responses ensure the demo works without an API key.

2. **Challenge Generation Engine:** Generates multiple-choice quizzes using the 23-lesson curriculum as context. Falls back to 18 expert-written template questions (3 per category) when offline.

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

- Frontend: Vanilla HTML/CSS/JS with particle animations, skeleton loaders, confetti effects, and toast notifications
- Backend: Python 3.11+ / FastAPI, JWT auth, SQLite WAL mode, 8 tables, 21 endpoints
- Blockchain: Move smart contract (878 lines) covering all on-chain game logic
- AI: Anthropic Claude with persona prompts, conversation history, and offline fallback

**How to Run the Demo**

```bash
# 1. Clone and set up
git clone https://github.com/xpandia/ludex.git
cd ludex/src/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Start the server (creates DB and seeds 5 quests automatically)
python server.py

# 3. Seed demo data (8 players, completions, badges, team, chat history)
python seed_demo.py

# 4. Restart the server to pick up seeded data
python server.py

# 5. In a new terminal, serve the frontend
cd ludex/src/frontend
python3 -m http.server 3000

# 6. Open in browser
# Landing page: http://localhost:3000/index.html
# Game app:     http://localhost:3000/app.html
# API docs:     http://localhost:8000/docs
```

No API keys required. All features work with built-in fallback responses.

**Business Model**

Three revenue streams: (1) In-game cosmetic purchases and seasonal passes; (2) B2B/B2G educational licenses for schools and governments; (3) On-chain transaction fees on reward distributions and credential verification.

**Team**

Builders from Latin America who know this problem because we lived it. Product design, Move development, full-stack engineering, and AI integration.

**Links**

- GitHub: https://github.com/xpandia/ludex
- DoraHacks: https://dorahacks.io/hackathon/onehackathon/detail

---

## 2. Demo Video Script (3 Minutes Max)

---

### Setup Checklist (Before Recording)

1. Backend server running (`python server.py` from `src/backend/`)
2. Demo data seeded (`python seed_demo.py`)
3. Server restarted after seeding
4. Frontend served (`python3 -m http.server 3000` from `src/frontend/`)
5. Landing page open: `http://localhost:3000/index.html`
6. Screen recording software ready (1080p, mic on)

---

### [0:00 - 0:20] THE HOOK -- Landing Page

> *Screen: Ludex landing page, particles animating, custom cursor visible.*

"200 million young people in Latin America cannot answer a basic question about compound interest. Textbooks have a 5% completion rate. Games have a 70% daily return rate.

This is Ludex -- Play-to-Learn GameFi for financial literacy, built on OneChain."

> *Scroll through landing page. Show NPC avatars, curriculum tabs, live leaderboard.*

---

### [0:20 - 0:50] THE APP -- Registration & Dashboard

> *Register a new player. App redirects to app.html.*

"I register with a wallet address and username. JWT authentication, instant access."

> *Show Home tab: player card, XP bar, streak, 6 category cards.*

"My dashboard: level, XP, streak, and six financial categories -- budgeting, investing, saving, credit, crypto, and taxes."

---

### [0:50 - 1:30] THE QUEST -- AI-Generated Challenge

> *Tap Quests tab. Open a quest. Click Start Challenge.*

"I take a budgeting quest. Three questions about the 50/30/20 rule, zero-based budgeting, needs versus wants."

> *Answer questions. Submit. Show confetti and XP earned.*

"Passed with 100%. 62 XP earned with a perfect-score bonus, plus 10 LDX tokens. My first badge -- 'First Steps' -- just unlocked."

---

### [1:30 - 2:00] THE AI -- NPC Chat

> *Tap NPCs tab. Open Professor Luna. Ask about budgeting.*

"Professor Luna is one of four AI mentors. Each has a unique personality and specialty."

> *Show response appearing. Point out XP earned from chat.*

"She explains compound interest conversationally and earns me 5 XP. All four NPCs work without an API key using curated fallback responses."

---

### [2:00 - 2:30] LEADERBOARD, STAKING & SMART CONTRACT

> *Show Ranking tab with 8 players ranked. Then Profile tab with badges and staking.*

"The leaderboard has 8 players competing. My profile tracks badges, curriculum progress, and staking."

> *Quick cut to Move contract in editor.*

"878 lines of Move on OneChain: LDX token, quests, badges, staking, leaderboard, teams. Designed as soulbound financial literacy credentials."

---

### [2:30 - 3:00] THE CLOSE

> *Return to landing page.*

"EdTech is a $21 billion market. GameFi is a $12 billion market. Nobody owns the intersection.

Ludex. 21 API endpoints, 4 AI mentors, 878 lines of Move, 23 lessons, and zero API keys needed to demo.

Learn by Playing. Earn by Living."

> *Hold on landing page hero. End.*

---

## 3. Screenshots to Capture for Submission

1. **Landing page hero** -- particles, tagline, NPC avatars visible
2. **Landing page curriculum section** -- 6 category tabs expanded
3. **Landing page leaderboard** -- live data from backend showing 8+ players
4. **App: Home tab** -- player card with level, XP bar, streak, category grid
5. **App: Quest tab** -- quest list showing 5 seeded quests
6. **App: Quest challenge** -- multiple choice quiz with 4 options
7. **App: Quest result** -- confetti, XP earned, badge unlocked
8. **App: NPC chat** -- Professor Luna conversation with response
9. **App: Ranking tab** -- podium + ranked list with varied levels
10. **App: Profile tab** -- badges, curriculum progress, staking section
11. **API docs** -- FastAPI Swagger UI showing all 21 endpoints
12. **Smart contract** -- editor showing key sections of ludex_game.move

---

## 4. Quick Start Commands

### Prerequisites

- Python 3.11+
- No API keys required (all features have offline fallbacks)

### Backend + Demo Data

```bash
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start server (creates DB, seeds 5 quests)
python server.py
# Ctrl+C after it starts

# Seed demo data (8 players, badges, completions, team, chat)
python seed_demo.py

# Restart server with demo data loaded
python server.py
```

### Frontend

```bash
cd src/frontend
python3 -m http.server 3000
```

### Open

- Landing page: http://localhost:3000/index.html
- Game app: http://localhost:3000/app.html
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## Submission Checklist

- [ ] DoraHacks BUIDL page created -- paste Section 1 as project description
- [ ] GitHub repo public at https://github.com/xpandia/ludex
- [ ] Demo video recorded (max 3 min) -- follow Section 2 script
- [ ] Demo video uploaded to YouTube/Loom and linked on DoraHacks
- [ ] 12 screenshots captured (Section 3) and uploaded
- [x] Smart contract code in repo (`src/contracts/ludex_game.move`)
- [x] Backend running for demo (`src/backend/server.py`)
- [x] Demo seed script ready (`src/backend/seed_demo.py`)
- [x] Landing page accessible (`src/frontend/index.html`)
- [x] Game app accessible (`src/frontend/app.html`)
- [ ] Track selected: GameFi (primary) + AI (secondary)

---

*Ludex | OneHack 3.0 | AI & GameFi Edition | Deadline: March 27, 2026*
