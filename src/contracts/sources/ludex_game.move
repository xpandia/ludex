/// Ludex — Play-to-Learn GameFi for Financial Literacy
/// OneHack 3.0 | AI & GameFi Edition
///
/// This module implements the on-chain game logic: player profiles, XP/leveling,
/// LDX token rewards, NFT achievement badges, leaderboards, quests, and staking.
module ludex::ludex_game {

    // ──────────────────────────────────────────────
    //  Imports
    // ──────────────────────────────────────────────
    use std::string::{Self, String};
    use std::signer;
    use std::vector;
    use std::option::{Self, Option};
    use aptos_framework::timestamp;

    use aptos_framework::coin::{Self, MintCapability, BurnCapability, FreezeCapability};
    use aptos_framework::account;
    use aptos_framework::event::{Self, EventHandle};
    use aptos_framework::table::{Self, Table};
    use aptos_framework::managed_coin; // used for register<LudexToken>

    // ──────────────────────────────────────────────
    //  Error codes
    // ──────────────────────────────────────────────
    const E_NOT_ADMIN: u64                = 1;
    const E_ALREADY_REGISTERED: u64       = 2;
    const E_NOT_REGISTERED: u64           = 3;
    const E_INSUFFICIENT_XP: u64          = 4;
    const E_QUEST_NOT_FOUND: u64          = 5;
    const E_QUEST_ALREADY_COMPLETE: u64   = 6;
    const E_INSUFFICIENT_BALANCE: u64     = 7;
    const E_STAKE_LOCKED: u64             = 8;
    const E_INVALID_AMOUNT: u64           = 9;
    const E_BADGE_ALREADY_CLAIMED: u64    = 10;
    const E_LEVEL_TOO_LOW: u64            = 11;
    const E_LEADERBOARD_FULL: u64         = 12;
    const E_QUEST_EXPIRED: u64            = 13;
    const E_TEAM_FULL: u64                = 14;
    const E_ALREADY_IN_TEAM: u64          = 15;
    const E_GAME_PAUSED: u64              = 16;

    // ──────────────────────────────────────────────
    //  Constants
    // ──────────────────────────────────────────────
    const MAX_LEVEL: u64                  = 100;
    const BASE_XP_PER_LEVEL: u64          = 100;
    const XP_SCALING_FACTOR: u64          = 15;   // +15% per level
    const LEADERBOARD_SIZE: u64           = 100;
    const MAX_TEAM_SIZE: u64              = 5;
    const STAKE_MIN_DURATION_SECS: u64    = 86400; // 24 hours
    const BASE_REWARD_PER_QUEST: u64      = 10_000_000; // 10 LDX (8 decimals)
    const STREAK_BONUS_PERCENT: u64       = 5;
    const TEAM_BONUS_PERCENT: u64         = 10;

    // ──────────────────────────────────────────────
    //  LDX Token definition
    // ──────────────────────────────────────────────
    struct LudexToken has key {}

    /// Admin-held capabilities for the LDX token.
    struct TokenCaps has key {
        mint_cap: MintCapability<LudexToken>,
        burn_cap: BurnCapability<LudexToken>,
        freeze_cap: FreezeCapability<LudexToken>,
    }

    // ──────────────────────────────────────────────
    //  Player profile
    // ──────────────────────────────────────────────
    struct PlayerProfile has key, store, copy, drop {
        addr: address,
        username: String,
        xp: u64,
        level: u64,
        total_quests_completed: u64,
        daily_streak: u64,
        longest_streak: u64,
        last_activity_ts: u64,
        registered_at: u64,
        team_id: Option<u64>,
    }

    /// Player-owned resource that stores badges and quest state.
    struct PlayerState has key {
        profile: PlayerProfile,
        badges: vector<Badge>,
        active_quests: vector<u64>,
        completed_quests: vector<u64>,
        stake: Option<StakeInfo>,
        friends: vector<address>,
        events: EventHandle<PlayerEvent>,
    }

