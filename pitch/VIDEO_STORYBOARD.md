# LUDEX -- Video Storyboard
### 60-90 Second Pitch Video
#### OneHack 3.0 | AI & GameFi Edition

---

## Video Specs

- **Duration:** 75 seconds (target sweet spot)
- **Aspect Ratio:** 16:9
- **Resolution:** 1080p minimum
- **Audio:** Voiceover + subtle ambient music (lo-fi or cinematic synth -- NOT stock corporate)
- **Tone:** Urgent, warm, inevitable. This is not a startup pitch. This is a movement announcing itself.

---

## SCENE 1 -- THE STAT [0:00 - 0:10]

**Visual:** Black screen. White text fades in, one line at a time. Typewriter or clean sans-serif.

```
200 million young people in Latin America
have no financial education.
```

*Beat.*

```
But they spend 3 hours a day gaming.
```

**Audio:** Silence. Then a single, low tone -- building tension.

**Voiceover:** None. Let the text land.

---

## SCENE 2 -- THE QUESTION [0:10 - 0:17]

**Visual:** Text fades out. New text:

```
What if the game WAS the education?
```

*Hold for 2 seconds. Then the Ludex logo appears -- clean, centered.*

```
LUDEX
Aprende jugando. Gana viviendo.
```

**Audio:** Logo hit -- subtle, satisfying sound. Music begins softly (ambient, building).

**Voiceover:** *"This is Ludex."*

---

## SCENE 3 -- THE APP [0:17 - 0:35]

**Visual:** Screen recording of the actual Ludex app. Quick cuts through real screens:

1. **Landing page hero** (2 sec) -- particles, custom cursor, phone mockup with animated XP bar and quest card. Scroll briefly to show NPC avatars and curriculum tabs.
2. **App Home tab** (3 sec) -- player card with avatar, level badge, animated XP bar, streak counter. Category grid with 6 financial topics visible.
3. **Quest list** (2 sec) -- quest cards with colored category borders, star difficulty, XP/token rewards displayed.
4. **Quiz in progress** (5 sec) -- AI-generated multiple-choice question on screen, progress bar at top, player selecting an answer, clicking "Siguiente".
5. **Quiz results** (3 sec) -- pass screen with confetti animation, XP earned, tokens rewarded.
6. **NPC chat** (3 sec) -- Professor Luna chat screen, typing indicator, AI response appearing with educational content about budgeting. Subtle "Powered by Claude" visible.

**Text overlays** (lower third, clean):
- "AI-generated quizzes tailored to your level"
- "4 AI mentors powered by Claude"

**Voiceover:**
*"An interactive financial education platform with AI-powered quests and mentors. Claude generates personalized challenges. Four AI NPCs coach you through budgeting, investing, crypto, and credit -- adapting to your knowledge in real time."*

---

## SCENE 4 -- THE EARN [0:35 - 0:50]

**Visual:** Quick sequence from the actual app:

1. **Badge earned notification** (3 sec) -- toast notification sliding in after quest completion, badge with glow animation in profile
2. **Leaderboard** (3 sec) -- podium with gold/silver/bronze, ranked list, "TU" badge next to current player, multiple players visible
3. **Profile page** (3 sec) -- stats grid (quests completed, badges, streak), curriculum progress bars across 6 categories
4. **Move contract code** (3 sec) -- quick scroll through `ludex_game.move` in an editor, highlighting LDX token, badge system, staking section
5. **Staking concept** (3 sec) -- show the profile staking section and overlay text explaining graduated multipliers

**Text overlays:**
- "Badges as soulbound credentials on OneChain"
- "LDX tokens -- earn, stake, grow"
- "Leaderboard with seasonal rewards"

**Voiceover:**
*"Every achievement earns XP, tokens, and badges -- designed to be minted on OneChain as verifiable credentials. Schools, employers, governments can confirm what you know. Stake your tokens for reward multipliers. Climb the leaderboard. Your financial literacy, proven on-chain."*

---

## SCENE 5 -- THE TECH [0:50 - 0:60]

**Visual:** Clean architecture diagram animating in -- stylized, on-brand:

```
Player (Browser) --> Web App (HTML/CSS/JS)
                          |
                   FastAPI Backend (Python)  <-->  Claude API (AI NPCs)
                          |
                   OneChain (Move Contract)
                     ludex_game.move
        LDX Token | Quests | Badges | Staking | Leaderboard
```

Each layer lights up as the voiceover mentions it. Fast. Confident. No lingering.

**Text overlay:** "Built on OneChain. Powered by Claude."

**Voiceover:**
*"Built on OneChain with a comprehensive Move smart contract -- 878 lines covering tokens, quests, badges, staking, and leaderboard. Python/FastAPI backend with 21 endpoints and JWT authentication. AI NPCs and challenge generation powered by Claude."*

---

## SCENE 6 -- THE CLOSE [0:60 - 0:75]

**Visual:** Return to the landing page hero section. Slow scroll up to the tagline. The phone mockup animates with the XP bar filling up.

*Fade to black.*

Ludex logo, centered.

```
LUDEX
Aprende jugando. Gana viviendo.

Play to learn. Earn to grow.
```

Below the logo:

```
OneHack 3.0 | AI & GameFi Edition
```

**Voiceover:**
*"200 million young people deserve better than a textbook. They deserve a world where learning feels like playing and progress pays real dividends. Ludex. Aprende jugando. Gana viviendo."*

**Audio:** Music peaks and resolves. Clean ending. No fade-out -- a definitive stop.

---

## Production Notes

### Music
- Use royalty-free lo-fi or cinematic synth. Avoid anything generic-corporate. The mood is: *determined optimism*.
- Recommended sources: Epidemic Sound, Artlist, or original composition if time permits.

### Voiceover
- One voice. Calm, clear, confident. Native Spanish speaker doing English VO is fine -- the accent adds authenticity for LATAM story.
- Record in a quiet room. Phone voice memos work if the room is dead silent.

### Footage
- All footage is screen recordings of the actual running app at 60fps.
- Landing page: record `index.html` served locally with backend running (for live leaderboard data).
- Game app: record `app.html` -- walk through Home, Quests, NPC chat, Leaderboard, Profile tabs.
- Smart contract: screen-record scrolling through `ludex_game.move` in VS Code or similar editor.
- The closing shot can use the landing page hero section or a simple title card.

### Editing
- Cut tight. No shot longer than 5 seconds. The rhythm should feel like a trailer, not a tutorial.
- Text overlays: use the project's brand font. White on dark, or dark on light game backgrounds. Always readable.
- No transitions except hard cuts and simple fades. No zooms, spins, or slide-ins.

### Timing Breakdown

| Scene | Duration | Running Total |
|---|---|---|
| 1 - The Stat | 10s | 0:10 |
| 2 - The Question | 7s | 0:17 |
| 3 - The App | 18s | 0:35 |
| 4 - The Earn | 15s | 0:50 |
| 5 - The Tech | 10s | 1:00 |
| 6 - The Close | 15s | 1:15 |

**Total: ~75 seconds** (within 60-90s window, with room to breathe)
