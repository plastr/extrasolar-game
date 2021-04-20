forward = """
ALTER TABLE users_edmodo ADD COLUMN user_type varchar(15) NOT NULL;
UPDATE users_edmodo SET user_type='STUDENT';
"""
reverse = """
ALTER TABLE users_edmodo DROP user_type;
"""
step(forward, reverse)
