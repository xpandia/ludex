#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Ludex Game — OneChain Testnet Deploy Script
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# Configuration
ONECHAIN_RPC="https://rpc.testnet.onechain.xyz/v1"
ONECHAIN_FAUCET="https://faucet.testnet.onechain.xyz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_NAME="ludex-testnet"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── Step 0: Check prerequisites ─────────────────────────────
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v aptos &> /dev/null; then
        log_err "Aptos CLI not found. Install it with:"
        echo "  curl -fsSL https://aptos.dev/scripts/install_cli.py | python3"
        echo "  -- or --"
        echo "  brew install aptos"
        exit 1
    fi
    log_ok "Aptos CLI found: $(aptos --version)"

    if ! command -v jq &> /dev/null; then
        log_warn "jq not found. Install it for JSON parsing (optional but recommended)."
        log_warn "  brew install jq  OR  apt-get install jq"
    fi
}

# ─── Step 1: Initialize account / profile ─────────────────────
init_account() {
    log_info "Initializing Aptos profile '${PROFILE_NAME}'..."

    if aptos config show-profiles 2>/dev/null | grep -q "${PROFILE_NAME}"; then
        log_warn "Profile '${PROFILE_NAME}' already exists. Using existing profile."
    else
        aptos init \
            --profile "${PROFILE_NAME}" \
            --rest-url "${ONECHAIN_RPC}" \
            --faucet-url "${ONECHAIN_FAUCET}" \
            --assume-yes
        log_ok "Profile created."
    fi

    # Extract the account address
    ACCOUNT_ADDR=$(aptos config show-profiles --profile "${PROFILE_NAME}" 2>/dev/null \
        | grep "account" | head -1 | awk -F'"' '{print $4}' || true)

    if [ -z "${ACCOUNT_ADDR}" ]; then
        log_warn "Could not parse account address from profile. Trying alternate method..."
        ACCOUNT_ADDR=$(aptos account lookup-address --profile "${PROFILE_NAME}" 2>/dev/null \
            | grep "Result" -A1 | tail -1 | tr -d ' "' || true)
    fi

    if [ -z "${ACCOUNT_ADDR}" ]; then
        log_err "Failed to determine account address. Run 'aptos init' manually."
        exit 1
    fi

    log_ok "Account address: ${ACCOUNT_ADDR}"
}

# ─── Step 2: Fund the account ─────────────────────────────────
fund_account() {
    log_info "Funding account from testnet faucet..."

    aptos account fund-with-faucet \
        --profile "${PROFILE_NAME}" \
        --faucet-url "${ONECHAIN_FAUCET}" \
        --amount 100000000 \
        2>/dev/null || {
            log_warn "Faucet funding failed (may not be available). Checking balance..."
        }

    log_info "Checking account balance..."
    aptos account balance --profile "${PROFILE_NAME}" 2>/dev/null || true
    log_ok "Account funded."
}

# ─── Step 3: Compile ──────────────────────────────────────────
compile_contract() {
    log_info "Compiling Move module..."

    cd "${SCRIPT_DIR}"
    aptos move compile \
        --named-addresses "ludex=${ACCOUNT_ADDR}" \
        --skip-fetch-latest-git-deps \
        2>&1

    if [ $? -eq 0 ]; then
        log_ok "Compilation successful."
    else
        log_err "Compilation failed. Check the errors above."
        exit 1
    fi
}

# ─── Step 4: Deploy (Publish) ─────────────────────────────────
deploy_contract() {
    log_info "Publishing module to OneChain testnet..."

    cd "${SCRIPT_DIR}"
    aptos move publish \
        --profile "${PROFILE_NAME}" \
        --named-addresses "ludex=${ACCOUNT_ADDR}" \
        --assume-yes \
        2>&1

    if [ $? -eq 0 ]; then
        log_ok "Module published successfully."
    else
        log_err "Publish failed. Check the errors above."
        exit 1
    fi
}

# ─── Step 5: Initialize the game ──────────────────────────────
initialize_game() {
    log_info "Calling initialize() to bootstrap the game..."

    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::initialize" \
        --assume-yes \
        2>&1

    if [ $? -eq 0 ]; then
        log_ok "Game initialized."
    else
        log_err "Initialization failed. The function may have already been called."
        exit 1
    fi
}

