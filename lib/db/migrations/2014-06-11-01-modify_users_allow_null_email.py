forward = """
ALTER TABLE users MODIFY email varchar(255) NULL DEFAULT NULL;
"""
reverse = """
ALTER TABLE users MODIFY email varchar(255) NOT NULL;
"""
step(forward, reverse)
