-- Database initialization script for Phishing Simulation Platform
-- This script runs when the PostgreSQL container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_campaign_targets_campaign_id ON campaign_targets(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_target_id ON campaign_targets(target_id);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_unique_token ON campaign_targets(unique_token);
CREATE INDEX IF NOT EXISTS idx_email_events_campaign_target_id ON email_events(campaign_target_id);
CREATE INDEX IF NOT EXISTS idx_email_events_timestamp ON email_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_email_events_event_type ON email_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

-- Create user for the application
-- Note: This user is created by Docker, but we ensure proper permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO phishuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO phishuser;

-- Set default permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO phishuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO phishuser;