# ─── Step 6: Seed sample quests ───────────────────────────────
seed_quests() {
    log_info "Creating sample quests..."

    # Quest 1: Budgeting Basics
    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::create_quest" \
        --args \
            "address:${ACCOUNT_ADDR}" \
            "hex:4275646765742042617369637320313031" \
            "hex:4c6561726e20686f7720746f206372656174652061206d6f6e74686c7920627564676574" \
            "u8:0" "u8:0" "u64:100" "u64:10000000" "u64:1" "u64:0" "bool:false" "bool:false" \
        --assume-yes 2>&1 || log_warn "Quest 1 creation may have failed."
    log_ok "Quest 1: Budget Basics 101"

    # Quest 2: Investing Intro
    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::create_quest" \
        --args \
            "address:${ACCOUNT_ADDR}" \
            "hex:496e74726f20746f20496e76657374696e67" \
            "hex:556e6465727374616e6420776861742073746f636b7320616e6420626f6e647320617265" \
            "u8:1" "u8:1" "u64:200" "u64:20000000" "u64:1" "u64:0" "bool:false" "bool:false" \
        --assume-yes 2>&1 || log_warn "Quest 2 creation may have failed."
    log_ok "Quest 2: Intro to Investing"

    # Quest 3: Daily Savings Challenge
    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::create_quest" \
        --args \
            "address:${ACCOUNT_ADDR}" \
            "hex:4461696c79205361766572" \
            "hex:5361766520612070657263656e74616765206f6620796f757220696e636f6d6520746f646179" \
            "u8:2" "u8:0" "u64:50" "u64:5000000" "u64:1" "u64:0" "bool:true" "bool:false" \
        --assume-yes 2>&1 || log_warn "Quest 3 creation may have failed."
    log_ok "Quest 3: Daily Saver"

    # Quest 4: Crypto Fundamentals (team quest)
    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::create_quest" \
        --args \
            "address:${ACCOUNT_ADDR}" \
            "hex:43727970746f2046756e64616d656e74616c73" \
            "hex:4c6561726e2061626f757420626c6f636b636861696e20616e642063727970746f637572726e63696573" \
            "u8:4" "u8:2" "u64:300" "u64:30000000" "u64:3" "u64:0" "bool:false" "bool:true" \
        --assume-yes 2>&1 || log_warn "Quest 4 creation may have failed."
    log_ok "Quest 4: Crypto Fundamentals (team)"

    # Quest 5: Tax Season Prep
    aptos move run \
        --profile "${PROFILE_NAME}" \
        --function-id "${ACCOUNT_ADDR}::ludex_game::create_quest" \
        --args \
            "address:${ACCOUNT_ADDR}" \
            "hex:54617820536561736f6e2050726570" \
            "hex:556e6465727374616e642074617820627261636b65747320616e64206465647563696f6e73" \
            "u8:5" "u8:3" "u64:500" "u64:50000000" "u64:5" "u64:0" "bool:false" "bool:false" \
        --assume-yes 2>&1 || log_warn "Quest 5 creation may have failed."
    log_ok "Quest 5: Tax Season Prep"
}

# ─── Step 7: Print summary ────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Ludex Game — Deployment Complete${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Network:          OneChain Testnet"
    echo -e "  RPC URL:          ${ONECHAIN_RPC}"
    echo -e "  Contract Address: ${CYAN}${ACCOUNT_ADDR}${NC}"
    echo -e "  Module:           ${ACCOUNT_ADDR}::ludex_game"
    echo -e "  Profile:          ${PROFILE_NAME}"
    echo ""
    echo -e "  ${YELLOW}Sample Quests Created:${NC}"
    echo -e "    1. Budget Basics 101       (Budgeting, Easy)"
    echo -e "    2. Intro to Investing      (Investing, Medium)"
    echo -e "    3. Daily Saver             (Saving, Easy, Daily)"
    echo -e "    4. Crypto Fundamentals     (Crypto, Hard, Team)"
    echo -e "    5. Tax Season Prep         (Taxes, Expert)"
    echo ""
    echo -e "  ${YELLOW}Next steps:${NC}"
    echo -e "    - Register a player:  aptos move run --profile ${PROFILE_NAME} \\"
    echo -e "        --function-id ${ACCOUNT_ADDR}::ludex_game::register_player \\"
    echo -e "        --args 'hex:506c6179657231' 'address:${ACCOUNT_ADDR}'"
    echo -e ""
    echo -e "    - View profile:       aptos move view --profile ${PROFILE_NAME} \\"
    echo -e "        --function-id ${ACCOUNT_ADDR}::ludex_game::get_player_profile \\"
    echo -e "        --args 'address:<PLAYER_ADDR>'"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
}

# ─── Main ─────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Ludex Game — OneChain Testnet Deployer         ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    check_prerequisites
    init_account
    fund_account
    compile_contract
    deploy_contract
    initialize_game
    seed_quests
    print_summary
}

main "$@"
