"""Seed the rs3.db with representative RS3 training methods, money-making
methods, quest data, boss data, teleports, and dailies.

All XP/hr figures reflect mid-effort play at the stated level range.
Run ``seed_all(db_path)`` once after ``init_db(db_path)``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# ── Training methods ─────────────────────────────────────────────────────────

_TRAINING_METHODS = [
    # (skill, method_name, lo_lvl, hi_lvl, xp_per_hr, gp_cost_per_hr, intensity, reqs_json, notes)
    # Slayer
    ("slayer", "Croesus", 95, 120, 850_000, -2_000_000, "semi",
     '{"slayer": 95, "woodcutting": 90, "fishing": 90, "mining": 90, "farming": 90}',
     "Front role yields highest XP. AoE aura recommended."),
    ("slayer", "Laniakea tasks (general)", 85, 120, 400_000, -500_000, "semi",
     '{"slayer": 85}', "Varies by task; use Morvran for best XP tasks."),
    ("slayer", "Abyssal demons", 85, 120, 450_000, 300_000, "afk",
     '{"slayer": 85}', "Great AFK money. Use aggression potion."),
    ("slayer", "Corrupted creatures (Sophanem)", 88, 120, 600_000, 200_000, "semi",
     '{"slayer": 88}', "Top-tier XP with good profitability."),
    # Herblore
    ("herblore", "Decanting overloads", 96, 120, 2_200_000, -80_000_000, "intensive",
     '{"herblore": 96}', "Fastest herblore in the game. Very expensive."),
    ("herblore", "Making super restores", 63, 120, 350_000, -15_000_000, "semi",
     '{"herblore": 63}', "Cheaper alternative; solid XP."),
    ("herblore", "Making saradomin brews", 81, 120, 500_000, -20_000_000, "semi",
     '{"herblore": 81}', "Good XP/gp ratio."),
    # Magic
    ("magic", "Alching", 55, 120, 120_000, -500_000, "afk",
     '{"magic": 55}', "AFK at almost any location."),
    ("magic", "Ape Atoll course (Surge/Dive)", 90, 120, 380_000, 0, "intensive",
     '{"magic": 90, "agility": 90}', "Requires mobile switches; high intensity."),
    ("magic", "Tan leather (spell)", 78, 120, 800_000, -10_000_000, "semi",
     '{"magic": 78, "lunar_diplomacy": 1}', "Profitable with hides."),
    # Farming
    ("farming", "Tree runs (elder + yew + magic)", 75, 120, 250_000, -500_000, "afk",
     '{"farming": 75}', "15 min per run; do while doing other content."),
    ("farming", "Calquat + palm + dragonfruit", 85, 120, 400_000, -1_000_000, "afk",
     '{"farming": 85}', "Add elder tree for max XP run."),
    # Runecrafting
    ("runecrafting", "Runespan (upper floor)", 90, 120, 95_000, 0, "afk",
     '{"runecrafting": 90}', "Fully AFK method; slow but low cost."),
    ("runecrafting", "Blood runes (Ourania)", 77, 120, 70_000, 10_000_000, "semi",
     '{"runecrafting": 77}', "Profitable; slower XP than Runespan."),
    # Invention
    ("invention", "Augmented dragonstone dragons (disassemble)", 67, 120, 3_000_000, 0, "afk",
     '{"invention": 67, "slayer": 80}', "Augment T80 gear, kill to T4, disassemble."),
    ("invention", "Divine charges (Battery battery)", 60, 120, 1_000_000, -5_000_000, "semi",
     '{"invention": 60}', "AFK with cannon; decent profit."),
    # Archaeology
    ("archaeology", "Stormguard Citadel", 68, 120, 250_000, 500_000, "semi",
     '{"archaeology": 68}', "Good GP + XP combo."),
    ("archaeology", "Orthen Dig Site", 90, 120, 450_000, 1_000_000, "semi",
     '{"archaeology": 90}', "Best Arch XP/hr at high level."),
    # Necromancy
    ("necromancy", "Undead Soul conjurer farming (50-99)", 50, 99, 200_000, 0, "semi",
     '{"necromancy": 50}', "Consistent mid-level XP source."),
    ("necromancy", "Elite Dungeon 3 (Necro)", 90, 120, 600_000, 2_000_000, "intensive",
     '{"necromancy": 90}', "High XP + GP, requires good rotation."),
    # Agility
    ("agility", "Hefin Agility Course", 77, 120, 55_000, 0, "afk",
     '{"agility": 77}', "Fully AFK. Slow but relaxed."),
    ("agility", "Anachronia Agility Course", 90, 120, 85_000, 0, "semi",
     '{"agility": 90}', "Best agility XP/hr at high level."),
    # Mining
    ("mining", "Volcanic Ash + Rockertunity", 80, 120, 100_000, 5_000_000, "semi",
     '{"mining": 80}', "Profitable and good XP with rockertunity nodes."),
    ("mining", "Seren Stones (Elf City)", 89, 120, 80_000, 0, "afk",
     '{"mining": 89, "plague_city_series": 1}', "AFK mining. Low intensity."),
    # Smithing
    ("smithing", "Burial armour (gold)", 70, 120, 380_000, -70_000_000, "afk",
     '{"smithing": 70}', "Fastest smithing but very expensive. AFK."),
    ("smithing", "Elder rune platebody (+5) smelting", 99, 120, 200_000, -5_000_000, "semi",
     '{"smithing": 99}', "Decent XP with lower cost than burial gold."),
    # Fishing
    ("fishing", "Fishing trawler / Menaphos fish", 68, 99, 50_000, 2_000_000, "afk",
     '{"fishing": 68}', "AFK method with decent GP."),
    ("fishing", "Granite crab + heavy rod (Prifddinas)", 90, 120, 150_000, 1_000_000, "afk",
     '{"fishing": 90, "plague_city_series": 1}', "AFK elite Prifddinas fishing."),
    # Woodcutting
    ("woodcutting", "Crystallise crystal trees (Prifddinas)", 94, 120, 150_000, 0, "semi",
     '{"woodcutting": 94, "magic": 88, "plague_city_series": 1}', "Crystallise every 5 ticks for max XP."),
    ("woodcutting", "Elder trees (normal)", 90, 120, 90_000, 2_000_000, "afk",
     '{"woodcutting": 90}', "Good profit; AFK."),
    # Prayer
    ("prayer", "Curses (Dagannoth bones)", 70, 99, 400_000, -40_000_000, "semi",
     '{"prayer": 70}', "Use Ectofuntus or altar with incense burners."),
    ("prayer", "Ourg bones (player-owned house altar)", 70, 99, 350_000, -30_000_000, "semi",
     '{"prayer": 70, "construction": 75}', "Solid XP rate with cheaper bones."),
    # Construction
    ("construction", "Mahogany homes (daily cap)", 50, 99, 250_000, -5_000_000, "semi",
     '{"construction": 50}', "Do daily contracts first for bonus XP."),
    ("construction", "Ornate jewellery box (repetitive)", 83, 99, 400_000, -15_000_000, "intensive",
     '{"construction": 83}', "Fastest construction but expensive."),
    # Dungeoneering
    ("dungeoneering", "Sinkholes (daily)", 75, 120, 600_000, 0, "semi",
     '{"dungeoneering": 75}', "Capped at 2 sinkholes per day; efficient tokens too."),
    ("dungeoneering", "Dungeoneering floors (complexity 6)", 1, 120, 150_000, 0, "intensive",
     '{"dungeoneering": 1}', "Best overall XP/hr with full team."),
    # Divination
    ("divination", "Pale wisps (low level)", 1, 40, 20_000, 0, "afk",
     '{"divination": 1}', "Early game AFK training."),
    ("divination", "Incandescent wisps", 95, 120, 80_000, 0, "afk",
     '{"divination": 95}', "Endgame Div; AFK with energy collection."),
    ("divination", "Hall of Memories (Hefin)", 70, 120, 120_000, 0, "semi",
     '{"divination": 70, "plague_city_series": 1}', "Solid Prifddinas method."),
    # Summoning
    ("summoning", "Infernal urns (bulk)", 57, 99, 250_000, -10_000_000, "semi",
     '{"summoning": 57}', "Make urns with craftable pouches for bonus XP."),
    ("summoning", "Spirit dagannoth pouches", 83, 99, 300_000, -15_000_000, "semi",
     '{"summoning": 83}', "Good XP with moderate cost."),
    # Hunter
    ("hunter", "Box traps (jadinko lair)", 70, 99, 100_000, 2_000_000, "afk",
     '{"hunter": 70}', "AFK box traps in Jadinko Lair."),
    ("hunter", "Grenwalls", 77, 99, 120_000, 5_000_000, "semi",
     '{"hunter": 77}', "Best Hunter profit; moderate XP."),
    # Thieving
    ("thieving", "Prifddinas elves", 91, 120, 280_000, 1_000_000, "semi",
     '{"thieving": 91, "plague_city_series": 1}', "Best thieving XP; good GP too."),
    ("thieving", "Desert bandits (afk)", 45, 90, 100_000, 0, "afk",
     '{"thieving": 45}', "AFK with full Menaphite; good mid-level method."),
    # Firemaking
    ("firemaking", "Bonfire (elder logs)", 90, 120, 400_000, -5_000_000, "afk",
     '{"firemaking": 90}', "AFK bonfire method; very fast with elder logs."),
    ("firemaking", "Incense sticks (daily)", 80, 120, 600_000, -3_000_000, "semi",
     '{"firemaking": 80}', "Make incense sticks for fastest FM XP."),
    # Crafting
    ("crafting", "Glassblowing (molten glass)", 46, 99, 200_000, -10_000_000, "semi",
     '{"crafting": 46}', "Semi-AFK with high cost."),
    ("crafting", "Cutting gems (onyx/zenyte)", 67, 99, 150_000, 5_000_000, "afk",
     '{"crafting": 67}', "AFK with decent profit."),
    # Fletching
    ("fletching", "Headless arrows (bulk)", 1, 99, 1_200_000, -2_000_000, "intensive",
     '{"fletching": 1}', "Fast click-intensive method."),
    ("fletching", "Ascendri bolts (e)", 80, 99, 600_000, 1_000_000, "semi",
     '{"fletching": 80}', "Solid XP with nice profit margin."),
    # Cooking
    ("cooking", "Rocktails (Prifddinas range)", 93, 99, 500_000, 2_000_000, "afk",
     '{"cooking": 93, "plague_city_series": 1}', "Fully AFK with no-burn at level 94+."),
    ("cooking", "Sharks (portable range)", 80, 99, 350_000, 500_000, "afk",
     '{"cooking": 80}', "Good XP; use portable range for 10% boost."),
    # Attack / Strength / Defence / Constitution / Ranged / Magic (combat)
    ("attack", "ED3 (melee)", 90, 99, 1_500_000, 3_000_000, "intensive",
     '{"attack": 90, "strength": 90, "defence": 90}', "Elite Dungeon 3 melee."),
    ("strength", "ED3 (melee)", 90, 99, 1_500_000, 3_000_000, "intensive",
     '{"strength": 90}', "Elite Dungeon 3 melee."),
    ("ranged", "Abyss combat training", 70, 99, 800_000, 0, "semi",
     '{"ranged": 70}', "AoE Abyss creatures; decent ranged XP."),
    ("magic", "ED2 (mage)", 80, 99, 1_000_000, 2_000_000, "intensive",
     '{"magic": 80}', "Elite Dungeon 2 — Temple of Aminishi."),
]

# ── Money-making methods ─────────────────────────────────────────────────────

_MONEY_MAKING = [
    # (method, gp_per_hr, reqs_json, intensity, is_boss, notes)
    ("Telos the Warden (high enrage)", 30_000_000, '{"combat": 130}', "intensive", 1,
     "1000%+ enrage. Requires near-BIS gear and top-tier rotations."),
    ("Solak (duo)", 20_000_000, '{"combat": 120, "slayer": 99}', "intensive", 1,
     "Best duo boss GP/hr with good team."),
    ("Araxxor", 15_000_000, '{"slayer": 92}', "intensive", 1,
     "Top single-player GP/hr at mid gear tier."),
    ("Arch-Glacor (adaptive)", 12_000_000, '{"combat": 115}', "intensive", 1,
     "Scale enrage for risk/reward balance."),
    ("Abyssal lords (slayer)", 8_000_000, '{"slayer": 115}', "afk",  0,
     "AFK slayer with good drops."),
    ("Praesulianic armour pieces", 7_000_000, '{"slayer": 95, "combat": 100}', "semi", 1,
     "Rago/Araxxor; depends on luck."),
    ("Nex", 6_000_000, '{"combat": 110}', "intensive", 1,
     "Good GP/hr with consistent drop table."),
    ("Killing tormented demons", 5_000_000, '{"combat": 100, "slayer": 0}', "semi", 0,
     "Drops hard clue scrolls and Zaros godsword shards."),
    ("Crystallise crystal trees + selling logs", 4_000_000, '{"woodcutting": 94, "magic": 88}', "semi", 0,
     "Good combined XP/GP method."),
    ("Slayer (Mandrith)", 5_500_000, '{"slayer": 85, "combat": 100}', "semi", 0,
     "Wilderness slayer; higher GP with risk."),
    ("Casting tan leather", 3_000_000, '{"magic": 78}', "semi", 0,
     "Buy dragonhide, tan, resell."),
    ("Herb runs (torstol/snapdragon)", 2_500_000, '{"farming": 85}', "afk", 0,
     "12-min runs; passive income alongside other activities."),
    ("Vis Wax (daily)", 2_000_000, '{"runecrafting": 50}', "afk", 0,
     "Daily RC Guild activity. ~5 min per day."),
    ("Merching elite dungeon tokens", 1_500_000, '{}', "afk", 0,
     "Check GE margin on dungeon-specific items."),
    ("Big Chinchompa (daily)", 500_000, '{"hunter": 53}', "afk", 0,
     "Daily D&D; good Div + Hunter XP too."),
]

# ── Quests (representative set) ───────────────────────────────────────────────

_QUESTS = [
    # (name, qp, qp_required, skill_reqs_json, quest_reqs_json, rewards_json, difficulty, length, series)
    ("Cook's Assistant", 1, 0, '{}', '[]', '{"cooking_xp": 300}', "novice", "short", ""),
    ("Dragon Slayer", 2, 0, '{"magic": 35}', '[]', '{"defence_xp": 18650}', "experienced", "long", ""),
    ("Desert Treasure", 3, 10,
     '{"magic": 50, "thieving": 53, "firemaking": 50, "slayer": 10}',
     '["The Dig Site", "Temple of Ikov", "The Tourist Trap", "Priest in Peril", "Waterfall Quest"]',
     '{"magic_xp": 20000}', "master", "long", ""),
    ("Sliske's Endgame", 1, 200,
     '{"combat": 110}',
     '["God Wars Dungeon", "The World Wakes", "Fate of the Gods", "Missing, Presumed Death", "The Light Within", "Kindred Spirits"]',
     '{"xp_lamps": 4, "quest_points": 1}', "grandmaster", "long", "Sliske's Game"),
    ("Monkey Madness", 3, 0,
     '{"agility": 43}',
     '["The Grand Tree", "Tree Gnome Village"]',
     '{"attack_xp": 35000, "magic_xp": 35000, "hitpoints_xp": 35000}', "experienced", "long", "Gnome"),
    ("The World Wakes", 2, 160,
     '{"attack": 60, "strength": 60, "magic": 60, "ranged": 60, "summoning": 60, "dungeoneering": 60, "prayer": 60}',
     '["The Chosen Commander", "While Guthix Sleeps", "Ritual of the Mahjarrat"]',
     '{"quest_points": 2, "combat_xp": 500000}', "grandmaster", "long", ""),
    ("Plague City", 1, 0, '{}', '[]', '{"mining_xp": 2425}', "novice", "short", "Plague City"),
    ("Plague's End", 2, 75,
     '{"agility": 75, "construction": 75, "crafting": 75, "dungeoneering": 75, "herblore": 75, "mining": 75, "prayer": 75, "ranged": 75, "smithing": 75, "summoning": 75, "woodcutting": 75}',
     '["Within the Light", "Branches of Darkmeyer", "The Light Within"]',
     '{"quest_points": 2, "access_to_prifddinas": true}', "grandmaster", "very long", "Plague City"),
    ("Haunted Mine", 2, 0,
     '{"crafting": 35, "agility": 15}',
     '["Priest in Peril"]',
     '{"slayer_xp": 22000}', "experienced", "medium", ""),
    ("Recipe for Disaster", 10, 175,
     '{"cooking": 70, "fishing": 53, "firemaking": 50, "magic": 59, "smithing": 40, "woodcutting": 36}',
     '["Cook\'s Assistant", "Biohazard", "Goblin Diplomacy", "Fishing Contest", "Gertrude\'s Cat", "Romeo & Juliet", "Shield of Arrav", "Witch\'s Potion", "Big Chompy Bird Hunting", "Jungle Potion", "Freeing Evil Dave"]',
     '{"quest_points": 10}', "master", "very long", ""),
    ("Ritual of the Mahjarrat", 3, 0,
     '{"combat": 76, "slayer": 76, "magic": 76, "agility": 60, "crafting": 50, "divination": 1}',
     '["Temple of Ikov", "The Dig Site", "Enakhra\'s Lament", "The Tale of the Muspah", "Hazeel Cult", "Stolen Hearts"]',
     '{"xp_lamps": 5}', "grandmaster", "long", "Mahjarrat"),
]

# ── Bosses ───────────────────────────────────────────────────────────────────

_BOSSES = [
    # (name, hp, weakness, kill_time_p50, kill_time_p10, drop_table_json, gp_hr_p50, gp_hr_p10, notes)
    ("Telos the Warden", 60_000, "None (spec)", 180, 90, '{"staff_of_sliske": 0.002}', 15_000_000, 30_000_000, "Enrage increases difficulty and loot."),
    ("Araxxor", 100_000, "varies by path", 240, 120, '{"noxious_components": 0.1}', 8_000_000, 15_000_000, "Choose path based on weakness."),
    ("Solak", 800_000, "all styles", 300, 180, '{"limitless_ability": 0.005}', 10_000_000, 20_000_000, "Duo recommended."),
    ("Arch-Glacor", 500_000, "None (adaptable)", 120, 60, '{"glacor_components": 0.25}', 6_000_000, 12_000_000, "Scale mechanics for higher loot."),
    ("Nex", 73_000, "None", 120, 70, '{"torva_platebody": 0.01, "zaryte_bow": 0.005}', 3_000_000, 6_000_000, "Classic endgame boss."),
    ("General Graardor", 35_000, "melee/crush", 90, 45, '{"bandos_chestplate": 0.016}', 1_500_000, 3_000_000, "Beginner-friendly GWD1 boss."),
    ("Commander Zilyana", 30_000, "ranged", 80, 40, '{"saradomin_sword": 0.016}', 1_200_000, 2_500_000, "GWD1 Saradomin boss."),
    ("K'ril Tsutsaroth", 35_000, "magic", 85, 42, '{"zamorakian_spear": 0.016}', 1_300_000, 2_600_000, "GWD1 Zamorak boss."),
    ("Kree'arra", 25_000, "magic", 75, 38, '{"armadyl_chestplate": 0.016}', 1_400_000, 2_800_000, "GWD1 Armadyl boss; ranged drops."),
]

# ── Teleports ───────────────────────────────────────────────────────────────

_TELEPORTS = [
    # (name, region, x, y, item_required, cooldown_s, type)
    ("Lodestone: Lumbridge", "Lumbridge", 3232, 3220, "", 0, "lodestone"),
    ("Lodestone: Varrock", "Varrock", 3213, 3424, "", 0, "lodestone"),
    ("Lodestone: Falador", "Falador", 2967, 3404, "", 0, "lodestone"),
    ("Lodestone: Edgeville", "Edgeville", 3087, 3491, "", 0, "lodestone"),
    ("Lodestone: Prifddinas", "Prifddinas", 2208, 3327, "", 0, "lodestone"),
    ("Lodestone: Menaphos", "Menaphos", 3232, 2720, "", 0, "lodestone"),
    ("Lodestone: Anachronia", "Anachronia", 5765, 5203, "", 0, "lodestone"),
    ("War's Retreat", "Wilderness border", 3296, 3886, "", 0, "war_retreat"),
    ("Slayer Cape (Morvran)", "Prifddinas Slayer", 2193, 3275, "slayer_cape", 0, "cape"),
    ("Max Guild teleport", "Prifddinas", 2280, 3113, "max_cape", 0, "cape"),
    ("Archaeology Journal (Kharid-et)", "Kharid-et", 3160, 3008, "arch_journal", 30, "item"),
    ("Archaeology Journal (Orthen)", "Orthen", 5893, 2931, "arch_journal", 30, "item"),
    ("Fairy Ring (AKQ) — Piscatoris", "Piscatoris", 2322, 3781, "fairy_ring", 0, "fairy_ring"),
    ("Spirit Tree — Gnome Stronghold", "Gnome Stronghold", 2461, 3444, "spirit_tree", 0, "spirit_tree"),
    ("God Wars Dungeon teleport", "Trollheim area", 2920, 3757, "gwd_tab", 0, "tablet"),
]

# ── Dailies ──────────────────────────────────────────────────────────────────

_DAILIES = [
    # (name, reset_type, category, gp_value, xp_value, notes)
    ("Vis Wax", "daily", "runecrafting", 2_000_000, 0, "RC Guild; figure out the 3 rune combo."),
    ("Herb runs", "daily", "farming", 500_000, 20_000, "Do every ~80 min; plant torstol/snapdragon."),
    ("Big Chinchompa", "daily", "hunter/divination", 200_000, 30_000, "2 per day; ~15 min each."),
    ("Sinkholes", "daily", "dungeoneering", 0, 50_000, "Bonus Dung tokens + XP."),
    ("Penguin Hide and Seek", "weekly", "various", 1_000_000, 100_000, "Visit penguins; convert points to XP or GP."),
    ("Reaper task", "daily", "combat", 0, 0, "Assigned by Death; Reaper points → Reaper necklace/ability."),
    ("Croesus", "weekly", "slayer/skilling", 0, 500_000, "Skilling boss. Reset Wednesday 00:00 UTC."),
    ("Shattered Worlds", "weekly", "combat/invention", 0, 100_000, "Fragment drops for Invention."),
    ("Player-Owned Farm", "daily", "farming", 200_000, 10_000, "Collect animals; sell premium produce."),
    ("Slayer Co-op points", "weekly", "slayer", 0, 0, "Co-op with a friend for bonus Slayer points."),
    ("Wilderness Flash Events", "daily", "combat", 500_000, 0, "Quick 2-min events; GP drops + emblems."),
    ("Daily challenges", "daily", "various", 0, 50_000, "Complete 3 for bonus XP lamps."),
    ("Travelling Merchant stock", "daily", "various", 0, 0, "Check for Brawling Gloves, Chronicle Fragments, etc."),
    ("Guthixian Cache", "daily", "divination", 0, 80_000, "10 min; great Div XP/hr in daily window."),
]


def seed_training_methods(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO training_methods
           (skill, method_name, lo_lvl, hi_lvl, xp_per_hr, gp_cost_per_hr, intensity, requirements_json, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        _TRAINING_METHODS,
    )


def seed_money_making(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO money_making
           (method, gp_per_hr, requirements_json, intensity, is_boss, notes)
           VALUES (?,?,?,?,?,?)""",
        _MONEY_MAKING,
    )


def seed_quests(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO quests
           (name, qp, qp_required, skill_reqs_json, quest_reqs_json, rewards_json, difficulty, length, series)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        _QUESTS,
    )


def seed_bosses(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO bosses
           (name, hp, weakness, kill_time_p50, kill_time_p10, drop_table_json, gp_per_hr_p50, gp_per_hr_p10, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        _BOSSES,
    )


def seed_teleports(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO teleports
           (name, region, x, y, item_required, cooldown_s, type)
           VALUES (?,?,?,?,?,?,?)""",
        _TELEPORTS,
    )


def seed_dailies(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO dailies
           (name, reset_type, category, gp_value, xp_value, notes)
           VALUES (?,?,?,?,?,?)""",
        _DAILIES,
    )


def seed_all(db_path: Path) -> None:
    """Seed all tables with representative RS3 data.

    Safe to run multiple times — uses INSERT OR IGNORE.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        seed_training_methods(conn)
        seed_money_making(conn)
        seed_quests(conn)
        seed_bosses(conn)
        seed_teleports(conn)
        seed_dailies(conn)
        conn.commit()
    finally:
        conn.close()
