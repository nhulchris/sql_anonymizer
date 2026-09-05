-- ============================================================
-- ICS 499 SQL Data Anonymization Assignment - Original Test File
-- A small retail database with PII spread across four tables.
-- Deliberate test cases:
--   1. Repeated values: fturner@example.com appears in
--      customers, orders, and support_tickets (must map to the
--      SAME replacement everywhere).
--   2. Cross-table person: Julie Bullock is both a customer
--      and an employee (name/email/phone must stay consistent).
--   3. Varied PII column names: fname/last_name/full_name,
--      email/email_address/contact_email, phone/phone_number/
--      cell_phone, address/street_address/shipping_address.
--   4. Format variety: phones as (322) 938-9600, 934-387-4130,
--      3338874755, +1-894-432-7300.
--   5. Escaped quote inside a value: Christensen.
--   6. Multi-row INSERT syntax (customers) and single-row
--      INSERTs (employees).
--   7. Non-PII that must NOT change: product names, prices,
--      dates, order statuses, foreign keys, ticket text ids.
-- ============================================================

CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    fname VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    street_address VARCHAR(120),
    city VARCHAR(50),
    state CHAR(2),
    zip_code VARCHAR(10),
    loyalty_points INT
);

CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    full_name VARCHAR(100),
    email_address VARCHAR(100),
    cell_phone VARCHAR(20),
    home_address VARCHAR(200),
    department VARCHAR(50),
    hire_date DATE,
    salary DECIMAL(10,2)
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    contact_email VARCHAR(100),
    shipping_address VARCHAR(200),
    product_name VARCHAR(100),
    quantity INT,
    unit_price DECIMAL(8,2),
    order_date DATE,
    status VARCHAR(20),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE support_tickets (
    ticket_id INT PRIMARY KEY,
    customer_email VARCHAR(100),
    contact_phone VARCHAR(20),
    subject VARCHAR(200),
    opened_date DATE,
    resolved BOOLEAN
);

INSERT INTO customers (customer_id, fname, last_name, email, phone, street_address, city, state, zip_code, loyalty_points) VALUES
(1, 'Daniel', 'Christensen', 'fturner@example.com', '(322) 938-9600', '414 Frazier Throughway', 'Figueroaview', 'NV', '41373', 1250),
(2, 'Julie', 'Bullock', 'christopherhampton@example.org', '934-387-4130', '9332 Diaz Fall Suite 775', 'East Elizabethside', 'NV', '36839', 340),
(3, 'Jose', 'Lee', 'mitchellprice@example.net', '3338874755', '0986 Lester Rapids', 'Smithburgh', 'NV', '76070', 890),
(4, 'Shirley', 'Morgan', 'allenchristopher@example.org', '+1-894-432-7300', '2056 Dustin Mount', 'Calhounfort', 'NV', '27859', 60),
(5, 'Daniel', 'Mueller', 'vickicook@example.net', '(695) 882-9229', '14394 Christopher Turnpike Apt. 127', 'Lake Jonathan', 'NV', '25150', 15);

INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (101, 'Julie Bullock', 'christopherhampton@example.org', '934-387-4130', '9332 Diaz Fall Suite 775, East Elizabethside, NV 36839', 'Sales', '2023-04-17', 52000.00);
INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (102, 'Diana Jimenez', 'umorgan@example.net', '(411) 499-8846', '62115 Megan Inlet Suite 035, East Kevinchester, NV 33594', 'Warehouse', '2021-09-02', 47500.00);
INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (103, 'Megan Zamora', 'perezelizabeth@example.org', '451-887-9518', '12167 Winters Tunnel, Smithburgh, NV 13690', 'Support', '2024-01-08', 44000.00);

INSERT INTO orders (order_id, customer_id, contact_email, shipping_address, product_name, quantity, unit_price, order_date, status) VALUES
(5001, 1, 'fturner@example.com', '414 Frazier Throughway, Figueroaview, NV 41373', 'Wireless Mouse', 2, 24.99, '2026-07-14', 'delivered'),
(5002, 2, 'christopherhampton@example.org', '9332 Diaz Fall Suite 775, East Elizabethside, NV 36839', 'USB-C Hub', 1, 39.95, '2026-07-20', 'delivered'),
(5003, 3, 'mitchellprice@example.net', '0986 Lester Rapids, Smithburgh, NV 76070', 'Mechanical Keyboard', 1, 89.00, '2026-08-02', 'shipped'),
(5004, 1, 'fturner@example.com', '414 Frazier Throughway, Figueroaview, NV 41373', 'Laptop Stand', 1, 32.50, '2026-08-11', 'processing');

INSERT INTO support_tickets (ticket_id, customer_email, contact_phone, subject, opened_date, resolved) VALUES
(9001, 'fturner@example.com', '(322) 938-9600', 'Order 5001 arrived with one mouse missing', '2026-07-18', TRUE),
(9002, 'allenchristopher@example.org', '+1-894-432-7300', 'Cannot reset account password', '2026-08-05', FALSE),
(9003, 'mitchellprice@example.net', '3338874755', 'Keyboard key sticking, requesting replacement', '2026-08-15', FALSE);
