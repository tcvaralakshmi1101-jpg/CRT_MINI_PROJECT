CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS patients (
    id                    UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                  VARCHAR(100) NOT NULL CHECK (char_length(trim(name)) > 0),
    age                   SMALLINT    NOT NULL CHECK (age >= 1 AND age <= 120),
    gender                VARCHAR(10) NOT NULL CHECK (gender IN ('Male','Female','Other')),
    condition             TEXT        NOT NULL CHECK (char_length(trim(condition)) > 0),
    priority              SMALLINT    NOT NULL CHECK (priority >= 1 AND priority <= 5),
    priority_label        VARCHAR(10) NOT NULL,
    ai_suggested_priority SMALLINT    NOT NULL DEFAULT 0,
    ai_reasoning          TEXT        NOT NULL DEFAULT '',
    arrival_time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                VARCHAR(10) NOT NULL DEFAULT 'waiting'
                          CHECK (status IN ('waiting','admitted','removed')),
    admitted_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_patients_status   ON patients(status);
CREATE INDEX IF NOT EXISTS idx_patients_priority ON patients(priority DESC);
CREATE INDEX IF NOT EXISTS idx_patients_arrival  ON patients(arrival_time);

CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL      PRIMARY KEY,
    patient_id  UUID        REFERENCES patients(id) ON DELETE SET NULL,
    action      VARCHAR(20) NOT NULL,
    old_priority SMALLINT,
    new_priority SMALLINT,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes       TEXT
);
