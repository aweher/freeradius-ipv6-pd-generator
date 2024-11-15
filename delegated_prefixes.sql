CREATE TABLE `delegated_prefixes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `delegated_prefix` varchar(255) NOT NULL,
  `assigned_date` date NOT NULL,
  `revoked_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `delegated_prefix` (`delegated_prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;