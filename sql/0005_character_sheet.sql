-- =============================================================================
-- 0005_character_sheet.sql
--
-- Purpose
--   Store the first two pages of the standard D&D 5e character sheet.
--
-- Row semantics
--   One row in character_sheet = one player character sheet header + page 2
--   narrative blocks, plus pointers to spells/skills and equipment items.
--
-- Conventions
--   - Some boxes remain free-form TEXT to match the sheet.
--   - Pointers are nullable to allow partial character creation flows.
--
-- Keys & constraints
--   - Primary key: character_sheet_id.
--   - Checks:
--       * experience_points is nonnegative
--       * currency fields are nonnegative
--       * death saves are NULL or in 0..3
--       * equipment_item_ids cardinality is bounded (<= 200)
-- =============================================================================
CREATE TABLE IF NOT EXISTS character_sheet (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this character sheet row.
    character_sheet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ========
    -- Identity
    -- ========

    -- Character name.
    character_name TEXT NOT NULL,

    -- Class levels map: JSON object where keys are class names and values are
    -- integer levels for that class (e.g., {"Wizard": 3, "Fighter": 1}).
    class_levels JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Class subclasses map: JSON object where keys are class names and values
    -- are subclass names for that class (e.g., {"Wizard": "Evocation"}).
    class_subclasses JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Background.
    background TEXT,

    -- Player name.
    player_name TEXT,

    -- Race.
    race TEXT,

    -- Alignment.
    alignment TEXT,

    -- Experience points.
    experience_points INTEGER NOT NULL DEFAULT 0,

    -- ==============
    -- Ability scores
    -- ==============

    -- Strength score.
    strength_score INTEGER,

    -- Dexterity score.
    dexterity_score INTEGER,

    -- Constitution score.
    constitution_score INTEGER,

    -- Intelligence score.
    intelligence_score INTEGER,

    -- Wisdom score.
    wisdom_score INTEGER,

    -- Charisma score.
    charisma_score INTEGER,

    -- ======
    -- Combat
    -- ======

    -- Armor Class.
    armor_class INTEGER,

    -- Initiative.
    initiative INTEGER,

    -- Speed.
    speed INTEGER,

    -- Proficiency bonus.
    proficiency_bonus INTEGER,

    -- Inspiration points (0 = none; positive integers allowed).
    inspiration INTEGER NOT NULL DEFAULT 0,

    -- ==========
    -- Hit points
    -- ==========

    -- Hit point maximum.
    hit_point_maximum INTEGER,

    -- Current hit points.
    current_hit_points INTEGER,

    -- Temporary hit points.
    temporary_hit_points INTEGER NOT NULL DEFAULT 0,

    -- =====================
    -- Hit dice / death saves
    -- =====================

    -- Hit dice totals per class (e.g., {"3d8", "1d10"}).
    hit_dice_total TEXT [],

    -- Hit dice current per class (e.g., {"2d8", "1d10"}).
    hit_dice_current TEXT [],

    -- Death saves successes (0..3).
    death_saves_successes INTEGER NOT NULL DEFAULT 0,

    -- Death saves failures (0..3).
    death_saves_failures INTEGER NOT NULL DEFAULT 0,

    -- =========
    -- Currency
    -- =========

    -- Copper pieces.
    copper_pieces INTEGER NOT NULL DEFAULT 0,

    -- Silver pieces.
    silver_pieces INTEGER NOT NULL DEFAULT 0,

    -- Electrum pieces.
    electrum_pieces INTEGER NOT NULL DEFAULT 0,

    -- Gold pieces.
    gold_pieces INTEGER NOT NULL DEFAULT 0,

    -- Platinum pieces.
    platinum_pieces INTEGER NOT NULL DEFAULT 0,

    -- =====================
    -- Proficiencies / boxes
    -- =====================

    -- Passive Wisdom (Perception).
    passive_wisdom_perception INTEGER,

    -- Other proficiencies and languages box.
    other_proficiencies_and_languages TEXT,

    -- Attacks and spellcasting box.
    attacks_and_spellcasting TEXT,

    -- Features and traits box.
    features_and_traits TEXT,

    -- =================
    -- Personality boxes
    -- =================

    -- Personality traits box.
    personality_traits TEXT,

    -- Ideals box.
    ideals TEXT,

    -- Bonds box.
    bonds TEXT,

    -- Flaws box.
    flaws TEXT,

    -- =========
    -- Equipment
    -- =========

    -- Equipment item ids (references items.item_id).
    equipment_item_ids UUID [] NOT NULL DEFAULT '{}'::UUID [],

    -- =========
    -- Narrative
    -- =========

    -- Age.
    age TEXT,

    -- Height.
    height TEXT,

    -- Weight.
    weight TEXT,

    -- Eyes.
    eyes TEXT,

    -- Skin.
    skin TEXT,

    -- Hair.
    hair TEXT,

    -- =========
    -- Narrative
    -- =========

    -- Character appearance.
    character_appearance TEXT,

    -- Character backstory.
    character_backstory TEXT,

    -- Treasure.
    treasure TEXT,

    -- Allies and organizations.
    allies_and_organizations TEXT,

    -- Additional features and traits.
    additional_features_and_traits TEXT,

    -- ==============
    -- Related tables
    -- ==============

    -- Pointer to player_skills(skills_id).
    skills_id UUID REFERENCES player_skills (skills_id),

    -- Pointer to player_spells(spells_id).
    spells_id UUID REFERENCES player_spells (spells_id),

    -- ==============
    -- Audit metadata
    -- ==============

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT character_sheet_chk_xp_nonnegative
    CHECK (
        experience_points >= 0
    ),

    CONSTRAINT character_sheet_chk_currency_nonnegative
    CHECK (
        copper_pieces >= 0
        AND silver_pieces >= 0
        AND electrum_pieces >= 0
        AND gold_pieces >= 0
        AND platinum_pieces >= 0
    ),

    CONSTRAINT character_sheet_chk_inspiration_nonnegative
    CHECK (
        inspiration >= 0
    ),

    CONSTRAINT character_sheet_chk_death_saves_range
    CHECK (
        (
            death_saves_successes IS NULL
            OR (death_saves_successes BETWEEN 0 AND 3)
        )
        AND (
            death_saves_failures IS NULL
            OR (death_saves_failures BETWEEN 0 AND 3)
        )
    ),

    CONSTRAINT character_sheet_chk_equipment_ids_bounded
    CHECK (
        cardinality(equipment_item_ids) <= 200
    )
);


