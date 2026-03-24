# LUDEX -- Technical & Strategic Audit Report V2

**Auditor:** Senior Technical Auditor (AI-Assisted)
**Date:** 2026-03-24
**Project:** Ludex -- Play-to-Learn GameFi on OneChain
**Context:** OneHack 3.0 | AI & GameFi Edition | Deadline: March 27, 2026
**Scope:** Full codebase audit comparing current state to previous audit (2026-03-23)

---

## EXECUTIVE SUMMARY

Since the V1 audit 24 hours ago, the team has addressed **4 of 8 critical/high issues**:

1. **FIXED:** Backend now uses SQLite persistence (was in-memory dictionaries).
2. **FIXED:** JWT authentication is implemented on protected endpoints.
3. **FIXED:** A full game app (`app.html`) now exists with 5 tabs, quests, NPC chat, leaderboard, and profile.
4. **FIXED:** Landing page now connects to the backend (registration, live leaderboard, live stats).
5. **PARTIALLY FIXED:** The smart contract `initialize()` now correctly captures and stores `TokenCaps` via `coin::initialize` (not `managed_coin::initialize`). However, the contract has not been deployed to testnet.
6. **NOT FIXED:** Backend and smart contract remain disconnected -- no on-chain transactions from the backend.
7. **NOT FIXED:** Pitch materials still reference Node.js/Next.js/Unity/3 contracts instead of the actual stack.
8. **NOT FIXED:** `GameState.paused` is still never checked in the smart contract.

The project has made a **significant leap** in product completeness. It is now a functional web app, not just a landing page.

---

## 1. PRODUCT COMPLETENESS -- 7.0 / 10

**What works end-to-end:**
- User can register on the landing page (wallet + username), which creates a player in the SQLite DB, issues a JWT, and redirects to the app.
- User can log in from the app with wallet + username.
- App displays player card (avatar, level, XP bar, streak).
- App shows 6 financial categories with per-category lesson progress.
- Quests tab lists quests (seeded automatically if empty), filters by category.
- Clicking a quest opens a modal; "Generate Challenge" calls the backend which generates quiz questions via Claude (or falls back to templates).
- Quiz flow works: answer questions, submit, get scored, see XP/token rewards if passed (60%+ threshold).
- NPC tab lists 4 mentors; clicking opens a full chat screen with typing indicator, message history (in-memory per session), and suggested prompts.
- Leaderboard tab shows podium (top 3) and ranked list with "TU" badge for current user.
- Profile tab shows stats grid, badges section, curriculum progress, staking section, and logout.
- Registration from landing page CTA works and redirects to app.

**What is missing for a complete MVP:**
- No wallet connection (Petra, Martian, or any Move wallet). Users type a wallet address manually -- there is no signature verification or actual blockchain interaction.
- Chat history is lost on page refresh (stored in JS state, not persisted to server on the client side -- though the server does persist it in SQLite).
- Staking UI in the profile tab renders empty -- `stake-card` div has no content rendered by JavaScript.
- "Ver Demo" button on landing page does nothing (links to `#` with no handler).
- Teams tab in leaderboard shows "no hay equipos" but there is no UI to create or join teams.
- No sound effects, no micro-animations on quiz correct/wrong (just color changes).
- The app feels like a well-built prototype, not a released product. It needs more polish to pass as "real."

**Verdict:** The end-to-end flow **works**. A judge can register, take a quiz, chat with an NPC, and see their score on the leaderboard. This is a massive improvement from V1. But the lack of wallet integration means the "Fi" in "GameFi" is performative -- no on-chain transactions happen.

---

## 2. CODE QUALITY -- 7.5 / 10

