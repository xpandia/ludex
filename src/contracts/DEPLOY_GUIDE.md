# Ludex Game — OneChain Testnet Deployment Guide

Deploy the Ludex play-to-learn GameFi smart contract on OneChain testnet in 5 minutes.

---

## Prerequisites

| Tool | Install |
|------|---------|
| **Aptos CLI** (v2.0+) | `curl -fsSL https://aptos.dev/scripts/install_cli.py \| python3` or `brew install aptos` |
| **Git** | Required to fetch Move framework dependencies |
| **jq** (optional) | `brew install jq` — for parsing JSON responses |

Verify installation:

```bash
aptos --version
# aptos-cli 2.x.x
```

---

## Network Details

| Parameter | Value |
|-----------|-------|
| **Network** | OneChain Testnet |
| **RPC URL** | `https://rpc.testnet.onechain.xyz/v1` |
| **Faucet** | `https://faucet.testnet.onechain.xyz` |
| **Explorer** | `https://explorer.testnet.onechain.xyz` |
| **Chain ID** | Check with `curl https://rpc.testnet.onechain.xyz/v1 -s \| jq .chain_id` |

---

## Option A: Automated Deploy (Recommended)

```bash
cd src/contracts
chmod +x deploy.sh
./deploy.sh
```

The script handles everything: account creation, funding, compilation, deployment, initialization, and seeding sample quests. Skip to **Step 7** to verify.

---

## Option B: Manual Step-by-Step

### Step 1: Create and Fund a Testnet Wallet

```bash
# Initialize a new profile pointing at OneChain testnet
aptos init \
  --profile ludex-testnet \
  --rest-url https://rpc.testnet.onechain.xyz/v1 \
  --faucet-url https://faucet.testnet.onechain.xyz \
  --assume-yes
```

This generates a new keypair and saves it locally. Note the **account address** printed.

```bash
# Fund the account with testnet tokens
aptos account fund-with-faucet \
  --profile ludex-testnet \
  --faucet-url https://faucet.testnet.onechain.xyz \
  --amount 100000000
```

```bash
# Verify the balance
aptos account balance --profile ludex-testnet
```

### Step 2: Compile the Move Module

```bash
cd src/contracts

# Replace <YOUR_ADDRESS> with the address from Step 1
aptos move compile \
  --named-addresses ludex=<YOUR_ADDRESS>
```

Expected output: `{ "Result": ["<YOUR_ADDRESS>::ludex_game"] }`

### Step 3: Deploy to Testnet

```bash
aptos move publish \
  --profile ludex-testnet \
  --named-addresses ludex=<YOUR_ADDRESS> \
  --assume-yes
```

The CLI will show the transaction hash. Wait for confirmation.

### Step 4: Initialize the Game

This must be called **once** by the deployer address. It bootstraps the LDX token, quest registry, badge registry, leaderboard, and team registry.

```bash
aptos move run \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::initialize \
  --assume-yes
```

### Step 5: Create Sample Quests

```bash
# Quest 1: Budget Basics 101 (Budgeting, Easy, 100 XP, 10 LDX)
aptos move run \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::create_quest \
  --args \
    "address:<YOUR_ADDRESS>" \
    "hex:4275646765742042617369637320313031" \
    "hex:4c6561726e20686f7720746f206372656174652061206d6f6e74686c7920627564676574" \
    "u8:0" "u8:0" "u64:100" "u64:10000000" "u64:1" "u64:0" "bool:false" "bool:false" \
  --assume-yes

# Quest 2: Intro to Investing (Investing, Medium, 200 XP, 20 LDX)
aptos move run \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::create_quest \
  --args \
    "address:<YOUR_ADDRESS>" \
    "hex:496e74726f20746f20496e76657374696e67" \
    "hex:556e6465727374616e6420776861742073746f636b7320616e6420626f6e647320617265" \
    "u8:1" "u8:1" "u64:200" "u64:20000000" "u64:1" "u64:0" "bool:false" "bool:false" \
  --assume-yes

# Quest 3: Daily Saver (Saving, Easy, Daily, 50 XP, 5 LDX)
aptos move run \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::create_quest \
  --args \
    "address:<YOUR_ADDRESS>" \
    "hex:4461696c79205361766572" \
    "hex:5361766520612070657263656e74616765206f6620796f757220696e636f6d6520746f646179" \
    "u8:2" "u8:0" "u64:50" "u64:5000000" "u64:1" "u64:0" "bool:true" "bool:false" \
  --assume-yes
```

