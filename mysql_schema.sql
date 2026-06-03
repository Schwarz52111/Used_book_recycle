CREATE DATABASE IF NOT EXISTS used_book_recycle
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE used_book_recycle;

CREATE TABLE IF NOT EXISTS books (
    id INT AUTO_INCREMENT PRIMARY KEY,
    isbn VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    publisher VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    original_price DECIMAL(10, 2) NOT NULL,
    market_price DECIMAL(10, 2) NOT NULL,
    base_recycle_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.35,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS condition_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    condition_level VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL,
    price_factor DECIMAL(5, 2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS recycle_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    book_id INT NOT NULL,
    condition_level VARCHAR(50) NOT NULL,
    damage_score DECIMAL(6, 4) NOT NULL,
    completeness_score DECIMAL(6, 4) NOT NULL,
    evaluated_price DECIMAL(10, 2) NOT NULL,
    recognized_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recycle_records_book
        FOREIGN KEY (book_id) REFERENCES books(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