COMMENT ON TABLE character_sheet IS
'One row per player character covering the first two pages of the 5e sheet.';

COMMENT ON COLUMN character_sheet.character_sheet_id IS
'Primary key for the character sheet row (UUID).';

COMMENT ON COLUMN character_sheet.character_name IS
'Character name (page 1 header).';

COMMENT ON COLUMN character_sheet.class_levels IS
'JSON object mapping class names to levels (supports multiclass).';

COMMENT ON COLUMN character_sheet.class_subclasses IS
'JSON object mapping class names to subclass names (supports multiclass).';

COMMENT ON COLUMN character_sheet.background IS
'Background (page 1 header).';

COMMENT ON COLUMN character_sheet.player_name IS
'Player name (page 1 header).';

COMMENT ON COLUMN character_sheet.race IS
'Race (page 1 header).';

COMMENT ON COLUMN character_sheet.alignment IS
'Alignment (page 1 header).';

COMMENT ON COLUMN character_sheet.experience_points IS
'Experience points (page 1 header).';

COMMENT ON COLUMN character_sheet.strength_score IS
'Ability score for Strength.';

COMMENT ON COLUMN character_sheet.dexterity_score IS
'Ability score for Dexterity.';

COMMENT ON COLUMN character_sheet.constitution_score IS
'Ability score for Constitution.';

COMMENT ON COLUMN character_sheet.intelligence_score IS
'Ability score for Intelligence.';

COMMENT ON COLUMN character_sheet.wisdom_score IS
'Ability score for Wisdom.';

COMMENT ON COLUMN character_sheet.charisma_score IS
'Ability score for Charisma.';