**Strengths:**
- Backend is well-structured: clean separation of DB layer (`_db_*` functions), game logic helpers (`_process_level_ups`, `_update_streak`, `_check_badge_eligibility`), API routes, and AI integration.
- Pydantic models with proper field validation (`Field(ge=0, le=5)`, `Field(min_length=3, max_length=24)`).
- Wallet address validation with regex (`^0x[0-9a-fA-F]{1,64}$`).
- JWT implementation using `python-jose` with proper expiry, `sub` claim, and dependency injection via `_get_current_wallet`.
- SQLite with WAL mode and foreign keys enabled. Schema is comprehensive (8 tables).
- Frontend JS uses async/await consistently, has proper error handling in API calls, and escapes HTML in chat messages (`escapeHtml` function -- though I note it is referenced but the function definition itself is not visible in the read portions).
- Good use of CSS custom properties, responsive design with `clamp()`, and `dvh` units for mobile viewports.

**Weaknesses:**
- **SQL injection risk:** While parameterized queries are used (good), the `_db_list_quests` function builds queries with string concatenation for the `WHERE` clause. The parameters are appended correctly with `?`, but the pattern is fragile -- a future developer could easily introduce injection.
- **No input sanitization on username:** The username field accepts any string 3-24 characters. No check for HTML/script injection. When rendered in the frontend via `textContent` this is safe, but when rendered via `innerHTML` (leaderboard, chat messages), it could be exploited. The `escapeHtml` function is called in chat rendering which helps, but leaderboard and home rendering use template literals inserted via `innerHTML` without escaping usernames.
- **Connection leak potential:** Every `_db_*` function opens and closes its own SQLite connection. `_db_get_player` opens 3 separate connections (player, badges, completions). Should use a single connection per request.
- **No request validation on `/challenges/generate`:** The endpoint does not require authentication. Anyone can call it without a JWT, running up Claude API costs.
- **requirements.txt bloat:** Still lists redis, celery, apscheduler, asyncpg, alembic, prometheus-client, websockets -- none of which are used. 22 dependencies where ~12 are actually needed.
- **CORS is `allow_origins=["*"]`:** Wide open. The `settings.cors_origins` config exists but is not used -- the actual middleware uses `["*"]`. Note: `allow_credentials=False` is set now (was `True` in V1), which is at least not a security anti-pattern.
- **Frontend is two monolithic HTML files:** `index.html` is ~1700 lines, `app.html` is ~1500+ lines. No build system, no component reuse, no minification. Acceptable for a hackathon but the files are getting unwieldy.
- **No tests anywhere.**

---

## 3. LANDING PAGE QUALITY -- 8.5 / 10

**Strengths:**
- **Premium visual design.** The dark theme with purple/cyan/orange accents, Space Grotesk headings, and Inter body text creates a cohesive brand identity. This does NOT look AI-generated -- it looks like a designer built it.
- **Custom cursor** with dot and ring follower, disabled on touch devices. Magnetic button effect on CTAs. Tilt cards on feature grid. These microinteractions signal craft.
- **Phone mockup in hero** is pure CSS/HTML (no images), with animated XP bar, quest card, leaderboard preview, and tab bar. Effective product visualization.
- **NPC avatars are hand-crafted SVGs** -- owl with graduation cap (Professor Luna), bull with tie (Trader Rex), wizard with star hat (Crypto Sage), fox with magnifying glass (Credit Fox). These are charming and memorable.
- **Horizontal scroll section** for the solution (Juega/Aprende/Gana) with sticky positioning. Technically impressive.
- **Curriculum tabs** with 6 categories and 23 lessons listed. Interactive, content-rich.
- **Live data from backend:** Player count from `/health`, leaderboard from `/leaderboard`, registration form posts to `/players`.
- **Registration flow works:** Form validates, shows loading state, displays success/error toasts, redirects to `app.html` on success.
- **Spanish language throughout** -- authentic for LATAM market.

