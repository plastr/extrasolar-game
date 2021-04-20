forward = """
ALTER TABLE targets ADD COLUMN neutered tinyint(1) NOT NULL DEFAULT '0';
"""
reverse = """
ALTER TABLE targets DROP COLUMN neutered;
"""
step(forward, reverse)
