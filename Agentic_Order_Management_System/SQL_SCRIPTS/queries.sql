-- i want to order Data science Handbook

SELECT sku, product_name, brand, price, quantity_available FROM Inventory WHERE status='ACTIVE' AND

(product_name LIKE '%Data Science Handbook%' OR CONCAT(brand,' ',product_name) LIKE '%Data Science Handbook%');

SELECT sku, product_name, brand, price, quantity_available FROM Inventory WHERE status='active' AND brand LIKE '%Samsung%';

SELECT sku, product_name, brand, price, quantity_available
FROM Inventory
WHERE status = 'active' AND product_name LIKE '%Women\'s Jacket WinterPro%';

SELECT order_number, status, total_price FROM Orders WHERE order_number = 'ORD-7D31E6DE';

DESC Orders;
SELECT sku, product_name, brand, price, quantity_available FROM Inventory WHERE status='active' AND product_name LIKE '%Robot Vacuum Cleaner%';
