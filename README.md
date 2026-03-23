# Ludex

**"Financial literacy shouldn't be a privilege. It should be a game everyone wins."**

---

## The Problem

Over **200 million young people across Latin America** lack access to meaningful financial education. Traditional methods fail them: boring curricula, zero engagement, no real-world incentive. Meanwhile, they spend hours every day gaming. The gap between what they need to learn and how they want to learn it is massive — and growing.

## The Solution

**Ludex** turns financial literacy into an RPG adventure on OneChain. Players navigate a living game world where every quest teaches a real financial concept — budgeting, investing, compound interest, risk management — and every achievement earns real on-chain rewards. AI-powered NPCs adapt to each player's level, making every conversation a personalized lesson.

Learn by playing. Earn by learning. No textbooks. No lectures. Just progress.

---

## How It Works

### 1. Play
Enter the Ludex world — an RPG city where every district represents a financial domain. Complete quests, negotiate with AI merchants, manage your in-game portfolio.

### 2. Learn
Every game mechanic maps to a real financial concept. AI NPCs (powered by Claude) adapt conversations to your knowledge level, explaining concepts through story — not slides.

### 3. Earn
Hit milestones, pass challenges, climb the leaderboard. Achievements are minted on OneChain as verifiable credentials. Top players earn token rewards from the community treasury.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Blockchain** | OneChain (Move-based) — single monolithic smart contract (`ludex_game.move`) covering rewards, credentials, leaderboard, staking, teams |
| **Frontend** | Vanilla HTML / CSS / JS — landing page with interactive animations |
| **AI NPCs** | Claude API (Anthropic) — adaptive dialogue, personalized financial coaching, AI-generated quizzes & lessons |
| **Backend** | Python / FastAPI — game state orchestration, REST API, JWT authentication |

### Architecture

```
Player (Web Browser)
    |
    v
Landing Page (HTML/CSS/JS)
    |
    v
FastAPI Backend (Python)  <-->  Claude API (AI NPCs, challenge generation)
    |
    v
OneChain (Move Contract)
  - ludex_game.move (players, quests, badges, staking, leaderboard, teams)
```

---

## Smart Contract (Move on OneChain)

A single comprehensive contract (`ludex_game.move`) that handles:

- **Player Profiles** — On-chain registration, XP, leveling, streaks
- **LDX Token** — Custom fungible token with admin-held mint/burn/freeze capabilities
- **Quest System** — Admin-created quests with category, difficulty, XP/token rewards, and expiry
- **Badge System** — NFT-like achievement badges with templates and eligibility checks
- **Staking** — Lock LDX tokens for graduated reward multipliers (1.2x–2x)
- **Leaderboard** — On-chain ranking with seasonal resets (top 100)
- **Teams & Social** — Team creation, membership, and friend lists
- **Pause Mechanism** — Admin can pause/unpause all player-facing operations

---

## Game Mechanics

| Mechanic | Financial Concept |
|---|---|
| Market District trading | Supply & demand, negotiation |
| Bank of Ludex deposits | Compound interest, savings |
| Insurance Guild quests | Risk management, premiums |
| Portfolio Arena PvP | Diversification, asset allocation |
| Tax Season events | Tax planning, obligations |

---

## Team

| Role | Responsibility |
|---|---|
| **Product & Design** | Game design, UX, brand identity |
| **Blockchain Dev** | Move smart contracts on OneChain |
| **Game Dev** | Unity/Godot world building, mechanics |
| **Full-Stack Dev** | Landing page, Python/FastAPI backend |
| **AI Engineer** | Claude API integration, NPC dialogue systems |

---

## Hackathon Submission Checklist

- [ ] Smart contracts deployed on OneChain testnet
- [ ] Playable game demo (1 district, 3 quests minimum)
- [ ] AI NPC conversations functional (Claude API)
- [ ] Landing page live
- [ ] Leaderboard with on-chain data
- [ ] 3-minute demo video
- [ ] Pitch deck (max 10 slides)
- [ ] DoraHacks BUIDL page submitted
- [ ] GitHub repo public with documentation

---

## Roadmap

**Hackathon (Week 1)** — Core loop: 1 district, AI NPCs, on-chain rewards
**Month 1** — 3 districts, mobile build, token economics refinement
**Month 3** — Public beta in Colombia & Mexico, school partnerships
**Month 6** — Full game launch, DAO governance for curriculum updates

---

## Links

- **DoraHacks:** [OneHack 3.0 Submission](#)
- **Live Demo:** [Coming Soon](#)
- **Contracts:** [OneChain Explorer](#)

---

<p align="center"><strong>Ludex</strong> — Play to learn. Earn to grow.</p>
