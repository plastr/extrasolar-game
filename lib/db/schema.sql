
-- ****************************************************************************
-- **  This file is generated -- if you want to change the                   **
-- **  schema, add a migration in the migrations directory                   **
-- ****************************************************************************
-- Naming style:
--   * use plural nouns  (e.g. 'users')
--   * compound tables (where you have a second table that just adds columns to
--   the first, such as users_password) should have the plural on the "core"
--   table name
--   * 'noun_id' is always the column name for an id for some noun, even in 
--     its own table
--   * any user-viewable text should be in UTF-8
--
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `_yoyo_migration`
--
DROP TABLE IF EXISTS _yoyo_migration;
CREATE TABLE _yoyo_migration (
  id varchar(255) NOT NULL,
  ctime timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `achievements`
--
DROP TABLE IF EXISTS achievements;
CREATE TABLE achievements (
  user_id binary(16) NOT NULL,
  achievement_key char(32) NOT NULL,
  achieved_at int(10) unsigned NOT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,achievement_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `capabilities`
--
DROP TABLE IF EXISTS capabilities;
CREATE TABLE capabilities (
  user_id binary(16) NOT NULL,
  capability_key char(32) NOT NULL,
  uses int(10) unsigned NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  PRIMARY KEY (user_id,capability_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `chips`
--
DROP TABLE IF EXISTS chips;
CREATE TABLE chips (
  user_id binary(16) NOT NULL,
  transient tinyint(1) NOT NULL DEFAULT '1',
  content blob NOT NULL,
  seq bigint(20) NOT NULL AUTO_INCREMENT,
  `time` bigint(20) unsigned NOT NULL,
  PRIMARY KEY (seq),
  KEY user_id_time (user_id,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `deferred`
--
DROP TABLE IF EXISTS deferred;
CREATE TABLE deferred (
  deferred_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  deferred_type char(32) NOT NULL,
  subtype char(32) NOT NULL,
  run_at datetime NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payload varchar(1024) DEFAULT NULL,
  PRIMARY KEY (deferred_id),
  KEY user_id_deferred_type (user_id,deferred_type,subtype)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `edmodo_groups`
--
DROP TABLE IF EXISTS edmodo_groups;
CREATE TABLE edmodo_groups (
  group_id bigint(10) NOT NULL,
  sandbox tinyint(1) NOT NULL DEFAULT '0',
  created datetime NOT NULL,
  PRIMARY KEY (group_id),
  UNIQUE KEY group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `email_queue`
--
DROP TABLE IF EXISTS email_queue;
CREATE TABLE email_queue (
  queue_id binary(16) NOT NULL,
  email_from varchar(255) NOT NULL,
  email_to varchar(255) NOT NULL,
  email_subject varchar(1024) NOT NULL,
  body_html text NOT NULL,
  created datetime NOT NULL,
  PRIMARY KEY (queue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `gifts`
--
DROP TABLE IF EXISTS gifts;
CREATE TABLE gifts (
  gift_id binary(16) NOT NULL,
  gift_type char(32) NOT NULL,
  creator_id binary(16) NOT NULL,
  redeemer_id binary(16) DEFAULT NULL,
  annotation varchar(127) NOT NULL,
  created datetime NOT NULL,
  redeemed_at datetime DEFAULT NULL,
  campaign_name varchar(127) DEFAULT NULL,
  PRIMARY KEY (creator_id,gift_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `highlighted_targets`
--
DROP TABLE IF EXISTS highlighted_targets;
CREATE TABLE highlighted_targets (
  target_id binary(16) NOT NULL,
  available_at datetime NOT NULL,
  highlighted_at datetime NOT NULL,
  PRIMARY KEY (target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `invitation_gifts`
--
DROP TABLE IF EXISTS invitation_gifts;
CREATE TABLE invitation_gifts (
  invite_id binary(16) NOT NULL,
  gift_id binary(16) NOT NULL,
  PRIMARY KEY (invite_id,gift_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `invitations`
--
DROP TABLE IF EXISTS invitations;
CREATE TABLE invitations (
  invite_id binary(16) NOT NULL,
  sender_id binary(16) NOT NULL,
  recipient_id binary(16) DEFAULT NULL,
  recipient_email varchar(255) NOT NULL,
  recipient_first_name varchar(127) NOT NULL,
  recipient_last_name varchar(127) NOT NULL,
  sent_at datetime NOT NULL,
  accepted_at datetime DEFAULT NULL,
  campaign_name varchar(127) DEFAULT NULL,
  PRIMARY KEY (sender_id,invite_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `invoices`
--
DROP TABLE IF EXISTS invoices;
CREATE TABLE invoices (
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  currency char(8) DEFAULT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_current_email varchar(255) NOT NULL,
  PRIMARY KEY (user_id,invoice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `landers`
--
DROP TABLE IF EXISTS landers;
CREATE TABLE landers (
  lander_id binary(16) NOT NULL,
  lat double NOT NULL,
  lng double NOT NULL,
  PRIMARY KEY (lander_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `messages`
--
DROP TABLE IF EXISTS messages;
CREATE TABLE messages (
  message_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  msg_type char(32) NOT NULL,
  sent_at int(10) unsigned NOT NULL,
  read_at int(10) unsigned DEFAULT NULL,
  locked tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (message_id,user_id),
  UNIQUE KEY user_id_msg_type (user_id,msg_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `missions`
--
-- This table contains the active missions for a user.  Note that the 
    -- specifics column is for configuring generic missions for the user's 
    -- specific needs, and is just a blob.  The specifics_hash column should 
    -- be populated with the hash of the specifics column as the name implies;
    -- it's there so that the user can't do the exact same mission twice.
--
DROP TABLE IF EXISTS missions;
CREATE TABLE missions (
  user_id binary(16) NOT NULL,
  mission_definition char(32) NOT NULL,
  specifics_hash char(32) NOT NULL DEFAULT '',
  specifics varchar(1024) NOT NULL,
  done tinyint(1) NOT NULL DEFAULT '0',
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  started_at int(10) unsigned NOT NULL,
  parent_hash char(32) NOT NULL DEFAULT '',
  done_at int(10) unsigned DEFAULT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,mission_definition,specifics_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `purchased_products`
--
DROP TABLE IF EXISTS purchased_products;
CREATE TABLE purchased_products (
  product_id binary(16) NOT NULL,
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  product_key char(32) NOT NULL,
  price int(10) unsigned NOT NULL,
  currency char(8) NOT NULL,
  purchased_at int(10) unsigned NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `rovers`
--
-- This table contains the rovers
--
DROP TABLE IF EXISTS rovers;
CREATE TABLE rovers (
  rover_id binary(16) NOT NULL,
  user_id binary(16) DEFAULT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  active tinyint(4) NOT NULL DEFAULT '1',
  lander_id binary(16) NOT NULL,
  rover_key char(32) NOT NULL,
  activated_at int(10) unsigned NOT NULL,
  PRIMARY KEY (rover_id),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `species`
--
DROP TABLE IF EXISTS species;
CREATE TABLE species (
  user_id binary(16) NOT NULL,
  species_id int(10) unsigned NOT NULL DEFAULT '0',
  detected_at int(10) unsigned NOT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (user_id,species_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `target_image_rects`
--
DROP TABLE IF EXISTS target_image_rects;
CREATE TABLE target_image_rects (
  xmin double NOT NULL,
  ymin double NOT NULL,
  xmax double NOT NULL,
  ymax double NOT NULL,
  density double DEFAULT NULL,
  target_id binary(16) NOT NULL,
  species_id int(10) unsigned DEFAULT NULL,
  seq int(11) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  subspecies_id int(10) unsigned DEFAULT NULL,
  user_id binary(16) NOT NULL,
  PRIMARY KEY (target_id,seq),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `target_images`
--
DROP TABLE IF EXISTS target_images;
CREATE TABLE target_images (
  `type` varchar(20) NOT NULL DEFAULT '',
  url varchar(256) NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  target_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  PRIMARY KEY (target_id,`type`),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `target_metadata`
--
DROP TABLE IF EXISTS target_metadata;
CREATE TABLE target_metadata (
  target_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id binary(16) NOT NULL,
  PRIMARY KEY (target_id,`key`),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `target_sounds`
--
DROP TABLE IF EXISTS target_sounds;
CREATE TABLE target_sounds (
  sound_key char(32) NOT NULL,
  target_id binary(16) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id binary(16) NOT NULL,
  PRIMARY KEY (target_id,sound_key),
  KEY user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `targets`
--
-- This table contains the user-specified rover target positions
--
DROP TABLE IF EXISTS targets;
CREATE TABLE targets (
  rover_id binary(16) NOT NULL,
  seq int(10) unsigned NOT NULL DEFAULT '0',
  lat double NOT NULL,
  lng double NOT NULL,
  arrival_time int(10) unsigned NOT NULL,
  yaw double NOT NULL,
  pitch double NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  processed tinyint(1) NOT NULL DEFAULT '0',
  picture tinyint(1) NOT NULL DEFAULT '0',
  target_id binary(16) NOT NULL,
  start_time int(10) unsigned NOT NULL,
  locked_at datetime DEFAULT NULL,
  viewed_at int(10) unsigned DEFAULT NULL,
  classified tinyint(1) NOT NULL DEFAULT '0',
  highlighted tinyint(1) NOT NULL DEFAULT '0',
  user_id binary(16) NOT NULL,
  user_created tinyint(1) NOT NULL DEFAULT '0',
  neutered tinyint(1) NOT NULL DEFAULT '0',
  render_at datetime NOT NULL,
  PRIMARY KEY (rover_id,arrival_time,seq),
  UNIQUE KEY target_id (target_id),
  KEY lat (lat),
  KEY lng (lng),
  KEY time_picture (arrival_time,picture),
  KEY user_id (user_id),
  KEY rover_id (rover_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `transaction_gateway_data`
--
DROP TABLE IF EXISTS transaction_gateway_data;
CREATE TABLE transaction_gateway_data (
  transaction_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  PRIMARY KEY (transaction_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `transactions`
--
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
  transaction_id binary(16) NOT NULL,
  invoice_id binary(16) NOT NULL,
  user_id binary(16) NOT NULL,
  transaction_type char(32) NOT NULL,
  amount int(10) unsigned NOT NULL,
  currency char(8) NOT NULL,
  gateway_type char(32) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (invoice_id,transaction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `user_map_tiles`
--
DROP TABLE IF EXISTS user_map_tiles;
CREATE TABLE user_map_tiles (
  user_id binary(16) NOT NULL,
  zoom int(3) NOT NULL,
  x bigint(20) NOT NULL,
  y bigint(20) NOT NULL,
  arrival_time int(10) unsigned NOT NULL,
  expiry_time datetime DEFAULT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  PRIMARY KEY (user_id,zoom,x,y,arrival_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users`
--
-- The users table is simply an indirection table and only really
    -- exists to collate ids from the various methods of authorization.
    -- Because the character set is latin1, don't put any user-visible
    -- data in here; use another table
--
DROP TABLE IF EXISTS users;
CREATE TABLE users (
  user_id binary(16) NOT NULL,
  authentication char(5) NOT NULL,
  dev tinyint(4) NOT NULL DEFAULT '0',
  email varchar(255) DEFAULT NULL,
  first_name varchar(127) NOT NULL,
  last_name varchar(127) NOT NULL,
  updated timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created datetime NOT NULL,
  valid tinyint(4) NOT NULL DEFAULT '0',
  epoch datetime NOT NULL,
  last_accessed datetime NOT NULL,
  viewed_alerts_at int(10) unsigned DEFAULT NULL,
  inviter_id binary(16) DEFAULT NULL,
  invites_left int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (user_id),
  UNIQUE KEY email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_edmodo`
--
DROP TABLE IF EXISTS users_edmodo;
CREATE TABLE users_edmodo (
  user_id binary(16) NOT NULL,
  uid bigint(20) NOT NULL,
  user_type varchar(15) NOT NULL,
  access_token varchar(31) NOT NULL,
  user_token varchar(31) NOT NULL,
  sandbox tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (user_id),
  UNIQUE KEY uid (uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_facebook`
--
DROP TABLE IF EXISTS users_facebook;
CREATE TABLE users_facebook (
  user_id binary(16) NOT NULL,
  uid bigint(20) NOT NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY uid (uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_metadata`
--
DROP TABLE IF EXISTS users_metadata;
CREATE TABLE users_metadata (
  user_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_notification`
--
DROP TABLE IF EXISTS users_notification;
CREATE TABLE users_notification (
  user_id binary(16) NOT NULL,
  wants_activity_alert tinyint(1) NOT NULL DEFAULT '0',
  activity_alert_window_start datetime DEFAULT NULL,
  activity_alert_last_sent datetime DEFAULT NULL,
  activity_alert_frequency char(32) NOT NULL,
  lure_alert_last_checked datetime DEFAULT NULL,
  wants_news_alert tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_password`
--
-- This table contains the usernames and passwords of users that signed up
    -- via the password auth stuff
--
DROP TABLE IF EXISTS users_password;
CREATE TABLE users_password (
  user_id binary(16) NOT NULL,
  `password` varchar(128) NOT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_progress`
--
DROP TABLE IF EXISTS users_progress;
CREATE TABLE users_progress (
  user_id binary(16) NOT NULL,
  `key` char(32) NOT NULL,
  `value` varchar(1024) NOT NULL,
  achieved_at int(10) unsigned NOT NULL,
  PRIMARY KEY (user_id,`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `users_shop`
--
DROP TABLE IF EXISTS users_shop;
CREATE TABLE users_shop (
  user_id binary(16) NOT NULL,
  stripe_customer_id char(32) DEFAULT NULL,
  stripe_customer_data varchar(1024) DEFAULT NULL,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Table structure for table `vouchers`
--
DROP TABLE IF EXISTS vouchers;
CREATE TABLE vouchers (
  user_id binary(16) NOT NULL,
  voucher_key char(32) NOT NULL,
  delivered_at int(10) unsigned NOT NULL,
  created timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id,voucher_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;


/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

LOCK TABLES _yoyo_migration WRITE;
/*!40000 ALTER TABLE _yoyo_migration DISABLE KEYS */;
INSERT INTO _yoyo_migration VALUES ('2013-09-27-01-baseline',NOW()),('2013-10-07-01-modify_target_tables_add_user_id',NOW()),('2013-10-15-01-modify_targets_add_user_created',NOW()),('2013-10-15-02-modify_targets_add_neutered',NOW()),('2013-10-23-01-fix_user_map_tiles_expiry_time',NOW()),('2013-10-29-01-modify_gifts_invitations_add_campaign_name',NOW()),('2013-10-31-01-modify_rovers_add_rover_key_and_activated_at',NOW()),('2013-11-19-01-add_progress_key_enable_nw_region',NOW()),('2013-11-20-01-deferred_target_arrived_to_target_id_subtype',NOW()),('2013-11-21-01-modify_targets_add_render_at',NOW()),('2013-12-13-01-modify_playback_mission',NOW()),('2014-01-06-01-add_invitations',NOW()),('2014-01-15-01-modify_users_notification_add_lure',NOW()),('2014-01-15-02-modify_users_notification_rename_frequencies',NOW()),('2014-01-28-01-add_progress_key_tagged_one_obelisk',NOW()),('2014-02-14-01-add_email_queue',NOW()),('2014-06-04-01-add_users_facebook',NOW()),('2014-06-11-01-modify_users_allow_null_email',NOW()),('2014-06-19-01-add_users_edmodo',NOW()),('2014-06-25-01-modify_users_edmodo_add_user_type',NOW()),('2014-08-06-01-modify_users_edmodo_add_access_token_and_sandbox',NOW()),('2014-08-08-01-add_edmodo_groups',NOW());
/*!40000 ALTER TABLE _yoyo_migration ENABLE KEYS */;
UNLOCK TABLES;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;


