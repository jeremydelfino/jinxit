-- gm_tranche1.sql  (game-mode, tranche 1)
BEGIN;

CREATE TABLE IF NOT EXISTS gm_teams (
  id          SERIAL PRIMARY KEY,
  owner_id    INTEGER NOT NULL UNIQUE REFERENCES users(id),
  name        VARCHAR(60) NOT NULL,
  logo_url    TEXT,
  league      VARCHAR(10) NOT NULL DEFAULT 'LFL',
  budget      BIGINT      NOT NULL DEFAULT 5000,
  fans        INTEGER     NOT NULL DEFAULT 0,
  reputation  SMALLINT    NOT NULL DEFAULT 50,
  ovr_cached  SMALLINT    NOT NULL DEFAULT 0,
  created_at  TIMESTAMP   DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gm_player_cards (
  id                SERIAL PRIMARY KEY,
  esports_player_id INTEGER REFERENCES esports_players(id),
  variant           VARCHAR(20) NOT NULL DEFAULT 'BASE',
  role              VARCHAR(10) NOT NULL,
  nationality       VARCHAR(2),
  laning    SMALLINT NOT NULL DEFAULT 70,
  teamfight SMALLINT NOT NULL DEFAULT 70,
  vision    SMALLINT NOT NULL DEFAULT 70,
  mechanics SMALLINT NOT NULL DEFAULT 70,
  stress    SMALLINT NOT NULL DEFAULT 70,
  clutch    SMALLINT NOT NULL DEFAULT 70,
  ego       SMALLINT NOT NULL DEFAULT 3,
  traits    JSONB    NOT NULL DEFAULT '[]'::jsonb,
  ovr         SMALLINT NOT NULL DEFAULT 0,
  base_salary INTEGER  NOT NULL DEFAULT 0,
  is_active   BOOLEAN  NOT NULL DEFAULT true,
  created_at  TIMESTAMP DEFAULT now(),
  CONSTRAINT uq_card_player_variant UNIQUE (esports_player_id, variant),
  CONSTRAINT ck_card_ego CHECK (ego BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS gm_contracts (
  id          SERIAL PRIMARY KEY,
  team_id     INTEGER NOT NULL REFERENCES gm_teams(id) ON DELETE CASCADE,
  card_id     INTEGER NOT NULL REFERENCES gm_player_cards(id),
  role_slot   VARCHAR(10),
  salary      INTEGER NOT NULL,
  side        VARCHAR(8) NOT NULL DEFAULT 'NEUTRAL',
  is_starter  BOOLEAN NOT NULL DEFAULT false,
  acquired_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gm_contracts_team ON gm_contracts(team_id);

CREATE TABLE IF NOT EXISTS gm_pack_types (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(80) NOT NULL,
  description   TEXT,
  image_url     TEXT,
  price_budget  INTEGER NOT NULL,
  w_70_74 SMALLINT NOT NULL DEFAULT 0,
  w_75_84 SMALLINT NOT NULL DEFAULT 0,
  w_85_89 SMALLINT NOT NULL DEFAULT 0,
  w_90_99 SMALLINT NOT NULL DEFAULT 0,
  league_filter VARCHAR(10),
  role_filter   VARCHAR(10),
  is_active     BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMP DEFAULT now()
);

COMMIT;