COMMENT ON COLUMN character_sheet.armor_class IS
'Armor Class (page 1 combat block).';

COMMENT ON COLUMN character_sheet.initiative IS
'Initiative (page 1 combat block).';

COMMENT ON COLUMN character_sheet.speed IS
'Speed (page 1 combat block).';

COMMENT ON COLUMN character_sheet.proficiency_bonus IS
'Proficiency bonus (page 1 combat block).';

COMMENT ON COLUMN character_sheet.inspiration IS
'Inspiration points (0 = none; nonnegative integer).';

COMMENT ON COLUMN character_sheet.hit_point_maximum IS
'Hit point maximum.';

COMMENT ON COLUMN character_sheet.current_hit_points IS
'Current hit points.';

COMMENT ON COLUMN character_sheet.temporary_hit_points IS
'Temporary hit points (defaults to 0).';

COMMENT ON COLUMN character_sheet.hit_dice_total IS
'Hit dice totals per class (TEXT[]; e.g., {"3d8","1d10"}).';

COMMENT ON COLUMN character_sheet.hit_dice_current IS
'Hit dice current per class (TEXT[]; e.g., {"2d8","1d10"}).';

COMMENT ON COLUMN character_sheet.death_saves_successes IS
'Death saves successes (0..3; defaults to 0).';

COMMENT ON COLUMN character_sheet.death_saves_failures IS
'Death saves failures (0..3; defaults to 0).';

COMMENT ON COLUMN character_sheet.copper_pieces IS
'Currency: CP.';

COMMENT ON COLUMN character_sheet.silver_pieces IS
'Currency: SP.';

COMMENT ON COLUMN character_sheet.electrum_pieces IS
'Currency: EP.';

COMMENT ON COLUMN character_sheet.gold_pieces IS
'Currency: GP.';

COMMENT ON COLUMN character_sheet.platinum_pieces IS
'Currency: PP.';

COMMENT ON COLUMN character_sheet.passive_wisdom_perception IS
'Passive Wisdom (Perception).';

COMMENT ON COLUMN character_sheet.other_proficiencies_and_languages IS
'Other proficiencies and languages box.';

COMMENT ON COLUMN character_sheet.attacks_and_spellcasting IS
'Attacks and spellcasting box.';

COMMENT ON COLUMN character_sheet.features_and_traits IS
'Features and traits box.';

COMMENT ON COLUMN character_sheet.personality_traits IS
'Personality traits box.';

COMMENT ON COLUMN character_sheet.ideals IS
'Ideals box.';

COMMENT ON COLUMN character_sheet.bonds IS
'Bonds box.';

COMMENT ON COLUMN character_sheet.flaws IS
'Flaws box.';

COMMENT ON COLUMN character_sheet.equipment_item_ids IS
'Equipment item ids (references items.item_id).';

COMMENT ON COLUMN character_sheet.age IS
'Age box.';

COMMENT ON COLUMN character_sheet.height IS
'Height box.';

COMMENT ON COLUMN character_sheet.weight IS
'Weight box.';

COMMENT ON COLUMN character_sheet.eyes IS
'Eyes box.';

COMMENT ON COLUMN character_sheet.skin IS
'Skin box.';

COMMENT ON COLUMN character_sheet.hair IS
'Hair box.';

COMMENT ON COLUMN character_sheet.character_appearance IS
'Character appearance box.';

COMMENT ON COLUMN character_sheet.character_backstory IS
'Character backstory box.';

COMMENT ON COLUMN character_sheet.treasure IS
'Treasure box.';

COMMENT ON COLUMN character_sheet.allies_and_organizations IS
'Allies and organizations box.';

COMMENT ON COLUMN character_sheet.additional_features_and_traits IS
'Additional features and traits box.';

COMMENT ON COLUMN character_sheet.skills_id IS
'Pointer to player_skills(skills_id).';

COMMENT ON COLUMN character_sheet.spells_id IS
'Pointer to player_spells(spells_id).';

COMMENT ON COLUMN character_sheet.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN character_sheet.updated_at IS
'UTC timestamp recording row update.';
