-- CspoE is developped and maintained by BreizhStakePool.io 
--
-- Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
-- Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
-- donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
--
-- Consider delegate your voting power to our Breizh DRep [BZH] 
-- drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: localhost    Database: test_DB
-- ------------------------------------------------------
-- Server version	8.0.46-0ubuntu0.22.04.3

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `assets`
--

DROP TABLE IF EXISTS `assets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `assets` (
  `epoch_epoch_number` int NOT NULL,
  `delegator_stake_address` varchar(128) NOT NULL,
  `name` varchar(64) NOT NULL,
  `amount` int NOT NULL DEFAULT '0',
  `policyID` varchar(64) NOT NULL,
  `name_hash` varchar(64) NOT NULL,
  `fingerprint` varchar(64) NOT NULL,
  PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`,`fingerprint`) USING BTREE,
  KEY `fk_assets_epoch_idx` (`epoch_epoch_number`),
  KEY `fk_assets_delegator_idx` (`delegator_stake_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `blocks`
--

DROP TABLE IF EXISTS `blocks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `blocks` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `hash` varchar(64) NOT NULL,
  `height` bigint unsigned NOT NULL,
  `absolute_slot` bigint unsigned NOT NULL,
  `epoch_slot` bigint unsigned NOT NULL,
  `time` timestamp NOT NULL,
  `previous_block_hash` varchar(64) NOT NULL,
  `next_block_hash` varchar(64) NOT NULL,
  `tx_count` int unsigned NOT NULL,
  `fees` bigint unsigned NOT NULL,
  `value` bigint unsigned NOT NULL,
  PRIMARY KEY (`epoch_epoch_number`,`hash`),
  KEY `fk_blocks_epoch_idx` (`epoch_epoch_number`),
  CONSTRAINT `fk_blocks_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bonus`
--

DROP TABLE IF EXISTS `bonus`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `delegator_stake_address` varchar(128) NOT NULL,
  `amount` bigint unsigned DEFAULT '0',
  `sum` bigint unsigned DEFAULT '0',
  PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
  KEY `fk_bonus_epoch_idx` (`epoch_epoch_number`),
  KEY `fk_bonus_delegator_idx` (`delegator_stake_address`),
  CONSTRAINT `fk_bonus_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
  CONSTRAINT `fk_bonus_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `delegator`
--

DROP TABLE IF EXISTS `delegator`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `delegator` (
  `stake_address` varchar(128) NOT NULL,
  `first_epoch` int NOT NULL DEFAULT '0',
  `since_epoch` int unsigned DEFAULT '0',
  `gone_epoch` int unsigned DEFAULT '0',
  `epoch_count` int unsigned NOT NULL DEFAULT '1',
  `loyalty` decimal(10,2) unsigned DEFAULT '0.00',
  `comeback` tinyint NOT NULL DEFAULT '0',
  `comeback_count` int unsigned DEFAULT '0',
  `stake` bigint unsigned DEFAULT '0',
  `stake_sum` bigint unsigned DEFAULT '0',
  `stake_previous` bigint unsigned DEFAULT '0',
  `stake_diff` bigint DEFAULT '0',
  `inputs_sum` bigint unsigned DEFAULT '0',
  `outputs_sum` bigint DEFAULT '0',
  `stake_max` bigint unsigned DEFAULT '0',
  `stake_min` bigint unsigned DEFAULT '0',
  `rewards` bigint unsigned DEFAULT '0',
  `rewards_sum` bigint unsigned DEFAULT '0',
  `bonus` bigint unsigned DEFAULT '0',
  `bonus_sum` bigint unsigned DEFAULT '0',
  `ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_bonus_included` decimal(10,2) unsigned DEFAULT '0.00',
  PRIMARY KEY (`stake_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `epoch`
--

DROP TABLE IF EXISTS `epoch`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `epoch` (
  `epoch_number` int unsigned NOT NULL,
  `pool_stake` bigint unsigned DEFAULT '0',
  `pool_stake_previous` bigint unsigned DEFAULT '0',
  `pool_stake_sum` bigint unsigned DEFAULT '0',
  `pool_stake_diff` bigint DEFAULT '0',
  `pool_stake_inputs_sum` bigint unsigned DEFAULT '0',
  `pool_stake_outputs_sum` bigint DEFAULT '0',
  `pool_stake_max` bigint unsigned DEFAULT '0',
  `pool_stake_min` bigint unsigned DEFAULT '0',
  `biggest_single_owner_pledge` bigint unsigned DEFAULT '0',
  `biggest_single_delegator_stake` bigint unsigned DEFAULT '0',
  `pool_rewards` bigint unsigned DEFAULT '0',
  `pool_rewards_sum` bigint unsigned DEFAULT '0',
  `pool_ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `pool_ROA_max` decimal(10,2) unsigned DEFAULT NULL,
  `owners_nb` int unsigned NOT NULL DEFAULT '1',
  `pledge` bigint unsigned DEFAULT '0',
  `pledge_previous` bigint unsigned DEFAULT '0',
  `pledge_sum` bigint unsigned DEFAULT '0',
  `pledge_diff` bigint DEFAULT '0',
  `pledge_inputs_sum` bigint unsigned DEFAULT '0',
  `pledge_outputs_sum` bigint DEFAULT '0',
  `pledge_max` bigint unsigned DEFAULT '0',
  `pledge_min` bigint unsigned DEFAULT '0',
  `owners_rewards` bigint unsigned DEFAULT '0',
  `owners_rewards_sum` bigint unsigned DEFAULT '0',
  `owners_ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `owners_ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  `delegators_nb` int unsigned DEFAULT '0',
  `delegators_back_count` int unsigned DEFAULT '0',
  `delegators_back_sum` int unsigned DEFAULT '0',
  `delegators_lost_count` int unsigned DEFAULT '0',
  `delegators_lost_sum` int unsigned DEFAULT '0',
  `delegators_stake` bigint unsigned DEFAULT '0',
  `delegators_stake_previous` bigint unsigned DEFAULT '0',
  `delegators_stake_diff` bigint DEFAULT '0',
  `delegators_stake_sum` bigint unsigned DEFAULT '0',
  `delegators_stake_inputs_sum` bigint unsigned DEFAULT '0',
  `delegators_stake_outputs_sum` bigint DEFAULT '0',
  `delegators_stake_max` bigint unsigned DEFAULT '0',
  `delegators_stake_min` bigint unsigned DEFAULT '0',
  `delegators_lost_stake` bigint DEFAULT '0',
  `delegators_lost_stake_sum` bigint DEFAULT '0',
  `delegators_rewards` bigint unsigned DEFAULT '0',
  `delegators_rewards_sum` bigint unsigned DEFAULT '0',
  `delegators_ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `delegators_ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  `delegators_ROA_bonusincluded` decimal(10,2) unsigned DEFAULT '0.00',
  `blocks` int unsigned DEFAULT '0',
  `blocks_sum` int unsigned DEFAULT '0',
  `bonuses` bigint unsigned DEFAULT '0',
  `bonuses_sum` bigint unsigned DEFAULT '0',
  PRIMARY KEY (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gone_delegators`
--

DROP TABLE IF EXISTS `gone_delegators`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `gone_delegators` (
  `delegator_stake_address` varchar(128) NOT NULL,
  `epoch_epoch_number` int unsigned NOT NULL,
  `first_epoch` int unsigned NOT NULL DEFAULT '0',
  `since_epoch` int NOT NULL DEFAULT '0',
  `gone_count` int unsigned NOT NULL DEFAULT '1',
  `lost_stake` bigint NOT NULL DEFAULT '0',
  `back_count` int unsigned NOT NULL DEFAULT '0',
  `lost_stake_sum` bigint NOT NULL DEFAULT '0',
  PRIMARY KEY (`delegator_stake_address`,`epoch_epoch_number`,`back_count`) USING BTREE,
  KEY `fk_gone delegators_epoch1_idx` (`epoch_epoch_number`),
  KEY `fk_gone delegators_delegator1_idx` (`delegator_stake_address`),
  CONSTRAINT `fk_gone delegators_delegator1` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
  CONSTRAINT `fk_gone delegators_epoch1` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `owner`
--

DROP TABLE IF EXISTS `owner`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `owner` (
  `stake_address` varchar(128) NOT NULL,
  `since_epoch` int unsigned DEFAULT '0',
  `gone_epoch` int unsigned DEFAULT '0',
  `epoch_count` int unsigned DEFAULT '1',
  `loyalty` decimal(10,2) unsigned DEFAULT '0.00',
  `pledge` bigint unsigned DEFAULT '0',
  `pledge_sum` bigint unsigned DEFAULT '0',
  `pledge_previous` bigint unsigned DEFAULT '0',
  `pledge_diff` bigint DEFAULT NULL,
  `pledge_max` bigint unsigned DEFAULT '0',
  `pledge_min` bigint unsigned DEFAULT '0',
  `rewards` bigint unsigned DEFAULT '0',
  `rewards_sum` bigint unsigned DEFAULT '0',
  `inputs_sum` bigint unsigned DEFAULT '0',
  `outputs_sum` bigint DEFAULT '0',
  `ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  PRIMARY KEY (`stake_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `owner_rewards`
--

DROP TABLE IF EXISTS `owner_rewards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `owner_rewards` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `owner_stake_address` varchar(128) NOT NULL,
  `amount` bigint unsigned DEFAULT '0',
  `sum` bigint unsigned DEFAULT '0',
  PRIMARY KEY (`epoch_epoch_number`,`owner_stake_address`),
  KEY `fk_owner_rewards_epoch_idx` (`epoch_epoch_number`),
  KEY `fk_owner_rewards_owner_idx` (`owner_stake_address`),
  CONSTRAINT `fk_owner_rewards_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`),
  CONSTRAINT `fk_owner_rewards_owner` FOREIGN KEY (`owner_stake_address`) REFERENCES `owner` (`stake_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pledge`
--

DROP TABLE IF EXISTS `pledge`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pledge` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `owner_stake_address` varchar(128) NOT NULL,
  `amount` bigint unsigned DEFAULT '0',
  `sum` bigint unsigned DEFAULT '0',
  `previous` bigint unsigned DEFAULT '0',
  `diff` bigint DEFAULT '0',
  `inputs_sum` bigint unsigned DEFAULT '0',
  `outputs_sum` bigint DEFAULT '0',
  `max` bigint unsigned DEFAULT '0',
  `min` bigint unsigned DEFAULT '0',
  `ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  PRIMARY KEY (`epoch_epoch_number`,`owner_stake_address`),
  KEY `fk_pledge_epoch_idx` (`epoch_epoch_number`),
  KEY `fk_pledge_owner_idx` (`owner_stake_address`),
  CONSTRAINT `fk_pledge_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`),
  CONSTRAINT `fk_pledge_owner` FOREIGN KEY (`owner_stake_address`) REFERENCES `owner` (`stake_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `rewards`
--

DROP TABLE IF EXISTS `rewards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rewards` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `delegator_stake_address` varchar(128) NOT NULL,
  `amount` bigint unsigned DEFAULT '0',
  `sum` bigint unsigned DEFAULT '0',
  PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
  KEY `fk_rewards_delegator_idx` (`delegator_stake_address`),
  KEY `fk_rewards_epoch_idx` (`epoch_epoch_number`),
  CONSTRAINT `fk_rewards_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
  CONSTRAINT `fk_rewards_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `stake`
--

DROP TABLE IF EXISTS `stake`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stake` (
  `epoch_epoch_number` int unsigned NOT NULL,
  `delegator_stake_address` varchar(128) NOT NULL,
  `amount` bigint unsigned DEFAULT '0',
  `sum` bigint unsigned DEFAULT '0',
  `previous` bigint unsigned DEFAULT '0',
  `diff` bigint DEFAULT '0',
  `inputs_sum` bigint unsigned DEFAULT '0',
  `outputs_sum` bigint DEFAULT '0',
  `max` bigint unsigned DEFAULT '0',
  `min` bigint unsigned DEFAULT '0',
  `ROA_current` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_max` decimal(10,2) unsigned DEFAULT '0.00',
  `ROA_bonusincluded` decimal(10,2) unsigned DEFAULT '0.00',
  PRIMARY KEY (`epoch_epoch_number`,`delegator_stake_address`),
  KEY `fk_stake_delegator_idx` (`delegator_stake_address`),
  KEY `fk_stake_epoch_idx` (`epoch_epoch_number`),
  CONSTRAINT `fk_stake_delegator` FOREIGN KEY (`delegator_stake_address`) REFERENCES `delegator` (`stake_address`),
  CONSTRAINT `fk_stake_epoch` FOREIGN KEY (`epoch_epoch_number`) REFERENCES `epoch` (`epoch_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'test_DB'
--

--
-- Dumping routines for database 'test_DB'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-29 12:16:34
