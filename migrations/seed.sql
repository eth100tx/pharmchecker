-- PharmChecker Development Seed Data
-- Optional seed data for development and testing

-- Insert test datasets
INSERT INTO datasets (kind, tag, description, created_by) VALUES
  ('pharmacies', 'dev_test', 'Development test pharmacy data', 'system'),
  ('states', 'dev_test', 'Development test state search data', 'system'),
  ('validated', 'dev_test', 'Development test validation data', 'system')
ON CONFLICT (kind, tag) DO NOTHING;

-- Insert test admin user for local development
INSERT INTO app_users (github_login, email, role, is_active) VALUES
  ('admin', 'admin@localhost', 'admin', true)
ON CONFLICT (email) DO NOTHING;