-- ============================================================
-- ICS 499 SQL Data Anonymization Assignment - Original Test File
-- A small retail database with PII spread across four tables.
-- Deliberate test cases:
--   1. Repeated values: john.obrien@gmail.com appears in
--      customers, orders, and support_tickets (must map to the
--      SAME replacement everywhere).
--   2. Cross-table person: Maria Gonzalez is both a customer
--      and an employee (name/email/phone must stay consistent).
--   3. Varied PII column names: fname/last_name/full_name,
--      email/email_address/contact_email, phone/phone_number/
--      cell_phone, address/street_address/shipping_address.
--   4. Format variety: phones as (612) 555-0143, 612-555-0198,
--      6125550172, +1-651-555-0111.
--   5. Escaped quote inside a value: O''Brien.
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
(1, 'John', 'O''Brien', 'john.obrien@gmail.com', '(612) 555-0143', '4821 Maple Grove Ln', 'Brooklyn Park', 'MN', '55443', 1250),
(2, 'Maria', 'Gonzalez', 'maria.gonzalez@yahoo.com', '612-555-0198', '77 Lakeview Ave Apt 3B', 'Minneapolis', 'MN', '55401', 340),
(3, 'David', 'Chen', 'dchen88@outlook.com', '6125550172', '1590 River Rd', 'St Paul', 'MN', '55104', 890),
(4, 'Aisha', 'Williams', 'aisha.w@gmail.com', '+1-651-555-0111', '236 Cedar St', 'Bloomington', 'MN', '55420', 60),
(5, 'John', 'Smith', 'jsmith.mn@gmail.com', '(763) 555-0122', '901 Birch Ct', 'Maple Grove', 'MN', '55369', 15);

INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (101, 'Maria Gonzalez', 'maria.gonzalez@yahoo.com', '612-555-0198', '77 Lakeview Ave Apt 3B, Minneapolis, MN 55401', 'Sales', '2023-04-17', 52000.00);
INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (102, 'Robert Kowalski', 'r.kowalski@company.com', '(952) 555-0187', '445 Oak Hill Dr, Edina, MN 55424', 'Warehouse', '2021-09-02', 47500.00);
INSERT INTO employees (employee_id, full_name, email_address, cell_phone, home_address, department, hire_date, salary) VALUES (103, 'Linh Tran', 'linh.tran@company.com', '651-555-0139', '18 Summit Ave, St Paul, MN 55102', 'Support', '2024-01-08', 44000.00);

INSERT INTO orders (order_id, customer_id, contact_email, shipping_address, product_name, quantity, unit_price, order_date, status) VALUES
(5001, 1, 'john.obrien@gmail.com', '4821 Maple Grove Ln, Brooklyn Park, MN 55443', 'Wireless Mouse', 2, 24.99, '2026-07-14', 'delivered'),
(5002, 2, 'maria.gonzalez@yahoo.com', '77 Lakeview Ave Apt 3B, Minneapolis, MN 55401', 'USB-C Hub', 1, 39.95, '2026-07-20', 'delivered'),
(5003, 3, 'dchen88@outlook.com', '1590 River Rd, St Paul, MN 55104', 'Mechanical Keyboard', 1, 89.00, '2026-08-02', 'shipped'),
(5004, 1, 'john.obrien@gmail.com', '4821 Maple Grove Ln, Brooklyn Park, MN 55443', 'Laptop Stand', 1, 32.50, '2026-08-11', 'processing');

INSERT INTO support_tickets (ticket_id, customer_email, contact_phone, subject, opened_date, resolved) VALUES
(9001, 'john.obrien@gmail.com', '(612) 555-0143', 'Order 5001 arrived with one mouse missing', '2026-07-18', TRUE),
(9002, 'aisha.w@gmail.com', '+1-651-555-0111', 'Cannot reset account password', '2026-08-05', FALSE),
(9003, 'dchen88@outlook.com', '6125550172', 'Keyboard key sticking, requesting replacement', '2026-08-15', FALSE);
