USE cat_food_shop;

-- Categories
INSERT IGNORE INTO categories (id, name, slug, description, status) VALUES
(1, 'Thuc an kho', 'thuc-an-kho', 'Hat kho cho meo cac loai', 1),
(2, 'Thuc an uot', 'thuc-an-uot', 'Pate va thuc an dong hop', 1),
(3, 'Do an vat', 'do-an-vat', 'Snack va banh thuong cho meo', 1),
(4, 'Sua & Nuoc uong', 'sua-nuoc-uong', 'Sua chuyen dung cho meo', 1);

-- Brands
INSERT IGNORE INTO brands (id, name, description, status) VALUES
(1, 'Royal Canin', 'Thuong hieu Phap cao cap', 1),
(2, 'Whiskas', 'Thuong hieu pho bien toan cau', 1),
(3, 'Ciao', 'Thuong hieu Nhat Ban', 1),
(4, 'Pedigree', 'Thuong hieu uy tin', 1);

-- Products (gia thap de khai thac race condition voi 100k)
INSERT IGNORE INTO products (id, name, slug, category_id, brand_id, price, sale_price, stock_quantity, description, status, is_featured) VALUES
(1, 'Royal Canin Adult 400g',  'royal-canin-adult-400g', 1, 1, 85000, 75000, 50,  'Thuc an kho cho meo truong thanh, giau dinh duong, kiem soat can nang hieu qua.', 1, 1),
(2, 'Whiskas Pate Ca Ngu 85g', 'whiskas-pate-ca-ngu',    2, 2, 15000, NULL,  200, 'Pate ca ngu thom ngon, bo duong cho meo moi lua tuoi.', 1, 1),
(3, 'Ciao Snack Sashimi Tom',  'ciao-snack-sashimi-tom', 3, 3, 35000, 30000, 100, 'Snack sashimi tom tuoi ngon, meo nao cung me.', 1, 0),
(4, 'Royal Canin Kitten 400g', 'royal-canin-kitten-400g',1, 1, 95000, NULL,  30,  'Thuc an dac biet cho meo con duoi 12 thang tuoi.', 1, 0),
(5, 'Sua Cat Milk 200ml',      'sua-cat-milk-200ml',     4, 2, 45000, NULL,  75,  'Sua khong lactose an toan cho meo, tang suc de khang.', 1, 0),
(6, 'Ciao Tuna & Chicken 80g', 'ciao-tuna-chicken',      2, 3, 18000, NULL,  120, 'Ket hop ca ngu va ga, giau protein cho meo hoat dong.', 1, 0),
(7, 'Whiskas Hairball 1.5kg',  'whiskas-hairball',       1, 2, 95000, 85000, 40,  'Cong thuc dac biet giam bon cat, phu hop meo long dai.', 1, 1),
(8, 'Go-Cat Tuna 375g',        'gocat-tuna',             1, 4, 55000, NULL,  60,  'Hat ca ngu giau Omega-3 cho meo truong thanh.', 1, 0);

-- Users voi balance 100,000 VND (password dang plain:, UUID co san de demo IDOR lab)
-- password: 123456    → plain:123456
-- password: password  → plain:password
-- password: abc123    → plain:abc123
INSERT IGNORE INTO users (id, full_name, email, phone, password_hash, role_id, balance, status, uuid) VALUES
(2, 'Admin Nguyen',  'admin2@catfood.com',    '0901234567', 'plain:123456',   1, 100000.00, 1, 'uuid-user2-0000-0000-000000000002'),
(3, 'Staff Tran',    'staff@catfood.com',     '0912345678', 'plain:password', 1, 100000.00, 1, 'uuid-user3-0000-0000-000000000003'),
(4, 'Nguyen Van An', 'customer1@catfood.com', '0923456789', 'plain:abc123',   2, 100000.00, 1, 'uuid-user4-0000-0000-000000000004'),
(5, 'Tran Thi Bich', 'customer2@catfood.com', '0934567890', 'plain:catfood',  2, 100000.00, 1, 'uuid-user5-0000-0000-000000000005'),
(6, 'Le Minh Cuong', 'customer3@catfood.com', '0945678901', 'plain:111111',   2, 100000.00, 1, 'uuid-user6-0000-0000-000000000006'),
(7, 'Pham Thi Dung', 'customer4@catfood.com', '0956789012', 'plain:123456',   2, 100000.00, 1, 'uuid-user7-0000-0000-000000000007');

-- Carts (can thiet cho Lab IDOR #10: xem gio hang nguoi khac qua UUID)
-- Sinh vien lay UUID tu /api/admin/users → dung UUID do de goi GET /api/cart?uuid=...
INSERT IGNORE INTO carts (id, user_id) VALUES
(1, 4),
(2, 5);

INSERT IGNORE INTO cart_items (cart_id, product_id, quantity) VALUES
(1, 1, 2),   -- Nguyen Van An: 2x Royal Canin Adult
(1, 3, 1),   -- Nguyen Van An: 1x Ciao Snack
(2, 2, 3),   -- Tran Thi Bich: 3x Whiskas Pate
(2, 5, 1);   -- Tran Thi Bich: 1x Sua Cat Milk

-- Orders mau
INSERT IGNORE INTO orders (id, user_id, receiver_name, receiver_phone, receiver_address, total_amount, payment_method, order_status) VALUES
(1, 1, 'Super Admin',    '0900000000', '100 Nguyen Hue, Q1, TP.HCM',       75000, 'wallet', 'Da giao'),
(2, 4, 'Nguyen Van An',  '0923456789', '50 Le Loi, Q3, TP.HCM',            30000, 'wallet', 'Da giao'),
(3, 5, 'Tran Thi Bich',  '0934567890', '20 Tran Hung Dao, Q5, TP.HCM',     85000, 'wallet', 'Dang giao');

-- Reviews
INSERT IGNORE INTO reviews (id, user_id, product_id, rating, comment, status) VALUES
(1, 4, 1, 5, 'San pham rat tot! Meo nha minh thich lam.', 1),
(2, 5, 1, 4, 'Chat luong on, giao hang nhanh.', 1),
(3, 6, 2, 5, 'Meo nha minh rat thich loai nay!', 1),
(4, 7, 3, 4, 'Snack ngon, gia hop ly.', 1);

-- Posts
INSERT IGNORE INTO posts (id, title, slug, content, author_id, status) VALUES
(1, 'Cach cham soc meo dung cach',       'cach-cham-soc-meo',    'Meo can duoc an dung gio va du dinh duong. Nen chon thuc an phu hop voi lua tuoi cua meo...', 1, 1),
(2, 'Top 5 thuc an tot nhat cho meo 2024','top-5-thuc-an-meo-2024','Danh gia cac san pham thuc an meo ban chay nhat tren thi truong hien nay...', 2, 1),
(3, 'Meo bi lon bung phai lam gi',        'meo-bi-lon-bung',      'Khi meo bi lon bung co the la do thuc an khong phu hop. Nen doi sang thuc an de tieu hoa hon...', 3, 1);