    // ──────────────────────────────────────────────
    //  NFT Achievement Badges
    // ──────────────────────────────────────────────
    struct Badge has store, copy, drop {
        id: u64,
        name: String,
        description: String,
        category: u8,        // 0=lesson, 1=streak, 2=social, 3=staking, 4=leaderboard
        rarity: u8,          // 0=common, 1=uncommon, 2=rare, 3=epic, 4=legendary
        earned_at: u64,
        image_uri: String,
    }

    struct BadgeRegistry has key {
        templates: Table<u64, BadgeTemplate>,
        next_badge_id: u64,
    }

    struct BadgeTemplate has store, copy, drop {
        id: u64,
        name: String,
        description: String,
        category: u8,
        rarity: u8,
        required_level: u64,
        required_quests: u64,
        image_uri: String,
    }

    // ──────────────────────────────────────────────
    //  Quest / Challenge system
    // ──────────────────────────────────────────────
    struct Quest has store, copy, drop {
        id: u64,
        title: String,
        description: String,
        category: u8,        // 0=budgeting, 1=investing, 2=saving, 3=credit, 4=crypto, 5=taxes
        difficulty: u8,      // 0..4
        xp_reward: u64,
        token_reward: u64,
        required_level: u64,
        expires_at: u64,     // 0 = never
        is_daily: bool,
        is_team_quest: bool,
    }

    struct QuestRegistry has key {
        quests: Table<u64, Quest>,
        next_quest_id: u64,
    }

    // ──────────────────────────────────────────────
    //  Staking
    // ──────────────────────────────────────────────
    struct StakeInfo has store, copy, drop {
        amount: u64,
        staked_at: u64,
        unlock_at: u64,
        bonus_multiplier: u64, // basis points, e.g. 150 = 1.5x
    }

    // ──────────────────────────────────────────────
    //  Leaderboard
    // ──────────────────────────────────────────────
    struct LeaderboardEntry has store, copy, drop {
        addr: address,
        username: String,
        xp: u64,
        level: u64,
    }

    struct Leaderboard has key {
        season: u64,
        entries: vector<LeaderboardEntry>,
        season_start: u64,
        season_end: u64,
    }

    // ──────────────────────────────────────────────
    //  Teams
    // ──────────────────────────────────────────────
    struct Team has store, copy, drop {
        id: u64,
        name: String,
        leader: address,
        members: vector<address>,
        total_xp: u64,
    }

    struct TeamRegistry has key {
        teams: Table<u64, Team>,
        next_team_id: u64,
    }

    // ──────────────────────────────────────────────
    //  Events
    // ──────────────────────────────────────────────
    struct PlayerEvent has store, drop {
        event_type: u8, // 0=register, 1=level_up, 2=quest_complete, 3=badge, 4=stake, 5=unstake
        value: u64,
        timestamp: u64,
    }

    // ──────────────────────────────────────────────
    //  Global game state (admin resource)
    // ──────────────────────────────────────────────
    struct GameState has key {
        admin: address,
        total_players: u64,
        total_quests_completed: u64,
        total_tokens_distributed: u64,
        paused: bool,
    }

    // ══════════════════════════════════════════════
    //  Initialization
    // ══════════════════════════════════════════════

    /// Called once by the deployer to bootstrap the game.
    public entry fun initialize(admin: &signer) {
        let admin_addr = signer::address_of(admin);

        // Initialize the LDX token and capture capabilities.
        let (burn_cap, freeze_cap, mint_cap) = coin::initialize<LudexToken>(
            admin,
            string::utf8(b"Ludex Token"),
            string::utf8(b"LDX"),
            8,  // decimals
            true, // monitor supply
        );

        // Store token capabilities so the admin can mint/burn later.
        move_to(admin, TokenCaps {
            mint_cap,
            burn_cap,
            freeze_cap,
        });

        // Store game state.
        move_to(admin, GameState {
            admin: admin_addr,
            total_players: 0,
            total_quests_completed: 0,
            total_tokens_distributed: 0,
            paused: false,
        });

        // Quest registry.
        move_to(admin, QuestRegistry {
            quests: table::new(),
            next_quest_id: 1,
        });

        // Badge registry.
        move_to(admin, BadgeRegistry {
            templates: table::new(),
            next_badge_id: 1,
        });

        // Leaderboard.
        move_to(admin, Leaderboard {
            season: 1,
            entries: vector::empty(),
            season_start: timestamp::now_seconds(),
            season_end: timestamp::now_seconds() + 2592000, // 30 days
        });

        // Team registry.
        move_to(admin, TeamRegistry {
            teams: table::new(),
            next_team_id: 1,
        });
    }

