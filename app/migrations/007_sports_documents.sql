CREATE TABLE sports_documents (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    run_card_number TEXT NOT NULL DEFAULT '',
    run_card_expiry TEXT,
    medical_certificate_expiry TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO sports_documents (id) VALUES (1);
