# LUDEX -- Technical & Strategic Audit Report

**Auditor:** Senior Technical Auditor (AI-Assisted)
**Date:** 2026-03-23
**Project:** Ludex -- Play-to-Learn GameFi on OneChain
**Context:** OneHack 3.0 | AI & GameFi Edition

---

## 1. CODE QUALITY -- 7.5 / 10

**Strengths:**
- Clean, well-organized file structure with clear separation of concerns (contracts, backend, frontend, pitch, docs).
- Consistent coding style across all files. Move contract uses descriptive section headers and comments. Python backend follows modern conventions (type hints, Pydantic models, async patterns).
- Smart use of enums, constants, and configuration classes. Error codes are well-defined in the Move contract.
- Both backend and smart contract mirror the same game logic (XP formula, streak calculation, staking multiplier), indicating thoughtful architectural alignment.

**Weaknesses:**
- Backend uses in-memory dictionaries (`players`, `quests`, `teams`) with no persistence. A server restart wipes all data. The `requirements.txt` includes SQLAlchemy, Alembic, asyncpg, and aiosqlite, but none are used -- pure dead dependencies.
- No authentication or authorization on any API endpoint. Any caller can impersonate any wallet by passing a `wallet` query parameter. The `jwt_secret` is configured but JWT is never implemented.
- No input sanitization on wallet addresses -- no format validation, no checksum verification.
- No tests exist anywhere in the project.
- The `requirements.txt` lists 22 dependencies but only ~7 are actually imported (FastAPI, uvicorn, pydantic, pydantic-settings, anthropic, httpx, structlog, cachetools). Redis, Celery, APScheduler, passlib, python-jose, prometheus-client, websockets, python-multipart, tenacity, alembic, asyncpg, aiosqlite are unused dead weight.
- CORS is set to `allow_origins=["*"]` with `allow_credentials=True` -- a security anti-pattern even for hackathons.

---

## 2. LANDING PAGE -- 8.5 / 10

**Strengths:**
- Visually striking dark-mode design with a polished gradient color system (purple/pink/orange). Professional enough to pass as a funded startup's landing page.
- Spanish-language content is a strong differentiator -- speaks directly to the LATAM audience rather than defaulting to English. Shows market awareness.
- Responsive design with mobile breakpoints at 900px and 640px. Mobile hamburger menu implemented. Grid layouts collapse properly.
- Interactive elements: particle canvas, floating coins animation, scroll-reveal transitions, animated XP bar, and a live leaderboard preview with mock data. These demonstrate product vision effectively.
- Complete information architecture: hero, stats bar, problem, solution (3-step flow), game mechanics (5 districts), earn/rewards, leaderboard, CTA, footer. All sections a judge would expect.