**Weaknesses:**
- **`cursor:none` on body** means users without custom cursor support (some browsers, assistive tech) get no cursor at all. The media query for `pointer:coarse` handles touch but not all edge cases.
- **No favicon, no Open Graph meta tags.** Sharing the URL on social media produces a blank preview.
- **"Ver Demo" button** in hero has no `href` or click handler -- it is dead.
- **Health endpoint mapping is fragile:** The landing page tries `data.player_count || data.players || data.total_players` but the actual health endpoint returns `counts.players`. The player count on the landing page will show 0 or fall back to "200M+ Jovenes objetivo" because the field path does not match.
- **Marquee text** ("200M+ jovenes") lacks accent marks -- should be "jóvenes," "educación," "años." The page is in Spanish but uses unaccented text throughout, which is common in informal contexts but looks less polished.
- **No loading state on the page itself.** When the backend is unreachable, the leaderboard silently falls back to mock data and the stats counter animates to 0 for players. A judge might think the backend is broken.
- **Accessibility:** No skip-to-content link, no aria-live regions for dynamic content, color contrast on `--text3` (#64748b on dark backgrounds) may fail WCAG AA.

---

## 4. GAME APP QUALITY -- 7.0 / 10

**Strengths:**
- **5-tab mobile-first app** with proper bottom nav, safe area insets, and screen transitions. Feels like a native app.
- **Auth flow** with register/login toggle, proper error messages, and localStorage persistence.
- **Player card** with avatar (first letter), level badge, animated XP bar with percentage. Good visual hierarchy.
- **Streak card** with fire emoji and pulsing animation. Motivating.
- **Quest cards** with colored left borders per category, star difficulty indicators, and XP/token reward display.
- **Quiz modal** with progress bar, question rendering, option selection, and results screen with confetti on pass. The flow feels gamified.
- **NPC chat screen** is full-screen with typing indicator, suggested prompts, and message history. The UX is solid.
- **Leaderboard** with podium visualization (gold/silver/bronze), "TU" badge for current user, and team tab.
- **Profile page** has stats grid, badges section (with earned/locked states and glow animations), curriculum progress bars, and staking section.
- **Skeleton loading states** throughout -- quest list, NPC grid, and leaderboard show shimmer placeholders while loading.
- **Toast notification system** with slide-in animation and auto-dismiss.

**Weaknesses:**
- **The app does NOT feel like a game.** It feels like a well-built dashboard with quiz functionality. There is no world, no exploration, no narrative. The NPC "chat" is a text interface, not an RPG dialogue. This is the fundamental gap between the pitch ("RPG world with districts") and reality ("quiz app with chat").
- **Quiz flow has a UX bug:** After selecting an answer, the "Siguiente" button appears, but there is no visual indication of whether the answer was correct until submission. The client does not know the correct answer (it is stored server-side), so the user clicks through all questions without feedback, then gets a summary. This is a missed opportunity for immediate learning feedback.
- **`escapeHtml` function IS properly defined** (line 1562) and used correctly in chat rendering. Chat messages are safe from XSS. However, leaderboard and home tab rendering still use template literals with `innerHTML` and do NOT escape usernames.
- **Staking section is empty.** The `stake-card` div exists but no JavaScript renders content into it. The staking feature is UI-incomplete.
- **Token display always shows 0.** The `stat-tokens` element is hardcoded to `formatTokens(0)`. There is no API call to fetch the player's token balance.
- **Category grid "onclick" calls `generateChallenge()`** which opens the quiz modal directly, skipping the quest list. This is confusing -- tapping "Presupuesto" from the home tab generates a quiz, while tapping a quest card from the quests tab opens the quest detail first. Inconsistent flows.
- **No offline/error state.** If the backend is down, the app shows skeleton loaders forever with no timeout or error message.
- **Chat history is session-only on the client.** Refreshing the page loses all chat messages (even though the server stores them in SQLite). The app should fetch chat history on NPC open.
- **Mobile experience is good** but the tab bar has no haptic/visual feedback on tap (no ripple effect, no press state).

---

## 5. BACKEND ROBUSTNESS -- 7.5 / 10

**Strengths:**
- **SQLite persistence is properly implemented.** 8 tables with foreign keys, WAL mode, and proper schema. Data survives server restarts.
- **JWT authentication** on protected endpoints (`/players/{wallet}`, `/players/{wallet}/progress`, `/npc/chat`, `/quests/{quest_id}/submit`, `/staking/*`, `/social/*`, `/teams/*`).
- **Seed data:** 5 well-crafted quests with 3 questions each are automatically seeded on first run. Questions have explanations and concept tags.
- **Fallback system for Claude:** 5 pre-written responses per NPC (20 total) with keyword matching for relevant topic selection. If Claude is unavailable, the NPC still "works" with substantive, educational responses.
- **Chat XP capping:** Daily cap of 100 XP from chat prevents farming. XP calculation rewards educational behavior (asking questions, using keywords like "how," "why," "explain").
- **Badge system:** 12 automatic badge rules covering quest milestones (1, 10, 50, 100), streaks (7, 30), levels (10, 25, 50), category completion, staking, and social.
- **Leaderboard caching** with TTLCache (60 second TTL), though the cache is declared but not actually used in `_build_leaderboard`.
- **Comprehensive API:** ~25+ endpoints covering health, stats, players, auth, quests, challenges, NPCs, leaderboard, staking, friends, and teams.

**Weaknesses:**
- **`/challenges/generate` has no authentication.** Anyone can call it repeatedly to generate Claude API calls. This is a cost vulnerability.
- **`/quests` POST has no authentication.** Anyone can create quests. This should be admin-only.
- **`/players/{wallet}/badges` has no authentication.** Minor, but inconsistent with other player endpoints.
- **No rate limiting anywhere.** The Claude-powered endpoints (`/npc/chat`, `/challenges/generate`) are especially vulnerable.
- **Leaderboard N+1 query problem:** `_build_leaderboard` fetches all players, then for each player opens a new connection to count badges. For 100 players, that is 101 database connections. Should use a JOIN or subquery.
- **Connection management:** Every DB function opens/closes its own connection. `_db_get_player` opens 3 separate connections. No connection pooling or context managers.
- **`leaderboard_cache` is declared but never populated.** The `_build_leaderboard` function always queries the database.
- **The health endpoint returns `counts.players`** but the landing page JavaScript looks for `data.player_count || data.players || data.total_players`. These do not match, so the live player count on the landing page is broken.
- **No data cleanup.** AI-generated quests accumulate in the database with no expiry enforcement. The `expires_at` field is stored but never checked when listing quests.
- **Streak logic edge case:** The 20-hour minimum between activities means a user who does two activities 19 hours apart gets no streak increment, even though they played on consecutive calendar days.

---

## 6. SMART CONTRACT -- 8.0 / 10

**Strengths:**
- **878 lines of Move code** covering the full game system: LDX token, player profiles, quests, badges, staking, leaderboard, teams, friends, events, and admin controls. This is one of the most comprehensive single-contract hackathon submissions I have seen.
- **`coin::initialize` correctly captures and stores capabilities** in `TokenCaps` struct. The V1 bug about discarded capabilities appears to be fixed in the current version (the code uses `coin::initialize` which returns `(burn_cap, freeze_cap, mint_cap)` and stores them).
- **Proper admin access control** on all privileged functions.
- **XP formula matches the backend** (`BASE_XP_PER_LEVEL * level * (100 + XP_SCALING_FACTOR * level) / 100`), ensuring on-chain and off-chain game logic are aligned.
- **Streak bonus capped at 50%** and **staking multiplier capped at 2x** prevent economic exploits.
- **View functions** properly annotated with `#[view]`.
- **Event emission** on all state changes (register, level up, quest complete, badge earned, stake, unstake).
- **`vector::insert` used for sorted leaderboard insertion** -- correct O(n) approach for Move.

**Weaknesses:**
- **`GameState.paused` is checked in `register_player` and `complete_quest` and `stake_tokens` but NOT in `join_team`, `create_team`, `add_friend`, or `update_leaderboard`.** Partial enforcement.
- **Not deployed.** No testnet address, no explorer link, no evidence the contract compiles against the actual OneChain framework. The `Move.toml` references `https://github.com/AOneChain/AOneChain-core.git` at `rev = "mainnet"` -- if this repo or revision does not exist, compilation fails.
- **`update_leaderboard` has no access control.** Anyone can call it for any player address. While functionally harmless, it externalizes gas costs.
- **Linear vector searches** for badge and quest completion duplicate checks. O(n) for each check. Acceptable at hackathon scale but will not scale.
- **No unit tests or Move test modules.**
- **`unstake_tokens` is admin-only** -- the player cannot unstake their own tokens. This may be intentional (oracle pattern) but it means a player's funds are at the admin's mercy.
- **`LudexToken` struct has `has key` only** (no other abilities like `store`). This should be fine for `coin::initialize` but worth verifying against the specific OneChain framework version.

---

## 7. PITCH & SUBMISSION MATERIALS -- 7.5 / 10

**Strengths:**
- **Story coherence is strong.** "Aprende jugando. Gana viviendo." tagline is consistent across every document. The 200M stat, Play-Learn-Earn loop, and district metaphor are repeated faithfully.
- **Investor brief is institutional-grade.** TAM/SAM/SOM with methodology, unit economics table, competitive moat analysis, go-to-market phasing, 3-year projections, risk matrix, exit strategy. Would get a meeting at a seed-stage fund.
- **Competitive analysis is honest.** Lists 7 direct competitors and 4 LATAM competitors with specific weaknesses relative to Ludex. Benchmarks against Duolingo, Axie, Cleo AI, and Greenlight.
- **Demo script and video storyboard are professional-grade.** Scene-by-scene timing, voiceover scripts, editing principles ("no shot longer than 5 seconds").
- **Pitch deck HTML** is a fully functional slide presentation with keyboard navigation, progress bar, animations, and speaker notes.
- **Submission package (`SUBMISSION.md`)** is comprehensive with copy-paste DoraHacks text, curl command sequences, and setup instructions.

**Weaknesses - CRITICAL INCONSISTENCIES:**

| Claim in Materials | Actual Implementation | Impact |
|---|---|---|
| "3 smart contracts (RewardPool, Leaderboard, Credential)" | 1 monolithic contract (`ludex_game.move`) | Technical judges will notice |
| "Node.js backend" (pitch deck, demo script, video storyboard) | Python/FastAPI | Factual error |
| "Next.js + TailwindCSS frontend" (pitch deck) | Vanilla HTML/CSS/JS | Factual error |
| "Unity/Godot game client" (pitch deck, demo script, README) | No game client exists | Demo script cannot be performed |
| "IPFS storage" (pitch deck) | No IPFS usage | Factual error |
| "Deployed. Live. Working." (demo script) | Not deployed to testnet | Factual claim about deployment |
| "Game client running, player already in the Ludex city overview" (demo script prerequisites) | No game client exists | Demo script is unusable |
| "3 districts, mobile build" for Month 1 | Zero districts exist | Roadmap credibility gap |
| Investor brief: Year 3 revenue $6M, monthly burn $280K ($3.36M/yr) = profit $2.64M | States "-$500K" for Year 3 | Internal contradiction |

**These inconsistencies are the single biggest risk to the submission.** A technical judge who reads "Node.js" in the pitch deck and sees `server.py` in the repo will question the team's credibility. The demo script literally cannot be performed because it requires a game client that does not exist.

**Data consistency issues:**
- Landing page says "23 lecciones" but the backend CURRICULUM has 22 lessons total (4+4+3+4+4+3).
- Investor brief says "20+ lesson modules" while landing page says "23 lecciones."
- Pitch deck says "1 district, AI NPCs, on-chain rewards, leaderboard" for hackathon -- there are 0 districts (no game world).

---

## 8. HACKATHON FIT -- 6.5 / 10

**Strengths:**
- Addresses both tracks: AI (Claude NPCs, challenge generation) and GameFi (token system, staking, badges, leaderboard).
- OneChain/Move integration is substantive -- 878 lines of contract code demonstrating genuine Move development.
- LATAM focus is a differentiator.
- The breadth of deliverables is impressive: contract + backend + landing + app + pitch deck + investor brief + competitive analysis + demo script + video storyboard + submission package.
- The app now has a working quiz/challenge flow that demonstrates the core learning mechanic.

**Weaknesses:**
- **Backend and chain are disconnected.** For a hackathon built on OneChain, there is no actual on-chain transaction anywhere in the running application. The contract is code-only.
- **No deployment evidence.** README links are still placeholders (`[Coming Soon](#)`, `[OneChain Explorer](#)`). Checklist items are unchecked.
- **No wallet integration.** Users type wallet addresses manually. No Petra/Martian/Pontem wallet connection. No transaction signing. This is critical for a blockchain hackathon.
- **The "game" is a quiz app with chat.** For a GameFi hackathon, judges expect gameplay. The app has no world, no exploration, no narrative beyond chat. It is functional and well-built, but it is not what the pitch promises.
- **Demo video not yet recorded.** 3 days to deadline with no video.
- **The demo script references features that do not exist** (walking through districts, talking to NPC merchants in a game UI, credential minting animation, OneChain explorer view). The script must be rewritten to match the actual product.

---

## 9. INVESTOR READINESS -- 8.0 / 10

**Strengths:**
- Investor brief would genuinely get a meeting at most seed-stage funds. The structure, data, and narrative are professional.
- Unit economics are internally consistent (mostly) and benchmarked against real comps.
- Competitive analysis is thorough and honest.
- Risk section identifies real risks with specific mitigations.
- $2.5M ask with use-of-funds breakdown is well-calibrated against comps (Duolingo $3.3M, Axie $1.5M, Platzi $2M).

**Weaknesses:**
- **No team names or backgrounds.** The most important element of a seed pitch is "who are you and why can you execute?" This is completely missing. Only role descriptions exist.
- **Retention claim is unsubstantiated.** "65%+ (projected, based on RPG engagement data)" -- no citation, no data, no methodology. This is the most important metric.
- **Viral coefficient "1.6x" is stated without support.**
- **Year 3 financial inconsistency** ($6M revenue - $3.36M expenses = $2.64M profit, but document says "-$500K").
- **The product does not yet demonstrate the thesis.** An investor who sees the actual app will see a quiz platform, not an RPG world. The gap between pitch vision and current product is significant.

---

## 10. CRITICAL ISSUES (Complete List)

### Bugs

| # | Severity | Issue | File |
|---|----------|-------|------|
| 1 | **VERIFIED OK** | `escapeHtml()` IS defined at line 1562 of `app.html`. Chat rendering is safe. | `app.html` |
| 2 | **HIGH** | Health endpoint returns `{counts: {players: N}}` but landing page looks for `data.player_count`. Live player count always shows 0 or falls back | `index.html` line ~1647, `server.py` line ~1034 |
| 3 | **MEDIUM** | Staking UI section in profile tab is empty -- no JS renders content into `#stake-card` | `app.html` |
| 4 | **MEDIUM** | Token balance always shows 0 -- `stat-tokens` hardcoded to `formatTokens(0)` with no API call | `app.html` line ~892 |
| 5 | **MEDIUM** | "Ver Demo" button in hero is dead -- no click handler or href | `index.html` line ~534 |
| 6 | **LOW** | `leaderboard_cache` TTLCache is declared but never populated or read | `server.py` line ~815 |
| 7 | **LOW** | Lesson count inconsistency: landing page says 23, backend CURRICULUM has 22 | `index.html`, `server.py` |

### Security Issues

| # | Severity | Issue | File |
|---|----------|-------|------|
| 8 | **HIGH** | `/challenges/generate` has no authentication -- anyone can trigger Claude API calls | `server.py` |
| 9 | **HIGH** | `/quests` POST has no authentication -- anyone can create quests | `server.py` |
| 10 | **MEDIUM** | XSS risk: usernames rendered via `innerHTML` without escaping in leaderboard and home tab | `app.html` |
| 11 | **MEDIUM** | No rate limiting on any endpoint, especially AI-powered ones | `server.py` |
| 12 | **LOW** | CORS `allow_origins=["*"]` -- overly permissive | `server.py` line ~1007 |

### Missing Features

| # | Severity | Issue |
|---|----------|-------|
| 13 | **CRITICAL** | No wallet integration -- users type addresses, no signing, no real blockchain interaction |
| 14 | **CRITICAL** | Backend never calls OneChain -- contract and server are disconnected |
| 15 | **HIGH** | Smart contract not deployed to any testnet |
| 16 | **HIGH** | No demo video recorded (3 days to deadline) |
| 17 | **MEDIUM** | No team creation/join UI in the app |
| 18 | **MEDIUM** | Chat history not fetched from server on NPC open (lost on page refresh) |
| 19 | **MEDIUM** | No quiz answer feedback (correct/wrong) until final submission |
| 20 | **LOW** | No favicon, no OG meta tags for social sharing |

### Pitch/Documentation Inconsistencies

| # | Severity | Issue |
|---|----------|-------|
| 21 | **HIGH** | Pitch deck, demo script, and video storyboard all reference a game client (Unity/Godot) that does not exist |
| 22 | **HIGH** | Tech stack claims Node.js + Next.js + IPFS -- actual stack is Python/FastAPI + vanilla HTML |
| 23 | **HIGH** | Demo script prerequisites require "game client running" -- impossible to perform |
| 24 | **MEDIUM** | Claims "3 smart contracts" but there is 1 monolithic contract |
| 25 | **MEDIUM** | Investor brief Year 3 math does not add up (-$500K stated vs. +$2.64M calculated) |

---

## 11. RECOMMENDATIONS

### P0 -- Must Fix Before Submission (Next 48 Hours)

**1. Fix the health endpoint data mapping on the landing page.**
Change the landing page JavaScript to read `data.counts?.players` instead of `data.player_count || data.players || data.total_players`. Otherwise judges see "0 Jugadores" on the landing page, which looks broken.

**2. Rewrite the demo script to match the actual product.**
The current demo script is for a game that does not exist. Create a new script that demonstrates:
- Landing page (scroll through, show design quality)
- Registration from landing page
- App: home tab showing player card, XP, streak
- App: take a quiz (show AI-generated questions, answer, get results)
- App: chat with an NPC (show Claude responding in character)
- App: leaderboard showing rankings
- Briefly show the Move contract code (highlight token, quests, badges)
- Close with the pitch

**3. Update pitch deck tech stack slide.**
Replace Node.js/Next.js/Unity/IPFS with:
- Backend: Python / FastAPI
- Frontend: Responsive Web App (HTML/CSS/JS)
- AI: Claude API (Anthropic)
- Blockchain: OneChain (Move)

Or alternatively, do not show the tech stack slide in the demo video and focus on the product.

**4. Add authentication to `/challenges/generate` and `/quests` POST.**
These are the most dangerous unprotected endpoints. Add `Depends(_get_current_wallet)` to `/challenges/generate` and create a simple admin check for `/quests` POST (e.g., check wallet against a configured admin address).

**5. Record the demo video.**
Use the rewritten demo script. 3 minutes max. Screen recording of the actual app. Focus on the working features, not the vision.

**6. Render the staking section in profile.**
Add JavaScript to populate `#stake-card` with either an active stake display or a "Stake LDX" form. Even a simple display is better than an empty div.

### P1 -- Should Fix If Time Permits

**8. Deploy the smart contract to OneChain testnet.**
Run `deploy.sh` or do it manually. Get a testnet address. Update the README links. Having a real explorer link dramatically increases credibility.

**9. Escape usernames in leaderboard and home tab rendering.**
Change `innerHTML` template literals to use a helper function that escapes HTML entities for username display.

**10. Fetch chat history from server when opening NPC chat.**
Call `/npc/chat-history` (if endpoint exists, or create one) when `openChat()` is called, so chat persists across page refreshes.

**11. Add quiz answer feedback.**
After the user selects an answer and clicks "Siguiente," show whether they got it right/wrong before moving to the next question. The server stores `correct_index` in the quest questions -- you could send it to the client after answer submission, or do a per-question check endpoint.

**12. Fix the "Ver Demo" button.**
Either link it to a demo video URL or remove it. A dead button in the hero is worse than no button.

### P2 -- Nice to Have

**13. Add rate limiting** to `/npc/chat` and `/challenges/generate` (e.g., 20 requests/minute per user).

**14. Clean up `requirements.txt`** -- remove redis, celery, apscheduler, alembic, asyncpg, prometheus-client. Keeps the dependency list honest.

**15. Add a "connecting" spinner** on app load when backend is unreachable, with a "Server unavailable" message after 5 seconds.

**16. Add favicon and OG meta tags** to both HTML files.

**17. Fix accent marks** in Spanish text (educación, jóvenes, años, interés) -- or commit to unaccented style consistently.

---

## 12. OVERALL SCORE & VERDICT

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Product Completeness | 7.0 | 15% | 1.05 |
| Code Quality | 7.5 | 10% | 0.75 |
| Landing Page | 8.5 | 10% | 0.85 |
| Game App | 7.0 | 15% | 1.05 |
| Backend Robustness | 7.5 | 15% | 1.13 |
| Smart Contract | 8.0 | 10% | 0.80 |
| Pitch & Submission | 7.5 | 10% | 0.75 |
| Hackathon Fit | 6.5 | 10% | 0.65 |
| Investor Readiness | 8.0 | 5% | 0.40 |
| **OVERALL** | | | **7.43 / 10** |

### Score: 74 / 100

### Verdict: **NEEDS WORK -- But Salvageable in 48 Hours**

### What Changed Since V1

| V1 Issue | Status | Impact |
|----------|--------|--------|
| No persistence (in-memory data) | **FIXED** (SQLite) | +1.0 to backend score |
| No authentication | **FIXED** (JWT) | +0.5 to code quality |
| No playable demo | **FIXED** (app.html with quests, chat, leaderboard) | +2.0 to hackathon fit |
| TokenCaps bug in contract | **FIXED** (coin::initialize stores caps) | +0.5 to contract score |
| No frontend-backend connection | **FIXED** (registration, quests, NPC chat, leaderboard) | +1.5 to product completeness |
| Tech stack mismatches in pitch | **NOT FIXED** | -1.5 to pitch score |
| No on-chain deployment | **NOT FIXED** | -1.0 to hackathon fit |
| Backend-chain disconnected | **NOT FIXED** | -1.0 to hackathon fit |
| Pause mechanism not enforced | **PARTIALLY FIXED** (checked in some functions) | Minimal impact |

### Probability of Winning

- **If submitted as-is:** 10-15%. The app works but the pitch materials do not match reality, there is no demo video, and the blockchain integration is code-only.
- **If P0 fixes are applied:** 25-35%. A working demo video showing the actual app, with corrected pitch materials, would make this a strong contender. The landing page is premium, the AI NPC experience is genuine, and the backend is solid.
- **If P0 + P1 fixes are applied:** 35-50%. A deployed contract + working demo + honest pitch materials would place this in the top tier. The combination of AI + GameFi + LATAM focus + premium landing page + functional app is compelling.

### The Honest Assessment

The team has done extraordinary work in 24 hours. Going from "landing page + backend + contract" to "landing page + functional 5-tab app + backend with SQLite + JWT + contract" is impressive. The app genuinely works -- you can register, take quizzes, chat with AI NPCs, and see your rank.

But the project is undermined by two things:

1. **The pitch promises a game. The product is a quiz platform.** This is not a criticism of the product -- the product is good. But the pitch deck says "RPG city with districts" and "Unity/Godot game client" and "walk through neighborhoods." The reality is a mobile-first web app with quizzes and chat. Either rebuild the pitch to match the product (which is strong on its own) or build enough game-like elements (narrative quest chains, visual progression, world map navigation) to bridge the gap. The former is faster and more honest.

2. **No blockchain transactions happen.** For OneHack 3.0 on OneChain, this is a problem. The Move contract is impressive code but it is not deployed and the app never touches the chain. Even one on-chain transaction (player registration, credential minting) would dramatically improve the submission.

**Bottom line:** Fix the P0s, especially the demo script and pitch alignment, and this project is a serious contender. The vision is right, the backend is solid, the landing page is beautiful, and the app works. The team just needs to close the gap between what they claim and what exists.

---

*Report generated 2026-03-24. All scores reflect the state of the codebase at time of audit. Comparison baseline is AUDIT_REPORT.md (V1) dated 2026-03-23.*
