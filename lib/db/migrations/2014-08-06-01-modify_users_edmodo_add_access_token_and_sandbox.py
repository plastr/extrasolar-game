forward = """
ALTER TABLE users_edmodo ADD COLUMN access_token varchar(31) NOT NULL;
ALTER TABLE users_edmodo ADD COLUMN user_token varchar(31) NOT NULL;
ALTER TABLE users_edmodo ADD COLUMN sandbox tinyint(1) NOT NULL DEFAULT '0';
UPDATE users_edmodo SET access_token='INVALID_TOKEN';
UPDATE users_edmodo SET user_token='INVALID_TOKEN';
"""
reverse = """
ALTER TABLE users_edmodo DROP COLUMN access_token;
ALTER TABLE users_edmodo DROP COLUMN user_token;
ALTER TABLE users_edmodo DROP COLUMN sandbox;
"""
step(forward, reverse)