### Step 6: Register a Test Player

```bash
aptos move run \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::register_player \
  --args \
    "hex:546573745f506c61796572" \
    "address:<YOUR_ADDRESS>" \
  --assume-yes
```

### Step 7: Verify Deployment

```bash
# Check game stats (total_players, total_quests_completed, total_tokens_distributed)
aptos move view \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::get_game_stats \
  --args "address:<YOUR_ADDRESS>"

# Check player profile
aptos move view \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::get_player_profile \
  --args "address:<YOUR_ADDRESS>"

# Check a quest
aptos move view \
  --profile ludex-testnet \
  --function-id <YOUR_ADDRESS>::ludex_game::get_quest \
  --args "address:<YOUR_ADDRESS>" "u64:1"
```

You can also view transactions on the OneChain explorer:
```
https://explorer.testnet.onechain.xyz/account/<YOUR_ADDRESS>/modules
```

---

## Troubleshooting

### "EMODULE_NOT_FOUND" or compilation fails with dependency errors

The Move.toml references the AOneChain git repo for framework dependencies. If OneChain uses a different repo URL:

```toml
# In Move.toml, update the git URL to match the actual OneChain repo:
[dependencies.AptosFramework]
git = "https://github.com/aptos-labs/aptos-core.git"
rev = "mainnet"
subdir = "aptos-move/framework/aptos-framework"
```

### "ALREADY_EXISTS" when calling initialize()

The `initialize` function can only be called once. If you see this error, the game is already initialized. Move on to creating quests.

### "E_NOT_ADMIN" (error code 1)

You must call admin functions (create_quest, complete_quest, etc.) from the **same account** that called `initialize`. Make sure `--profile` matches your deployer profile.

### "INSUFFICIENT_BALANCE" when funding

The testnet faucet may have rate limits. Wait a few minutes and try again, or use a smaller amount:
```bash
aptos account fund-with-faucet --profile ludex-testnet \
  --faucet-url https://faucet.testnet.onechain.xyz --amount 10000000
```

### Module compilation error: "unbound module 'aptos_framework::X'"

Ensure the `AptosFramework` dependency is pointing to a valid revision. Try changing `rev` in Move.toml:
```toml
rev = "main"     # latest
# or
rev = "testnet"  # testnet-compatible
```

### "SEQUENCE_NUMBER_TOO_OLD"

This means a transaction was submitted too quickly after a previous one. Wait a few seconds and retry.

### RPC connection errors

Verify the RPC endpoint is reachable:
```bash
curl -s https://rpc.testnet.onechain.xyz/v1 | jq .
```

If the default endpoint is down, check OneChain docs for alternative RPC URLs.

---

## Quick Reference: Entry Functions

| Function | Who | Description |
|----------|-----|-------------|
| `initialize` | Admin (once) | Bootstrap game, LDX token, registries |
| `register_player` | Player | Create player profile |
| `create_quest` | Admin | Add a new quest |
| `complete_quest` | Admin/Oracle | Mark quest done, award XP + LDX |
| `create_badge_template` | Admin | Define a new badge type |
| `award_badge` | Admin/Oracle | Give badge to player |
| `stake_tokens` | Player | Lock LDX for multiplier |
| `unstake_tokens` | Admin | Return staked LDX + reward |
| `create_team` | Player | Start a new team |
| `join_team` | Player | Join existing team |
| `add_friend` | Player | Add friend connection |
| `update_leaderboard` | Anyone | Refresh player's leaderboard rank |
| `new_season` | Admin | Reset leaderboard for new season |
| `set_paused` | Admin | Pause/unpause the game |

## Quick Reference: View Functions

| Function | Returns |
|----------|---------|
| `get_player_profile` | Full player profile struct |
| `get_player_level` | Player's current level |
| `get_player_xp` | Player's current XP |
| `get_xp_to_next_level` | XP needed for next level |
| `get_player_badges` | List of earned badges |
| `get_player_streak` | Current daily streak count |
| `get_quest` | Quest details by ID |
| `get_stake_info` | Player's staking info |
| `get_game_stats` | (total_players, total_quests, total_tokens) |