**Weaknesses:**
- Entirely a single HTML file with inline CSS and JS (~900+ lines). No build system, no component reuse. Acceptable for a hackathon but the README claims "Next.js + TailwindCSS" -- this is vanilla HTML/CSS/JS. That is a misrepresentation.
- The "Jugar Ahora" and "Comenzar Aventura" CTAs link to `#cta` which is just another section on the same page, not an actual game or app. No wallet connection flow exists.
- The leaderboard section shows hardcoded mock data, not live on-chain data.
- Missing: favicon, Open Graph meta tags, SEO meta description. Minor but shows it was not prepared for public sharing.
- No accessibility attributes (aria-labels are present on the mobile toggle only). Color contrast on `--text-dim` (#94a3b8 on #0c0c1d) may fail WCAG AA for body text.

---

## 3. SMART CONTRACTS (Move) -- 8.0 / 10

**Strengths:**
- Comprehensive and well-structured contract at 842 lines. Covers player registration, XP/leveling, quests, badges (NFT-like), staking, leaderboard, teams, friends, and events. This is far more than most hackathon submissions deliver.
- Good use of Move's resource model: `PlayerState`, `GameState`, `QuestRegistry`, `BadgeRegistry`, `TeamRegistry`, and `Leaderboard` are all properly structured as on-chain resources with appropriate abilities (`key`, `store`, `copy`, `drop`).
- Admin access control is consistently enforced via `assert!(admin_addr == game.admin, E_NOT_ADMIN)` on all privileged functions.
- XP scaling formula (`BASE_XP_PER_LEVEL * level * (100 + XP_SCALING_FACTOR * level) / 100`) provides a smooth difficulty curve. Streak bonus is capped at 50% to prevent abuse.
- View functions are properly annotated with `#[view]` for read-only access. Event emission is consistent for all state-changing operations.
- Staking system with time-lock and graduated multiplier (1.2x to 2x based on lock duration) is a reasonable tokenomics mechanic.

**Weaknesses:**
- The contract uses `aptos_framework` imports, not OneChain-specific modules. If OneChain has its own standard library, this may not compile as-is. If OneChain is Aptos-compatible, this is fine -- but it should be explicitly stated.
- `initialize()` stores `TokenCaps` struct but the actual `move_to` for `TokenCaps` is missing. The `managed_coin::initialize` returns capabilities but they are not captured or stored. This means minting in `complete_quest` would fail because the admin would not have the `MintCapability` in their account. This is a **critical bug** that would prevent the core reward loop from working.
- `update_leaderboard` is a public entry function with no access control -- anyone can call it with any `player_addr`. While functionally harmless (it just refreshes rankings), it means gas costs for leaderboard updates are externalized.
- Linear search through vectors for duplicate badge checking and quest completion checking (`while (i < len)`) will not scale. For a hackathon this is acceptable but production would need indexed data structures.
- No `pause` check in any function despite `GameState.paused` field existing. The pause mechanism is declared but never enforced.
- The `LudexToken` struct has no abilities annotation -- it should have `has key` or similar depending on the framework requirements for coin types.
- No unit tests or Move test modules.

---

## 4. BACKEND -- 8.0 / 10

### AI NPC Quality: 8.5 / 10

- Four distinct NPC personas with well-crafted personalities (Professor Luna, Trader Rex, Crypto Sage, Credit Fox). Each has a defined specialty and tone. The system prompts are detailed with 10 behavioral rules including staying in character, educational focus, level-appropriate responses, and a responsible "never give real financial advice" guardrail.
- Conversation history is maintained per player-NPC pair (last 20 messages), enabling contextual multi-turn dialogue.
- Chat XP calculation rewards educational behavior: asking questions (`?`), using educational keywords (`how`, `why`, `explain`), and writing substantive messages all earn more XP. Daily XP cap of 100 prevents farming.
- Graceful fallbacks when AI client is unavailable -- templated responses that still reference the player's username, streak, and NPC specialty.
- Lesson content generation uses Claude with a well-structured prompt template (Hook, Core Concept, Real-World Example, Pro Tip, Did You Know). The prompt specifies ~300 words and conversational tone.

### Game Logic: 7.5 / 10

- Complete quest lifecycle: creation, listing (with filters), submission with scoring, XP/token calculation with streak/staking bonuses, and automatic badge eligibility checking.
- AI-powered challenge generation creates dynamic quiz questions using Claude, with fallback templates for offline mode. JSON parsing includes markdown code block stripping.
- Curriculum system is well-designed: 6 categories, 3-4 lessons each, level-gated progression, per-category tracking. Covers budgeting, investing, saving, credit, crypto, and taxes.
- 12 automatic badge rules covering quest milestones, streaks, levels, category completion, staking, and social activity.
- WebSocket support for live notifications (though no events currently trigger notifications).

**Weaknesses:**
- Zero authentication. No JWT implementation despite config existing. Any user can act as any wallet.
- All state is in-memory dictionaries. Production dependencies (Postgres, Redis, Celery) are in requirements.txt but completely unused.
- No rate limiting on any endpoint, including the AI-powered `/npc/chat` and `/challenges/generate` -- these could be abused to run up Claude API costs.
- No actual blockchain interaction. The backend never calls the OneChain RPC despite having `onechain_rpc_url` configured. Quest completion on-chain, credential minting, and token distribution are all missing -- the backend and smart contract are not connected.
- The `wallet` parameter is passed as a query string, not extracted from a signed message or JWT. This is fundamentally insecure.
- Fallback questions are sparse: only 3 categories have templates (budgeting, investing, crypto), missing saving, credit, and taxes.

---

## 5. PITCH MATERIALS -- 9.0 / 10

**Strengths:**
- **Pitch Deck (Markdown):** Exceptional storytelling. Opens with a Steve Jobs quote and immediately frames the 200M youth stat. The problem-insight-solution arc is tight. Every slide serves a purpose. The "People don't avoid learning. They avoid boredom." insight is the kind of reframe that wins hackathons.
- **Pitch Deck (HTML):** A fully functional 12-slide presentation with keyboard/touch navigation, animated counters, speaker notes, fullscreen mode, progress bar, and particle effects. This is presentation infrastructure most hackathon teams never build. Speaker notes are thoughtful and prepared for judge Q&A.
- **Demo Script:** Minute-by-minute scripted demo with exact dialogue, transition cues, and post-demo FAQ preparation. The tone guidance ("like showing a friend something incredible you built last night") shows presentation coaching awareness.
- **Video Storyboard:** Scene-by-scene breakdown with timing, visual direction, audio cues, and production notes. Includes music sourcing guidance, voiceover casting notes (native Spanish speaker), and editing principles ("no shot longer than 5 seconds"). Professional-grade production planning.
- Consistent messaging across all materials: "Aprende jugando. Gana viviendo." tagline, 200M stat, Play-Learn-Earn loop, district metaphor.

**Weaknesses:**
- The pitch deck references "3 smart contracts" (RewardPool, Leaderboard, Credential) but the actual codebase has a single monolithic contract (`ludex_game.move`) that combines all three. This inconsistency could be caught by technical judges.
- Tech stack slide claims Node.js backend but the actual implementation is Python/FastAPI. Claims Next.js frontend but it is vanilla HTML.
- Some market data citations are vague ("S&P/World Bank", "Newzoo, 2024") -- specific report names would strengthen credibility.
- The demo script assumes a game client (Unity/Godot) that does not exist in the codebase. The demo as scripted cannot be performed with current deliverables.

---

## 6. INVESTOR READINESS -- 8.5 / 10

**Strengths:**
- The Investor Brief is remarkably thorough for a hackathon project: problem with cited data, solution with comparison matrix, "Why Now" thesis (6 converging trends), TAM/SAM/SOM with methodology, unit economics table, competitive moat analysis, go-to-market phasing, business model with 5 revenue streams, 3-year financial projections, team requirements, funding ask with use-of-funds breakdown, risk matrix with mitigations, exit strategy with comparable transactions.
- Unit economics are well-reasoned: $2.50 CAC (gaming organic), $72 LTV, 28.8:1 LTV:CAC, 78% gross margin. The numbers are optimistic but internally consistent.
- Competitive analysis is honest and detailed. The moat thesis (AI NPC training data flywheel + curriculum + credential network effects) is defensible.
- Risk section identifies 5 real risks with specific mitigations. Not boilerplate.
- Comparable seed rounds (Duolingo $3.3M, Axie $1.5M, Platzi $2M) are well-chosen and make the $2.5M ask feel calibrated.

**Weaknesses:**
- Retention projection of "65%+ (projected, based on RPG engagement data)" is hand-waved. No specific RPG engagement data is cited. This is the most important metric in the deck and it is the weakest-supported claim.
- Year 1 projections ($100K revenue, 50K players) are aggressive for a product that does not yet have a game client.
- The team section lists roles but no actual names or backgrounds. For a real investor, this is the first thing they would ask about.
- "Viral coefficient: 1.6x" is stated without any supporting data or calculation methodology.
- Path to profitability shows Year 3 at -$500K but the projections table shows $6M revenue and $280K monthly burn ($3.36M annual) -- these numbers do not reconcile. $6M - $3.36M = $2.64M positive, not -$500K.

---

## 7. HACKATHON FIT -- 7.5 / 10

**Strengths:**
- Directly addresses both hackathon tracks: AI (Claude-powered NPCs, AI challenge generation, AI lesson content) and GameFi (on-chain rewards, soulbound credentials, staking, leaderboard).
- OneChain integration via Move smart contracts. The contract is substantial and demonstrates genuine blockchain development competency.
- LATAM focus is a strong differentiator -- most hackathon teams target generic global markets.
- The breadth of deliverables is impressive: smart contract, backend API, landing page, pitch deck (markdown + HTML presentation), demo script, video storyboard, investor brief, README.

**Weaknesses:**
- **No working game.** The README checklist item "Playable game demo (1 district, 3 quests minimum)" is unchecked. There is no Unity/Godot client, no game interface, no playable demo. This is the single biggest gap for a GameFi hackathon. The project is a backend + landing page + smart contract, not a game.
- **No blockchain deployment evidence.** The README links are placeholders (`[Coming Soon](#)`, `[OneChain Explorer](#)`). No testnet deployment addresses are provided. The contract may not have been deployed.
- **Backend-to-chain integration is missing.** The FastAPI server and the Move contract are completely disconnected. There is no code that submits transactions to OneChain.
- The demo script describes interactions that cannot actually be performed with the current codebase (walking through districts, talking to NPC merchants in a game UI).

---

## 8. CRITICAL ISSUES

| # | Severity | Issue |
|---|----------|-------|
| 1 | **CRITICAL** | `TokenCaps` (MintCapability, BurnCapability, FreezeCapability) are never stored in `initialize()`. The `managed_coin::initialize` return values are discarded. This means `managed_coin::mint` in `complete_quest` will fail because the admin account will not have the mint capability resource. The entire reward loop is broken on-chain. |
| 2 | **CRITICAL** | No playable game exists. The core value proposition is "play-to-learn RPG" but there is no game client, no game UI, no interactive gameplay of any kind. The frontend is a marketing landing page only. |
| 3 | **HIGH** | Backend and smart contract are completely disconnected. No RPC calls, no transaction submission, no wallet signing. The two systems cannot interact. On-chain rewards, credentials, and leaderboard updates are non-functional. |
| 4 | **HIGH** | Zero authentication on the backend API. Any caller can impersonate any wallet. JWT infrastructure is configured but unimplemented. |
| 5 | **HIGH** | All backend state is in-memory. Server restart = total data loss. Database dependencies are listed but unused. |
| 6 | **MEDIUM** | Tech stack claims in pitch materials do not match implementation (Node.js vs. Python, Next.js vs. vanilla HTML). Technical judges will notice. |
| 7 | **MEDIUM** | `GameState.paused` field exists but is never checked. The pause mechanism is non-functional. |
| 8 | **LOW** | Investor brief financial projections contain internal inconsistency (Year 3 revenue vs. burn vs. stated loss). |

---

## 9. RECOMMENDATIONS

### P0 -- Must Fix Before Submission

1. **Fix the TokenCaps bug in the Move contract.** Capture the return values from `managed_coin::initialize` and `move_to` them to the admin account. Without this, the contract cannot mint tokens.
2. **Build a minimal playable demo.** Even a simple web-based UI (HTML/JS) that lets a player talk to an AI NPC, answer a quiz, and see XP update would satisfy the "playable demo" requirement. Does not need to be Unity/Godot.
3. **Connect backend to OneChain.** Implement at least one on-chain transaction from the backend (e.g., `register_player` or `complete_quest`). Use the Aptos SDK for Python or a simple HTTP RPC call.
4. **Align pitch materials with reality.** Update tech stack references to say Python/FastAPI backend and vanilla HTML frontend, or rename the files. Do not claim Node.js and Next.js if they are not used.

### P1 -- Should Fix

5. **Add basic authentication.** Implement wallet signature verification or at minimum JWT token issuance on player registration. The `python-jose` dependency is already listed.
6. **Deploy contract to testnet.** Get a testnet deployment address and update the README links. Having a real explorer link is powerful in demos.
7. **Add SQLite persistence.** The `aiosqlite` dependency is already listed. Even a minimal SQLAlchemy model for players would prevent data loss.
8. **Implement the `paused` check.** Add a `assert!(!game.paused, E_GAME_PAUSED)` assertion to all player-facing functions in the contract.
9. **Add at least 3-5 API tests.** Use pytest with FastAPI's TestClient. Focus on the core loop: register, complete quest, check XP/level-up.

### P2 -- Nice to Have

10. **Add rate limiting** to AI-powered endpoints (`/npc/chat`, `/challenges/generate`, `/lessons/{category}/start`).
11. **Remove unused dependencies** from `requirements.txt` (redis, celery, apscheduler, alembic, asyncpg, passlib, prometheus-client).
12. **Add Open Graph meta tags** to the landing page for social sharing previews.
13. **Implement team bonus XP** in the backend (currently only exists in the smart contract constants but is never applied).
14. **Add missing fallback quiz templates** for saving, credit, and taxes categories.

---

## 10. OVERALL SCORE & VERDICT

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Code Quality | 7.5 | 15% | 1.13 |
| Landing Page | 8.5 | 10% | 0.85 |
| Smart Contracts | 8.0 | 20% | 1.60 |
| Backend | 8.0 | 15% | 1.20 |
| Pitch Materials | 9.0 | 15% | 1.35 |
| Investor Readiness | 8.5 | 10% | 0.85 |
| Hackathon Fit | 7.5 | 15% | 1.13 |
| **OVERALL** | | | **8.10 / 10** |

### Verdict

**Ludex is a strong hackathon submission with exceptional pitch materials and solid backend/contract engineering, undermined by a critical gap: there is no game.** The project excels at vision, storytelling, and business planning -- the pitch deck and investor brief alone are top-tier hackathon deliverables. The Move smart contract is substantive and demonstrates real blockchain development skill. The backend API is well-architected with thoughtful AI NPC design.

However, for a **GameFi** hackathon, the absence of any playable game experience is a serious liability. The backend and smart contract are disconnected. The contract has a mint capability bug that breaks the core reward loop. The tech stack claims in pitch materials do not match the actual implementation.

**If the team fixes the P0 issues -- particularly building a minimal playable web demo and connecting the backend to the chain -- this project moves from "impressive pitch" to "impressive product." The vision, market thesis, and engineering foundation are all there. The execution just needs to catch up to the ambition.**

**Bottom line:** Top 20% of hackathon submissions on vision and materials. Drops to top 40% on working product. Fix the P0s and this is a contender.

---

*Report generated 2026-03-23. All scores reflect the state of the codebase at time of audit.*
