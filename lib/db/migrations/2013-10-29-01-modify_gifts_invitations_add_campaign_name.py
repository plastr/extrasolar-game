forward = """
ALTER TABLE invitations ADD COLUMN campaign_name varchar(127) DEFAULT NULL;
ALTER TABLE gifts ADD COLUMN campaign_name varchar(127) DEFAULT NULL;
"""
reverse = """
ALTER TABLE invitations DROP COLUMN campaign_name;
ALTER TABLE gifts DROP COLUMN campaign_name;
"""
step(forward, reverse)
