# LUDEX — Demo Script
### 3-Minute Live Demo
#### OneHack 3.0 | AI & GameFi Edition

---

## Before You Begin

- Have the game client running, player already in the Ludex city overview
- Have the Next.js dashboard open in a second tab (leaderboard visible)
- Have the OneChain explorer open in a third tab
- Wallet connected, zero credentials minted
- Practice the AI NPC conversation at least twice — know where it leads

**Tone:** Confident. Conversational. Like showing a friend something incredible you built last night.

---

## [0:00 - 0:30] THE HOOK

> *Start on the Ludex landing page.*

"Let me show you something.

Right now, 200 million young people in Latin America cannot answer a basic question about compound interest. They have never been taught. And the tools that exist? Textbooks. PDFs. Forty-minute lectures.

Nobody finishes those.

But you know what they do finish? Games. Raids. Quests. Leaderboards.

So we asked a simple question: what if the game *was* the education?

This is Ludex."

> *Click 'Enter World'. The RPG city loads.*

---

## [0:30 - 1:15] THE WORLD

> *Camera shows the Ludex city overview — districts visible.*

"This is the Ludex city. Every district is a financial domain. Market District — that is supply and demand. Bank of Ludex — compound interest and savings. Insurance Guild — risk management. Portfolio Arena — diversification.

You do not pick a textbook chapter. You walk into a neighborhood."

> *Navigate to the Market District. Walk toward an AI NPC merchant.*

"Let me show you how learning actually happens here. I am going to talk to this merchant. She is powered by Claude — Anthropic's AI. She is not reading from a script. She adapts to my level."

> *Click on the NPC. The dialogue opens.*

**NPC (AI):** *"Welcome back, traveler. I have 50 units of Starfruit, and the festival is in three days. Half the city wants them. What would you offer me per unit?"*

> *Type a response or select an option. Show the negotiation in real-time.*

"See what just happened? That is a supply and demand lesson. But I did not read about it. I just negotiated it. The AI tracks my answers, adjusts difficulty, and gives me feedback in-story — not in a popup."

> *Show the AI giving contextual feedback within the dialogue.*

**NPC (AI):** *"Smart offer. You read the scarcity right. But remember — if the festival gets canceled, those Starfruit are worth nothing. That is called demand risk. Ready for the next deal?"*

"Every conversation is personalized. Every quest builds on the last."

---

## [1:15 - 2:00] THE EARN — ON-CHAIN

> *Complete the quest. A success animation plays.*

"Quest complete. Now watch what happens."

> *A credential minting transaction fires. Show the notification in the game.*

"That achievement just minted as a soulbound credential on OneChain. Let me show you."

> *Switch to the OneChain explorer tab. Show the transaction.*

"There it is. On-chain. Verifiable. Nobody can take it from you. No institution can gatekeep it. A school, an employer, a government — anyone can verify that this player understands supply and demand fundamentals."

> *Switch to the Next.js dashboard. Show the leaderboard updating.*

"And the leaderboard updates. Top players this season earn token rewards from the community treasury — our RewardPool smart contract distributes automatically based on verified milestones. No middleman."

> *Show the player's profile: credentials earned, progress across districts, ranking.*

"This is the player dashboard. Every district. Every quest. Every credential. A full financial literacy portfolio — built by playing."

---

## [2:00 - 2:40] THE TECH

> *Brief architecture walkthrough — keep it fast, keep it visual.*

"Under the hood, three smart contracts on OneChain, written in Move:

**RewardPool** — the treasury. Distributes tokens when milestones are verified.
**Leaderboard** — on-chain rankings, seasonal resets, reward tiers.
**Credential** — soulbound tokens. Your proof of learning. Non-transferable, permanently yours.

The AI NPCs run on Claude API. Every conversation adapts in real-time. The game client talks to our Node.js backend, which orchestrates state between the game, the AI, and the chain.

This is not a mockup. This is deployed. This is live. This is working."

---

## [2:40 - 3:00] THE CLOSE

> *Return to the Ludex city overview. Pause.*

"We are not building another EdTech app that nobody opens. We are not building another GameFi project that nobody cares about in three months.

We are building the world where 200 million young people finally learn the one subject no one taught them — by doing the one thing they already love.

Ludex. Aprende jugando. Gana viviendo.

Thank you."

> *Hold the frame. City alive in the background. Silence.*

---

## Post-Demo Notes

- If judges ask about tokenomics: emphasize soulbound credentials (non-speculative), reward pool funded by in-game economy, and B2B license revenue
- If judges ask about AI safety: Claude's constitutional AI ensures NPC conversations stay educational, age-appropriate, and financially accurate
- If judges ask about scalability: Move on OneChain handles high-throughput credential minting; game client is lightweight 2.5D; AI calls are async with caching for common dialogue paths
- If they ask "why LATAM?": because that is where the pain is sharpest, smartphone penetration is high, gaming culture is massive, and nobody is serving this market with anything that works
