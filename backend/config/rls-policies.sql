-- Row-Level Security (RLS) Policies for Multi-Tenant Data Isolation
-- This script sets up row-level security to ensure users can only access
-- data from their own organization

-- Enable Row-Level Security on all multi-tenant tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE detections ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;

-- Create a function to get the current user's organization_id
-- This would typically be set by the application layer based on the authenticated user
CREATE OR REPLACE FUNCTION current_user_organization_id()
RETURNS UUID AS $$
BEGIN
    -- This function would be implemented to retrieve the organization_id
    -- from the current session context. For now, it's a placeholder.
    -- In production, use SET LOCAL to set this per transaction
    RETURN current_setting('app.current_organization_id', TRUE)::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Users table RLS policies
CREATE POLICY users_isolation_policy ON users
    FOR ALL
    USING (organization_id = current_user_organization_id());

-- Projects table RLS policies
CREATE POLICY projects_isolation_policy ON projects
    FOR ALL
    USING (organization_id = current_user_organization_id());

-- Photos table RLS policies
-- Users can only see photos from projects in their organization
CREATE POLICY photos_isolation_policy ON photos
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE organization_id = current_user_organization_id()
        )
    );

-- Detections table RLS policies
-- Users can only see detections for photos from their organization
CREATE POLICY detections_isolation_policy ON detections
    FOR ALL
    USING (
        photo_id IN (
            SELECT p.id FROM photos p
            JOIN projects pr ON p.project_id = pr.id
            WHERE pr.organization_id = current_user_organization_id()
        )
    );

-- Tags table RLS policies
-- Users can only see tags for photos from their organization
CREATE POLICY tags_isolation_policy ON tags
    FOR ALL
    USING (
        photo_id IN (
            SELECT p.id FROM photos p
            JOIN projects pr ON p.project_id = pr.id
            WHERE pr.organization_id = current_user_organization_id()
        )
    );

-- Grant usage on the function to application roles
GRANT EXECUTE ON FUNCTION current_user_organization_id() TO org_admin;
GRANT EXECUTE ON FUNCTION current_user_organization_id() TO org_user;

-- Documentation and usage notes:
--
-- To use RLS in application code, set the organization_id at the start of each transaction:
--
-- Example in Python/SQLAlchemy:
--   await session.execute(
--       text("SET LOCAL app.current_organization_id = :org_id"),
--       {"org_id": str(user.organization_id)}
--   )
--
-- This ensures all subsequent queries in that transaction are filtered by organization.
--
-- To bypass RLS for admin operations (use carefully):
--   ALTER TABLE table_name DISABLE ROW LEVEL SECURITY;
--   -- or --
--   SET SESSION session_replication_role = 'replica';
