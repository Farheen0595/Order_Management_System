SHOW databases;

CREATE DATABASE order_mg_sys;

USE order_mg_sys;

-- Inventory Table
CREATE TABLE IF NOT EXISTS Inventory(
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,
    brand VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity_available INT NOT NULL,
    reorder_level INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    warehouse_location VARCHAR(255) NOT NULL DEFAULT 'WH-A2',
    status VARCHAR(20) NOT NULL
);

-- Inventory Audit
CREATE TABLE IF NOT EXISTS InventoryAudit(
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    quantity_available INT NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    quantity_changed INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remarks VARCHAR(50),
    FOREIGN KEY (product_id)
        REFERENCES Inventory(product_id)
        ON DELETE CASCADE
);

-- Orders Table
CREATE TABLE IF NOT EXISTS Orders(
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PROCESSED',
    remarks VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id)
        REFERENCES Inventory(product_id)
        ON DELETE CASCADE
);

-- Order Audit Table
CREATE TABLE IF NOT EXISTS OrderAudit(
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    previous_status VARCHAR(20) NOT NULL,
    new_status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remarks VARCHAR(255),
    FOREIGN KEY (order_id)
        REFERENCES Orders(order_id)
        ON DELETE CASCADE
);

    
    
    
    
    
SELECT * FROM order_mg_sys.Inventory;

SELECT * FROM order_mg_sys.Inventory WHERE Inventory.product_name LIKE '%Air%';

SELECT o.order_id, i.product_id, product_name FROM Inventory i 

JOIN Orders o WHERE i.product_id = o.product_id;

INSERT INTO Orders (product_id, quantity, status, remarks)
VALUES
(1, 2, 'PROCESSED', 'First test order');

SELECT product_id, product_name, price, quantity_available FROM Inventory
 WHERE brand LIKE '%Samsung%' AND product_name LIKE '%Smart LED TV%' AND status='active';


SELECT product_id, product_name, price, quantity_available FROM Inventory 
WHERE status='active' AND ((brand LIKE '%Apple%' AND product_name LIKE '%Apple Smartphone X15%') 
OR (product_name LIKE '%Apple%') OR (brand LIKE '%Apple Smartphone X15%') );

SELECT product_id, product_name, price, quantity_available FROM Inventory 
WHERE status='active' AND (brand LIKE '%Samsung%' AND product_name LIKE '%Smart LED TV%');

SELECT product_id, product_name, price, quantity_available FROM Inventory
 WHERE status='active' AND brand LIKE '%Apple%' AND product_name LIKE '%Smartphone X15%';
 
 SELECT product_id, product_name, price, quantity_available FROM Inventory WHERE status='active' AND product_name LIKE '%wireless headphones%';
 
 SELECT product_id, product_name, price, quantity_available FROM Inventory WHERE status='active' AND product_name LIKE '%Smartphone X15%';
 
 SELECT product_id, product_name, price, quantity_available FROM Inventory WHERE status='active' AND product_name LIKE '%wireless%' AND product_name LIKE '%headphones%';

 
SELECT product_id, product_name, brand, price, quantity_available FROM Inventory WHERE status='active' AND brand LIKE '%Samsung%' AND product_name LIKE '%Smart LED TV%';


SELECT product_id, product_name, brand, price, quantity_available
FROM Inventory
WHERE status = 'active' AND product_name LIKE '%smartphone x15%';

SELECT product_id, product_name, brand, price, quantity_available FROM Inventory WHERE status='active' AND brand LIKE '%Samsung%' AND product_name LIKE '%Smart LED TV%';

SELECT product_id, product_name, brand, price, quantity_available
FROM Inventory
WHERE status = 'active'
  AND product_name LIKE '%wireless%'
  AND product_name LIKE '%headphones%';
  
  SELECT product_id, product_name, brand, price, quantity_available FROM Inventory 
  WHERE status='active' AND brand LIKE '%Samsung%' AND product_name LIKE '%Smart LED TV%';


