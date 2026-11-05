-- KPI Catalog schema: the single source of truth (PRD §4).
-- The seed generator (kpigen) is validated against it and the app builds its database from it.
-- Conventions: readable string IDs fixed in the curation files (DIV-001, USR-001, KPI-0001, DEF-0001, ...);
-- timestamps are ISO 8601 text in UTC ("2026-10-01T09:00:00Z"); every enum has a CHECK.
-- Run with PRAGMA foreign_keys = ON.
-- The FTS5 search index is built by the loader (W2), not here.

-- ---------------------------------------------------------------------------
-- 4.1 Organization and access
-- ---------------------------------------------------------------------------

CREATE TABLE divisions (
    division_id  TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE
                 CHECK (code IN ('FIN', 'COM', 'MKT', 'PRD', 'OPS', 'PPL', 'RSK', 'DAT')),
    name         TEXT NOT NULL,
    description  TEXT NOT NULL
);

CREATE TABLE users (
    user_id           TEXT PRIMARY KEY,
    full_name         TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    home_division_id  TEXT NOT NULL REFERENCES divisions (division_id),
    job_title         TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE roles (
    role_id      TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE
                 CHECK (code IN ('observer', 'contributor', 'curator', 'reviewer', 'admin')),
    name         TEXT NOT NULL,
    description  TEXT NOT NULL
);

CREATE TABLE permissions (
    permission_id  TEXT PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    description    TEXT NOT NULL
);

CREATE TABLE role_permissions (
    role_id        TEXT NOT NULL REFERENCES roles (role_id),
    permission_id  TEXT NOT NULL REFERENCES permissions (permission_id),
    PRIMARY KEY (role_id, permission_id)
);

-- division_id is NULL for the admin role (group-wide) and required for every other role.
CREATE TABLE user_roles (
    user_id      TEXT NOT NULL REFERENCES users (user_id),
    role_id      TEXT NOT NULL REFERENCES roles (role_id),
    division_id  TEXT REFERENCES divisions (division_id),
    UNIQUE (user_id, role_id, division_id)
);
-- UNIQUE treats NULLs as distinct, so guard the admin rows separately.
CREATE UNIQUE INDEX user_roles_admin_once ON user_roles (user_id, role_id) WHERE division_id IS NULL;

CREATE TRIGGER user_roles_division_insert BEFORE INSERT ON user_roles
WHEN (NEW.division_id IS NULL) <> ((SELECT code FROM roles WHERE role_id = NEW.role_id) = 'admin')
BEGIN
    SELECT RAISE(ABORT, 'user_roles.division_id must be NULL for admin and set for every other role');
END;

CREATE TRIGGER user_roles_division_update BEFORE UPDATE ON user_roles
WHEN (NEW.division_id IS NULL) <> ((SELECT code FROM roles WHERE role_id = NEW.role_id) = 'admin')
BEGIN
    SELECT RAISE(ABORT, 'user_roles.division_id must be NULL for admin and set for every other role');
END;

-- ---------------------------------------------------------------------------
-- 4.2 Catalog
-- ---------------------------------------------------------------------------

CREATE TABLE kpis (
    kpi_id       TEXT PRIMARY KEY,
    slug         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,          -- division-neutral
    created_at   TEXT NOT NULL
);

-- A KPI can have several definitions in the same division (told apart by source_table).
CREATE TABLE definitions (
    definition_id     TEXT PRIMARY KEY,
    kpi_id            TEXT NOT NULL REFERENCES kpis (kpi_id),
    division_id       TEXT NOT NULL REFERENCES divisions (division_id),
    display_name      TEXT NOT NULL,     -- the label this division uses
    definition_text   TEXT NOT NULL,
    metric_type       TEXT NOT NULL
                      CHECK (metric_type IN ('base', 'simple', 'ratio', 'derived', 'cumulative')),
    formula           TEXT,
    unit              TEXT NOT NULL
                      CHECK (unit IN ('EUR', 'USD', '%', 'ratio', 'times', 'count', 'score')),
    grain             TEXT NOT NULL
                      CHECK (grain IN ('daily', 'weekly', 'monthly', 'quarterly')),
    source_table      TEXT,
    source_column     TEXT,
    related_columns   TEXT,
    owner_user_id     TEXT NOT NULL REFERENCES users (user_id),
    status            TEXT NOT NULL
                      CHECK (status IN ('draft', 'in_review', 'approved', 'rejected', 'deprecated')),
    version           INTEGER NOT NULL CHECK (version >= 1),
    superseded_by_id  TEXT REFERENCES definitions (definition_id)
                      CHECK (superseded_by_id IS NULL OR superseded_by_id <> definition_id),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL CHECK (updated_at >= created_at),
    origin            TEXT NOT NULL
                      CHECK (origin IN ('huggingface', 'dbt', 'handwritten', 'app')),
    origin_ref        TEXT,              -- e.g. hf:22, dbt:revenue, scenarios:turnover_fin; NULL for app
    CHECK ((origin = 'app') = (origin_ref IS NULL))
);

CREATE TABLE kpi_relationships (
    relationship_id     TEXT PRIMARY KEY,
    from_definition_id  TEXT NOT NULL REFERENCES definitions (definition_id),
    to_definition_id    TEXT NOT NULL REFERENCES definitions (definition_id),
    relationship_type   TEXT NOT NULL
                        CHECK (relationship_type IN ('composed_of', 'subset_of', 'cumulative_of', 'related_to')),
    role                TEXT CHECK (role IN ('numerator', 'denominator', 'input')),
    alias               TEXT,
    offset_window       TEXT,
    origin              TEXT NOT NULL CHECK (origin IN ('dbt', 'handwritten', 'curation')),
    CHECK (from_definition_id <> to_definition_id),
    CHECK (role IS NULL OR relationship_type = 'composed_of')
);

CREATE TABLE reviews (
    review_id         TEXT PRIMARY KEY,
    definition_id     TEXT NOT NULL REFERENCES definitions (definition_id),
    reviewer_user_id  TEXT NOT NULL REFERENCES users (user_id),
    decision          TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
    comment           TEXT NOT NULL,
    reviewed_at       TEXT NOT NULL
);

CREATE TABLE assets (
    asset_id       TEXT PRIMARY KEY,
    asset_type     TEXT NOT NULL CHECK (asset_type IN ('dashboard', 'report')),
    name           TEXT NOT NULL UNIQUE,
    description    TEXT NOT NULL,
    tool           TEXT NOT NULL,
    url            TEXT NOT NULL,
    division_id    TEXT NOT NULL REFERENCES divisions (division_id),
    owner_user_id  TEXT NOT NULL REFERENCES users (user_id),
    created_at     TEXT NOT NULL
);

CREATE TABLE asset_definitions (
    asset_id       TEXT NOT NULL REFERENCES assets (asset_id),
    definition_id  TEXT NOT NULL REFERENCES definitions (definition_id),
    PRIMARY KEY (asset_id, definition_id)
);

-- ---------------------------------------------------------------------------
-- 4.3 Tags (official = SKOS concept, community = folksonomy)
-- ---------------------------------------------------------------------------

CREATE TABLE tags (
    tag_id       TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('official', 'community')),
    label        TEXT NOT NULL,
    facet        TEXT CHECK (facet IN ('category', 'business_line')),
    concept_uri  TEXT,
    created_by   TEXT REFERENCES users (user_id),
    created_at   TEXT NOT NULL,
    UNIQUE (kind, label),
    CHECK (
        (kind = 'official' AND facet IS NOT NULL AND concept_uri IS NOT NULL)
        OR (kind = 'community' AND facet IS NULL AND concept_uri IS NULL)
    )
);