    // ══════════════════════════════════════════════
    //  Player registration
    // ══════════════════════════════════════════════

    public entry fun register_player(
        player: &signer,
        username: vector<u8>,
        game_addr: address,
    ) acquires GameState {
        let player_addr = signer::address_of(player);
        assert!(!exists<PlayerState>(player_addr), E_ALREADY_REGISTERED);

        // Update global stats and enforce pause using a single mutable borrow.
        let game = borrow_global_mut<GameState>(game_addr);
        assert!(!game.paused, E_GAME_PAUSED);
        game.total_players = game.total_players + 1;

        let now = timestamp::now_seconds();

        let profile = PlayerProfile {
            addr: player_addr,
            username: string::utf8(username),
            xp: 0,
            level: 1,
            total_quests_completed: 0,
            daily_streak: 0,
            longest_streak: 0,
            last_activity_ts: now,
            registered_at: now,
            team_id: option::none(),
        };

        move_to(player, PlayerState {
            profile,
            badges: vector::empty(),
            active_quests: vector::empty(),
            completed_quests: vector::empty(),
            stake: option::none(),
            friends: vector::empty(),
            events: account::new_event_handle<PlayerEvent>(player),
        });

        // Register the player for LDX coin if not already.
        if (!coin::is_account_registered<LudexToken>(player_addr)) {
            managed_coin::register<LudexToken>(player);
        };
    }

    // ══════════════════════════════════════════════
    //  XP & Leveling
    // ══════════════════════════════════════════════

    /// Computes XP needed to reach the next level.
    /// Formula: BASE_XP_PER_LEVEL * level * (100 + XP_SCALING_FACTOR * level) / 100
    fun xp_for_next_level(current_level: u64): u64 {
        BASE_XP_PER_LEVEL * current_level * (100 + XP_SCALING_FACTOR * current_level) / 100
    }

    /// Awards XP and processes any resulting level-ups.
    fun award_xp(state: &mut PlayerState, amount: u64) {
        state.profile.xp = state.profile.xp + amount;

        // Process level-ups.
        while (state.profile.level < MAX_LEVEL) {
            let needed = xp_for_next_level(state.profile.level);
            if (state.profile.xp < needed) break;
            state.profile.xp = state.profile.xp - needed;
            state.profile.level = state.profile.level + 1;

            event::emit_event(&mut state.events, PlayerEvent {
                event_type: 1, // level_up
                value: state.profile.level,
                timestamp: timestamp::now_seconds(),
            });
        };
    }

    /// Updates the daily streak counter.
    fun update_streak(profile: &mut PlayerProfile) {
        let now = timestamp::now_seconds();
        let elapsed = now - profile.last_activity_ts;

        if (elapsed < 172800) { // within 48 hours
            if (elapsed >= 72000) { // at least 20 hours since last activity
                profile.daily_streak = profile.daily_streak + 1;
                if (profile.daily_streak > profile.longest_streak) {
                    profile.longest_streak = profile.daily_streak;
                };
            };
        } else {
            profile.daily_streak = 1; // reset
        };

        profile.last_activity_ts = now;
    }

    // ══════════════════════════════════════════════
    //  Quest management (admin)
    // ══════════════════════════════════════════════

