forward = """
ALTER TABLE users_notification CHANGE wants_notification wants_activity_alert tinyint(1) NOT NULL DEFAULT '0';
ALTER TABLE users_notification CHANGE digest_window_start activity_alert_window_start datetime DEFAULT NULL;
ALTER TABLE users_notification CHANGE digest_last_sent activity_alert_last_sent datetime DEFAULT NULL;
ALTER TABLE users_notification CHANGE frequency activity_alert_frequency char(32) NOT NULL;

ALTER TABLE users_notification ADD COLUMN lure_alert_last_checked datetime DEFAULT NULL;
ALTER TABLE users_notification ADD COLUMN wants_news_alert tinyint(1) NOT NULL DEFAULT '0';
"""
reverse = """
ALTER TABLE users_notification CHANGE wants_activity_alert wants_notification tinyint(1) NOT NULL DEFAULT '0';
ALTER TABLE users_notification CHANGE activity_alert_window_start digest_window_start datetime DEFAULT NULL;
ALTER TABLE users_notification CHANGE activity_alert_last_sent digest_last_sent datetime DEFAULT NULL;
ALTER TABLE users_notification CHANGE activity_alert_frequency frequency char(32) NOT NULL;

ALTER TABLE users_notification DROP COLUMN lure_alert_last_checked;
ALTER TABLE users_notification DROP COLUMN wants_news_alert;
"""
step(forward, reverse)