CREATE TABLE definition_tags (
    definition_id  TEXT NOT NULL REFERENCES definitions (definition_id),
    tag_id         TEXT NOT NULL REFERENCES tags (tag_id),
    source         TEXT NOT NULL CHECK (source IN ('ml', 'curator', 'user')),
    confidence     REAL CHECK (confidence BETWEEN -1 AND 1),
    status         TEXT CHECK (status IN ('auto', 'accepted', 'rejected')),
    tagged_by      TEXT REFERENCES users (user_id),
    tagged_at      TEXT NOT NULL,
    PRIMARY KEY (definition_id, tag_id),
    CHECK ((source = 'ml') = (confidence IS NOT NULL)),
    CHECK ((source = 'ml') = (tagged_by IS NULL))
);

-- status is NULL exactly for community tags (it tracks curator validation of official tags).
CREATE TRIGGER definition_tags_status_insert BEFORE INSERT ON definition_tags
WHEN (NEW.status IS NULL) <> ((SELECT kind FROM tags WHERE tag_id = NEW.tag_id) = 'community')
BEGIN
    SELECT RAISE(ABORT, 'definition_tags.status must be NULL for community tags and set for official tags');
END;

CREATE TRIGGER definition_tags_status_update BEFORE UPDATE ON definition_tags
WHEN (NEW.status IS NULL) <> ((SELECT kind FROM tags WHERE tag_id = NEW.tag_id) = 'community')
BEGIN
    SELECT RAISE(ABORT, 'definition_tags.status must be NULL for community tags and set for official tags');
END;

-- ---------------------------------------------------------------------------
-- 4.4 ML output (not in the seed)
-- ---------------------------------------------------------------------------

CREATE TABLE similarity_flags (
    flag_id          TEXT PRIMARY KEY,
    type             TEXT NOT NULL
                     CHECK (type IN ('possible_synonym', 'definitions_diverge', 'unit_mismatch')),
    a_definition_id  TEXT NOT NULL REFERENCES definitions (definition_id),
    b_definition_id  TEXT REFERENCES definitions (definition_id),
    score            REAL NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('open', 'merged', 'related', 'dismissed', 'fixed')),
    resolved_by      TEXT REFERENCES users (user_id),
    resolved_at      TEXT,
    CHECK ((type = 'unit_mismatch') = (b_definition_id IS NULL)),
    CHECK ((status = 'open') = (resolved_at IS NULL)),
    CHECK (resolved_by IS NULL OR resolved_at IS NOT NULL)
);

-- Indexes for the lookups the app does most.
CREATE INDEX definitions_kpi ON definitions (kpi_id);
CREATE INDEX definitions_division_status ON definitions (division_id, status);
CREATE INDEX reviews_definition ON reviews (definition_id);
CREATE INDEX definition_tags_tag ON definition_tags (tag_id);
CREATE INDEX kpi_relationships_from ON kpi_relationships (from_definition_id);
CREATE INDEX kpi_relationships_to ON kpi_relationships (to_definition_id);
