-- PostgreSQL initialization script for CompanyCam Photo Detection
-- This script sets up required extensions and initial database configuration

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for additional cryptographic functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Note: JSONB support is built-in to PostgreSQL 9.4+, no extension needed

-- Create application-specific schema (optional, using public for now)
-- CREATE SCHEMA IF NOT EXISTS companycam;

-- Grant permissions to application user
GRANT ALL PRIVILEGES ON DATABASE companycam_detection TO companycam;
GRANT ALL PRIVILEGES ON SCHEMA public TO companycam;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO companycam;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO companycam;

-- Create roles for row-level security
CREATE ROLE org_admin;
CREATE ROLE org_user;

-- Grant basic permissions to roles
GRANT CONNECT ON DATABASE companycam_detection TO org_admin;
GRANT CONNECT ON DATABASE companycam_detection TO org_user;

-- Initial setup complete
SELECT 'Database initialization completed successfully' AS status;
