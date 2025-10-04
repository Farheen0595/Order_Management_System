CREATE DATABASE Order_Management_System;

USE Order_Management_System;

-- ===== 1. USER SESSIONS TABLE =====
CREATE TABLE IF NOT EXISTS UserSessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_name VARCHAR(255) DEFAULT 'Guest User',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    status ENUM('ACTIVE', 'EXPIRED') DEFAULT 'ACTIVE'
);

-- ===== 2. INVENTORY TABLE =====

CREATE TABLE IF NOT EXISTS Inventory (
    sku VARCHAR(50) PRIMARY KEY,          
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,
    brand VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    quantity_available INT NOT NULL,
    reserved_quantity INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    warehouse_location VARCHAR(255) NOT NULL DEFAULT 'WH-A2',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
);


-- ===== 3. SHOPPING CART TABLE =====
-- When user checks out, all SKUs from this cart will be copied into Orders with the same order_number.
CREATE TABLE IF NOT EXISTS ShoppingCart (
    cart_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    price_when_added DECIMAL(10,2) NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES UserSessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES Inventory(sku) ON DELETE CASCADE,
    UNIQUE KEY unique_session_sku (session_id, sku)
);

-- ===== 4. ORDERS TABLE =====
CREATE TABLE IF NOT EXISTS Orders (
    id INT AUTO_INCREMENT PRIMARY KEY,     
    order_number VARCHAR(50) NOT NULL,     
    session_id VARCHAR(255) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    status ENUM('PENDING','PLACED','CANCELLED','COMPLETED') DEFAULT 'PENDING',
    remarks VARCHAR(255),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES UserSessions(session_id),
    FOREIGN KEY (sku) REFERENCES Inventory(sku)
);


-- ===== 5. INVENTORY AUDIT TABLE =====
CREATE TABLE IF NOT EXISTS InventoryAudit (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    change_type VARCHAR(20) NOT NULL,   
    quantity_changed INT NOT NULL,
    previous_available INT NOT NULL,
    new_available INT NOT NULL,
    previous_reserved INT NOT NULL DEFAULT 0,
    new_reserved INT NOT NULL DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reference_type VARCHAR(20),         
    reference_id VARCHAR(50),           
    session_id VARCHAR(255),
    remarks VARCHAR(255),
    FOREIGN KEY (sku) REFERENCES Inventory(sku) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES UserSessions(session_id) ON DELETE SET NULL
);

-- ===== 6. ORDER AUDIT TABLE =====
CREATE TABLE IF NOT EXISTS OrderAudit (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,                  
    order_number VARCHAR(50) NOT NULL,       
    sku VARCHAR(50) NOT NULL,
    previous_status VARCHAR(20) NOT NULL,
    new_status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remarks VARCHAR(255),
    FOREIGN KEY (order_id) REFERENCES Orders(id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES Inventory(sku) ON DELETE CASCADE
);




-- ===== VERIFY TABLE CREATION =====
SHOW TABLES;

-- ===== CHECK TABLE STRUCTURES =====
DESCRIBE UserSessions;
DESCRIBE Inventory;
DESCRIBE ShoppingCart;
DESCRIBE Orders;
DESCRIBE OrderItems;
DESCRIBE InventoryAudit;
DESCRIBE OrderAudit;


SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE OrderAudit;
TRUNCATE TABLE InventoryAudit;
TRUNCATE TABLE Orders;
TRUNCATE TABLE ShoppingCart;
TRUNCATE TABLE Inventory;
TRUNCATE TABLE UserSessions;

SET FOREIGN_KEY_CHECKS = 1;

