    public entry fun create_quest(
        admin: &signer,
        game_addr: address,
        title: vector<u8>,
        description: vector<u8>,
        category: u8,
        difficulty: u8,
        xp_reward: u64,
        token_reward: u64,
        required_level: u64,
        expires_at: u64,
        is_daily: bool,
        is_team_quest: bool,
    ) acquires GameState, QuestRegistry {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);

        let registry = borrow_global_mut<QuestRegistry>(game_addr);
        let quest_id = registry.next_quest_id;

        let quest = Quest {
            id: quest_id,
            title: string::utf8(title),
            description: string::utf8(description),
            category,
            difficulty,
            xp_reward,
            token_reward,
            required_level,
            expires_at,
            is_daily,
            is_team_quest,
        };

        table::add(&mut registry.quests, quest_id, quest);
        registry.next_quest_id = quest_id + 1;
    }

    // ══════════════════════════════════════════════
    //  Quest completion
    // ══════════════════════════════════════════════

    /// Called by the backend oracle after verifying that the player
    /// has legitimately completed a quest (answered quiz, finished lesson, etc.).
    public entry fun complete_quest(
        admin: &signer,
        game_addr: address,
        player_addr: address,
        quest_id: u64,
    ) acquires GameState, QuestRegistry, PlayerState, TokenCaps {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global_mut<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);
        assert!(!game.paused, E_GAME_PAUSED);

        let registry = borrow_global<QuestRegistry>(game_addr);
        assert!(table::contains(&registry.quests, quest_id), E_QUEST_NOT_FOUND);
        let quest = *table::borrow(&registry.quests, quest_id);

        // Validate expiry.
        if (quest.expires_at > 0) {
            assert!(timestamp::now_seconds() <= quest.expires_at, E_QUEST_EXPIRED);
        };

        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(state.profile.level >= quest.required_level, E_LEVEL_TOO_LOW);

        // Check not already completed (for non-daily quests).
        if (!quest.is_daily) {
            let len = vector::length(&state.completed_quests);
            let i = 0;
            while (i < len) {
                assert!(*vector::borrow(&state.completed_quests, i) != quest_id, E_QUEST_ALREADY_COMPLETE);
                i = i + 1;
            };
        };

        // Calculate rewards with bonuses.
        let xp_reward = quest.xp_reward;
        let token_reward = quest.token_reward;

        // Streak bonus.
        if (state.profile.daily_streak > 0) {
            let streak_bonus = xp_reward * STREAK_BONUS_PERCENT * state.profile.daily_streak / 100;
            // Cap streak bonus at 50%.
            if (streak_bonus > xp_reward / 2) {
                streak_bonus = xp_reward / 2;
            };
            xp_reward = xp_reward + streak_bonus;
        };

        // Staking multiplier bonus.
        if (option::is_some(&state.stake)) {
            let stake_info = *option::borrow(&state.stake);
            token_reward = token_reward * stake_info.bonus_multiplier / 100;
        };

        // Award XP.
        award_xp(state, xp_reward);
        update_streak(&mut state.profile);

        // Mark completed.
        vector::push_back(&mut state.completed_quests, quest_id);
        state.profile.total_quests_completed = state.profile.total_quests_completed + 1;

        // Mint LDX reward using stored capability.
        if (token_reward > 0) {
            let caps = borrow_global<TokenCaps>(game_addr);
            let coins = coin::mint<LudexToken>(token_reward, &caps.mint_cap);
            coin::deposit(player_addr, coins);
            game.total_tokens_distributed = game.total_tokens_distributed + token_reward;
        };

        game.total_quests_completed = game.total_quests_completed + 1;

        // Emit event.
        event::emit_event(&mut state.events, PlayerEvent {
            event_type: 2,
            value: quest_id,
            timestamp: timestamp::now_seconds(),
        });
    }

    // ══════════════════════════════════════════════
    //  Badge system
    // ══════════════════════════════════════════════

    public entry fun create_badge_template(
        admin: &signer,
        game_addr: address,
        name: vector<u8>,
        description: vector<u8>,
        category: u8,
        rarity: u8,
        required_level: u64,
        required_quests: u64,
        image_uri: vector<u8>,
    ) acquires GameState, BadgeRegistry {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);

        let registry = borrow_global_mut<BadgeRegistry>(game_addr);
        let badge_id = registry.next_badge_id;

        table::add(&mut registry.templates, badge_id, BadgeTemplate {
            id: badge_id,
            name: string::utf8(name),
            description: string::utf8(description),
            category,
            rarity,
            required_level,
            required_quests,
            image_uri: string::utf8(image_uri),
        });

        registry.next_badge_id = badge_id + 1;
    }

    /// Award a badge to a player (admin/oracle call after verification).
    public entry fun award_badge(
        admin: &signer,
        game_addr: address,
        player_addr: address,
        badge_template_id: u64,
    ) acquires GameState, BadgeRegistry, PlayerState {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);

        let registry = borrow_global<BadgeRegistry>(game_addr);
        assert!(table::contains(&registry.templates, badge_template_id), E_QUEST_NOT_FOUND);
        let template = *table::borrow(&registry.templates, badge_template_id);

        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(state.profile.level >= template.required_level, E_LEVEL_TOO_LOW);
        assert!(state.profile.total_quests_completed >= template.required_quests, E_INSUFFICIENT_XP);

        // Check not already earned.
        let len = vector::length(&state.badges);
        let i = 0;
        while (i < len) {
            let b = vector::borrow(&state.badges, i);
            assert!(b.id != badge_template_id, E_BADGE_ALREADY_CLAIMED);
            i = i + 1;
        };

        let badge = Badge {
            id: badge_template_id,
            name: template.name,
            description: template.description,
            category: template.category,
            rarity: template.rarity,
            earned_at: timestamp::now_seconds(),
            image_uri: template.image_uri,
        };

        vector::push_back(&mut state.badges, badge);

        event::emit_event(&mut state.events, PlayerEvent {
            event_type: 3,
            value: badge_template_id,
            timestamp: timestamp::now_seconds(),
        });
    }

    // ══════════════════════════════════════════════
    //  Staking for advanced courses
    // ══════════════════════════════════════════════

    /// Stake LDX to unlock premium content and earn a reward multiplier.
    public entry fun stake_tokens(
        player: &signer,
        game_addr: address,
        amount: u64,
        duration_secs: u64,
    ) acquires PlayerState, GameState {
        let player_addr = signer::address_of(player);
        assert!(exists<PlayerState>(player_addr), E_NOT_REGISTERED);

        // Enforce pause.
        let game = borrow_global<GameState>(game_addr);
        assert!(!game.paused, E_GAME_PAUSED);
        assert!(amount > 0, E_INVALID_AMOUNT);
        assert!(duration_secs >= STAKE_MIN_DURATION_SECS, E_INVALID_AMOUNT);

        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(option::is_none(&state.stake), E_STAKE_LOCKED); // already staking

        // Transfer tokens to the module (burn from user, tracked in StakeInfo).
        let balance = coin::balance<LudexToken>(player_addr);
        assert!(balance >= amount, E_INSUFFICIENT_BALANCE);
        coin::transfer<LudexToken>(player, @ludex, amount);

        // Bonus multiplier: base 120 (1.2x), +10 bps per 7 days locked, max 200 (2x).
        let weeks = duration_secs / 604800;
        let multiplier = 120 + weeks * 10;
        if (multiplier > 200) { multiplier = 200; };

        let now = timestamp::now_seconds();
        state.stake = option::some(StakeInfo {
            amount,
            staked_at: now,
            unlock_at: now + duration_secs,
            bonus_multiplier: multiplier,
        });

        event::emit_event(&mut state.events, PlayerEvent {
            event_type: 4,
            value: amount,
            timestamp: now,
        });
    }

    /// Unstake LDX after the lock period.
    public entry fun unstake_tokens(
        admin: &signer,
        game_addr: address,
        player_addr: address,
    ) acquires GameState, PlayerState, TokenCaps {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);

        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(option::is_some(&state.stake), E_INVALID_AMOUNT);

        let stake_info = *option::borrow(&state.stake);
        let now = timestamp::now_seconds();
        assert!(now >= stake_info.unlock_at, E_STAKE_LOCKED);

        // Return staked tokens + staking reward (5% of staked amount).
        let reward = stake_info.amount * 5 / 100;
        let caps = borrow_global<TokenCaps>(game_addr);
        let coins = coin::mint<LudexToken>(stake_info.amount + reward, &caps.mint_cap);
        coin::deposit(player_addr, coins);

        state.stake = option::none();

        event::emit_event(&mut state.events, PlayerEvent {
            event_type: 5,
            value: stake_info.amount + reward,
            timestamp: now,
        });
    }

    // ══════════════════════════════════════════════
    //  Leaderboard
    // ══════════════════════════════════════════════

    /// Refresh a player's position on the leaderboard.
    public entry fun update_leaderboard(
        game_addr: address,
        player_addr: address,
    ) acquires PlayerState, Leaderboard {
        let state = borrow_global<PlayerState>(player_addr);
        let board = borrow_global_mut<Leaderboard>(game_addr);

        let entry = LeaderboardEntry {
            addr: player_addr,
            username: state.profile.username,
            xp: state.profile.xp,
            level: state.profile.level,
        };

        // Remove existing entry for this player if present.
        let len = vector::length(&board.entries);
        let i = 0;
        while (i < len) {
            if (vector::borrow(&board.entries, i).addr == player_addr) {
                vector::swap_remove(&mut board.entries, i);
                len = len - 1;
            } else {
                i = i + 1;
            };
        };

        // Insert in sorted position (descending by XP, then level).
        let inserted = false;
        let len = vector::length(&board.entries);
        let i = 0;
        while (i < len) {
            let existing = vector::borrow(&board.entries, i);
            if (entry.xp > existing.xp || (entry.xp == existing.xp && entry.level > existing.level)) {
                vector::insert(&mut board.entries, i, entry);
                inserted = true;
                break
            };
            i = i + 1;
        };

        if (!inserted) {
            if (len < LEADERBOARD_SIZE) {
                vector::push_back(&mut board.entries, entry);
            };
        } else {
            // Trim if over size.
            while (vector::length(&board.entries) > LEADERBOARD_SIZE) {
                vector::pop_back(&mut board.entries);
            };
        };
    }

    /// Admin: start a new leaderboard season.
    public entry fun new_season(
        admin: &signer,
        game_addr: address,
    ) acquires GameState, Leaderboard {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);

        let board = borrow_global_mut<Leaderboard>(game_addr);
        board.season = board.season + 1;
        board.entries = vector::empty();
        board.season_start = timestamp::now_seconds();
        board.season_end = timestamp::now_seconds() + 2592000;
    }

    // ══════════════════════════════════════════════
    //  Admin: pause / unpause
    // ══════════════════════════════════════════════

    /// Toggle the paused state of the game. When paused, player-facing
    /// functions (register, quest completion, staking) are blocked.
    public entry fun set_paused(
        admin: &signer,
        game_addr: address,
        paused: bool,
    ) acquires GameState {
        let admin_addr = signer::address_of(admin);
        let game = borrow_global_mut<GameState>(game_addr);
        assert!(admin_addr == game.admin, E_NOT_ADMIN);
        game.paused = paused;
    }

    // ══════════════════════════════════════════════
    //  Teams
    // ══════════════════════════════════════════════

    public entry fun create_team(
        player: &signer,
        game_addr: address,
        name: vector<u8>,
    ) acquires PlayerState, TeamRegistry {
        let player_addr = signer::address_of(player);
        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(option::is_none(&state.profile.team_id), E_ALREADY_IN_TEAM);

        let registry = borrow_global_mut<TeamRegistry>(game_addr);
        let team_id = registry.next_team_id;

        let members = vector::empty<address>();
        vector::push_back(&mut members, player_addr);

        let team = Team {
            id: team_id,
            name: string::utf8(name),
            leader: player_addr,
            members,
            total_xp: state.profile.xp,
        };

        table::add(&mut registry.teams, team_id, team);
        registry.next_team_id = team_id + 1;

        state.profile.team_id = option::some(team_id);
    }

    public entry fun join_team(
        player: &signer,
        game_addr: address,
        team_id: u64,
    ) acquires PlayerState, TeamRegistry {
        let player_addr = signer::address_of(player);
        let state = borrow_global_mut<PlayerState>(player_addr);
        assert!(option::is_none(&state.profile.team_id), E_ALREADY_IN_TEAM);

        let registry = borrow_global_mut<TeamRegistry>(game_addr);
        let team = table::borrow_mut(&mut registry.teams, team_id);
        assert!(vector::length(&team.members) < MAX_TEAM_SIZE, E_TEAM_FULL);

        vector::push_back(&mut team.members, player_addr);
        team.total_xp = team.total_xp + state.profile.xp;
        state.profile.team_id = option::some(team_id);
    }

    // ══════════════════════════════════════════════
    //  Social: Friends
    // ══════════════════════════════════════════════

    public entry fun add_friend(
        player: &signer,
        friend_addr: address,
    ) acquires PlayerState {
        let player_addr = signer::address_of(player);
        assert!(exists<PlayerState>(player_addr), E_NOT_REGISTERED);
        assert!(exists<PlayerState>(friend_addr), E_NOT_REGISTERED);

        let state = borrow_global_mut<PlayerState>(player_addr);
        let len = vector::length(&state.friends);
        let i = 0;
        let already_friends = false;
        while (i < len) {
            if (*vector::borrow(&state.friends, i) == friend_addr) {
                already_friends = true;
                break
            };
            i = i + 1;
        };

        if (!already_friends) {
            vector::push_back(&mut state.friends, friend_addr);
        };
    }

    // ══════════════════════════════════════════════
    //  View functions
    // ══════════════════════════════════════════════

    #[view]
    public fun get_player_profile(player_addr: address): PlayerProfile acquires PlayerState {
        assert!(exists<PlayerState>(player_addr), E_NOT_REGISTERED);
        borrow_global<PlayerState>(player_addr).profile
    }

    #[view]
    public fun get_player_level(player_addr: address): u64 acquires PlayerState {
        borrow_global<PlayerState>(player_addr).profile.level
    }

    #[view]
    public fun get_player_xp(player_addr: address): u64 acquires PlayerState {
        borrow_global<PlayerState>(player_addr).profile.xp
    }

    #[view]
    public fun get_xp_to_next_level(player_addr: address): u64 acquires PlayerState {
        let level = borrow_global<PlayerState>(player_addr).profile.level;
        xp_for_next_level(level)
    }

    #[view]
    public fun get_player_badges(player_addr: address): vector<Badge> acquires PlayerState {
        borrow_global<PlayerState>(player_addr).badges
    }

    #[view]
    public fun get_player_streak(player_addr: address): u64 acquires PlayerState {
        borrow_global<PlayerState>(player_addr).profile.daily_streak
    }

    #[view]
    public fun get_quest(game_addr: address, quest_id: u64): Quest acquires QuestRegistry {
        let registry = borrow_global<QuestRegistry>(game_addr);
        *table::borrow(&registry.quests, quest_id)
    }

    #[view]
    public fun get_stake_info(player_addr: address): Option<StakeInfo> acquires PlayerState {
        borrow_global<PlayerState>(player_addr).stake
    }

    #[view]
    public fun get_game_stats(game_addr: address): (u64, u64, u64) acquires GameState {
        let game = borrow_global<GameState>(game_addr);
        (game.total_players, game.total_quests_completed, game.total_tokens_distributed)
    }
}
