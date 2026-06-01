-- ═══════════════════════════════════════════════════════════
-- Myceo — Tranche 2 : Compétition (saison LFL, classement, séries, games, events)
-- Idempotent — à lancer en local ET sur la VM.
-- ═══════════════════════════════════════════════════════════

-- ─── Saison (1 active par franchise ; 3 splits/an) ─────────
CREATE TABLE IF NOT EXISTS gm_seasons (
  id               SERIAL PRIMARY KEY,
  team_id          INTEGER NOT NULL REFERENCES gm_teams(id) ON DELETE CASCADE,
  league           VARCHAR(10) NOT NULL DEFAULT 'LFL',
  year             SMALLINT NOT NULL,
  split_no         SMALLINT NOT NULL DEFAULT 1,
  phase            VARCHAR(12) NOT NULL DEFAULT 'REGULAR',
  current_matchday SMALLINT NOT NULL DEFAULT 1,
  total_matchdays  SMALLINT NOT NULL DEFAULT 9,
  created_at       TIMESTAMP DEFAULT now(),
  CONSTRAINT ck_gm_season_phase CHECK (phase IN ('REGULAR','PLAYOFFS','DONE')),
  CONSTRAINT ck_gm_season_split CHECK (split_no BETWEEN 1 AND 3)
);
CREATE INDEX IF NOT EXISTS idx_gm_seasons_team ON gm_seasons(team_id);

-- ─── Équipes IA (pool global, skin LFL au-dessus d'un bot_tier) ─
CREATE TABLE IF NOT EXISTS gm_ai_teams (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(60) NOT NULL,
  logo_url      TEXT,
  region        VARCHAR(10) NOT NULL DEFAULT 'LFL',
  bot_tier      VARCHAR(4) NOT NULL DEFAULT 'G2',
  base_strength SMALLINT NOT NULL DEFAULT 70,
  seed          SMALLINT NOT NULL DEFAULT 0,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMP DEFAULT now(),
  CONSTRAINT ck_gm_ai_tier CHECK (bot_tier IN ('KC','G2','T1'))
);

-- ─── Classement (1 ligne par compétiteur ; ai_team_id NULL = user) ─
CREATE TABLE IF NOT EXISTS gm_standings (
  id         SERIAL PRIMARY KEY,
  season_id  INTEGER NOT NULL REFERENCES gm_seasons(id) ON DELETE CASCADE,
  ai_team_id INTEGER REFERENCES gm_ai_teams(id),
  wins       SMALLINT NOT NULL DEFAULT 0,
  losses     SMALLINT NOT NULL DEFAULT 0,
  points     SMALLINT NOT NULL DEFAULT 0,
  played     SMALLINT NOT NULL DEFAULT 0,
  CONSTRAINT uq_gm_standing UNIQUE (season_id, ai_team_id)
);
CREATE INDEX IF NOT EXISTS idx_gm_standings_season ON gm_standings(season_id);
-- une seule ligne "user" (ai_team_id NULL) par saison
CREATE UNIQUE INDEX IF NOT EXISTS uq_gm_standing_user
  ON gm_standings(season_id) WHERE ai_team_id IS NULL;

-- ─── Match = série (BO1 régulière, BO3/BO5 playoffs) ───────
CREATE TABLE IF NOT EXISTS gm_matches (
  id            SERIAL PRIMARY KEY,
  season_id     INTEGER NOT NULL REFERENCES gm_seasons(id) ON DELETE CASCADE,
  phase         VARCHAR(8) NOT NULL DEFAULT 'REGULAR',
  matchday      SMALLINT,
  round_label   VARCHAR(20),
  home_ai_id    INTEGER REFERENCES gm_ai_teams(id),
  away_ai_id    INTEGER REFERENCES gm_ai_teams(id),
  format        VARCHAR(4) NOT NULL DEFAULT 'BO1',
  score_home    SMALLINT NOT NULL DEFAULT 0,
  score_away    SMALLINT NOT NULL DEFAULT 0,
  status        VARCHAR(12) NOT NULL DEFAULT 'SCHEDULED',
  winner_side   VARCHAR(4),
  involves_user BOOLEAN NOT NULL DEFAULT false,
  played_at     TIMESTAMP,
  CONSTRAINT ck_gm_match_phase  CHECK (phase IN ('REGULAR','SEMI','FINAL')),
  CONSTRAINT ck_gm_match_format CHECK (format IN ('BO1','BO3','BO5')),
  CONSTRAINT ck_gm_match_status CHECK (status IN ('SCHEDULED','DRAFTING','PLAYED')),
  CONSTRAINT ck_gm_match_winner CHECK (winner_side IS NULL OR winner_side IN ('HOME','AWAY'))
);
CREATE INDEX IF NOT EXISTS idx_gm_matches_season ON gm_matches(season_id);
CREATE INDEX IF NOT EXISTS idx_gm_matches_user   ON gm_matches(involves_user);

-- ─── Game = une draft d'une série (matchs du user uniquement) ─
CREATE TABLE IF NOT EXISTS gm_games (
  id            SERIAL PRIMARY KEY,
  match_id      INTEGER NOT NULL REFERENCES gm_matches(id) ON DELETE CASCADE,
  game_no       SMALLINT NOT NULL DEFAULT 1,
  user_side     VARCHAR(4),
  draft_state   JSONB,
  draft_user    REAL,
  draft_opp     REAL,
  strength_user REAL,
  strength_opp  REAL,
  mental_user   REAL,
  mental_opp    REAL,
  p_win         REAL,
  result        VARCHAR(4),
  status        VARCHAR(12) NOT NULL DEFAULT 'DRAFTING',
  played_at     TIMESTAMP,
  created_at    TIMESTAMP DEFAULT now(),
  CONSTRAINT uq_gm_game UNIQUE (match_id, game_no),
  CONSTRAINT ck_gm_game_result CHECK (result IS NULL OR result IN ('WIN','LOSS')),
  CONSTRAINT ck_gm_game_side   CHECK (user_side IS NULL OR user_side IN ('BLUE','RED'))
);
CREATE INDEX IF NOT EXISTS idx_gm_games_match ON gm_games(match_id);

-- ─── Events aléatoires ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS gm_events (
  id          SERIAL PRIMARY KEY,
  team_id     INTEGER NOT NULL REFERENCES gm_teams(id) ON DELETE CASCADE,
  season_id   INTEGER REFERENCES gm_seasons(id) ON DELETE CASCADE,
  matchday    SMALLINT,
  type        VARCHAR(16) NOT NULL,
  payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
  message     TEXT,
  is_resolved BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gm_events_team ON gm_events(team_id);

ALTER TABLE gm_ai_teams DROP CONSTRAINT IF EXISTS ck_gm_ai_tier;
ALTER TABLE gm_ai_teams ADD CONSTRAINT ck_gm_ai_tier
  CHECK (bot_tier IN ('LFL','KC','G2','T1'));