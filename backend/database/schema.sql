-- Database Schema
-- ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md

-- Example table - customize for your project
CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_examples_name ON examples(name);
CREATE INDEX IF NOT EXISTS idx_examples_created_at ON examples(created_at);

-- Add more tables as needed for your project




