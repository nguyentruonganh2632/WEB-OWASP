"""
Products, Orders, Purchase routes - CatFood Shop CMS
"""

from flask import Blueprint, request, jsonify
import jwt
import time
from models.db import get_db_connection
from config import Config

products_bp = Blueprint('products', __name__)


def get_current_user(req):
    token = req.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    try:
        # [VULN #5] JWT Algorithm Confusion: Cho phép thuật toán "none"
        return jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=['HS256', 'none'],
            options={"verify_signature": False}
            if jwt.get_unverified_header(token).get('alg') == 'none'
            else {}
        )
    except:
        return None


# ─── ORDERS ───────────────────────────────────────────────
@products_bp.route('/orders', methods=['GET'])
def get_orders():
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC",
        (current['user_id'],)
    )
    orders = cursor.fetchall()
    db.close()
    return jsonify({'orders': orders}), 200


# ─── PRODUCTS ─────────────────────────────────────────────
@products_bp.route('/search', methods=['GET'])
def search_products():
    q = request.args.get('q', '')

    # [VULN #2] SQLi UNION-based: Filter chặn comment nhưng không ngăn UNION
    # Bypass: ' UNION SELECT 1,email,password_hash,4,5,6,7,8,9,10,11,12,13 FROM users WHERE '1'='1
    if '--' in q or '#' in q or '/*' in q:
        return jsonify({'error': 'Phát hiện ký tự nghi vấn trong từ khóa tìm kiếm!'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    # Vulnerable: direct string interpolation
    query = f"""
        SELECT p.*, c.name AS category_name, b.name AS brand_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        WHERE p.status=1 AND (p.name LIKE '%{q}%' OR p.description LIKE '%{q}%')
    """
    try:
        cursor.execute(query)
        products = cursor.fetchall()
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400
    db.close()
    return jsonify({'products': products, 'query': q}), 200


@products_bp.route('/products', methods=['GET'])
def get_products():
    db = get_db_connection()
    cursor = db.cursor()
    query = """
        SELECT p.*, c.name AS category_name, b.name AS brand_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        WHERE p.status=1
        ORDER BY p.is_featured DESC, p.created_at DESC
    """
    cursor.execute(query)
    products = cursor.fetchall()
    db.close()
    return jsonify({'products': products}), 200


@products_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    db = get_db_connection()
    cursor = db.cursor()
    query = """
        SELECT p.*, c.name AS category_name, b.name AS brand_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
        WHERE p.id=%s
    """
    cursor.execute(query, (product_id,))
    product = cursor.fetchone()
    db.close()
    if not product:
        return jsonify({'error': 'Sản phẩm không tồn tại'}), 404
    return jsonify({'product': product}), 200


@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    current = get_current_user(request)
    if not current or current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403
    data = request.get_json()
    price = data.get('price')
    stock_quantity = data.get('stock_quantity')
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE products SET price=%s, stock_quantity=%s WHERE id=%s",
            (price, stock_quantity, product_id)
        )
        db.close()
        return jsonify({'message': 'Đã cập nhật sản phẩm'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400


@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    current = get_current_user(request)
    if not current or current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM cart_items WHERE product_id=%s", (product_id,))
        cursor.execute("DELETE FROM reviews WHERE product_id=%s", (product_id,))
        cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
        db.close()
        return jsonify({'message': 'Đã xóa sản phẩm'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400


@products_bp.route('/products', methods=['POST'])
def create_product():
    current = get_current_user(request)
    if not current or current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403
    data = request.get_json()
    name = data.get('name', '')
    price = data.get('price', 0)
    sale_price = data.get('sale_price') or None
    description = data.get('description', '')
    category_id = data.get('category_id', 1)
    stock_quantity = data.get('stock_quantity', 10)

    import re
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()) + f'-{int(time.time())}'

    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (name, slug, price, sale_price, description, category_id,
                                  stock_quantity, status, is_featured, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 0, NOW(), NOW())
        """, (name, slug, price, sale_price, description, category_id, stock_quantity))
        db.close()
        return jsonify({'message': 'Tạo sản phẩm thành công'}), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400


# ─── PURCHASE (Race Condition + Price Manipulation) ────────
@products_bp.route('/purchase', methods=['POST'])
def purchase():
    """
    [VULN #6] Race Condition: Không dùng transaction hay SELECT FOR UPDATE.
    [VULN #8] Price Manipulation: Server tin tưởng giá do client gửi lên.
    """
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Vui lòng đăng nhập để mua hàng'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not product_id or quantity < 1:
        return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400

    db = get_db_connection()
    cursor = db.cursor()

    # Step 1: Get product
    cursor.execute("SELECT * FROM products WHERE id=%s AND status=1", (product_id,))
    product = cursor.fetchone()
    if not product:
        db.close()
        return jsonify({'error': 'Sản phẩm không tồn tại'}), 404

    # [VULN #8] Price Manipulation: Nếu client gửi lên giá, server dùng luôn giá đó
    client_price = data.get('price')
    if client_price is not None:
        price = float(client_price)
    else:
        price = float(product['sale_price'] or product['price'])

    total = price * quantity

    # Step 2: Check balance — RACE CONDITION WINDOW BẮT ĐẦU TẠI ĐÂY
    cursor.execute("SELECT balance, full_name FROM users WHERE id=%s", (current['user_id'],))
    user = cursor.fetchone()
    current_balance = float(user['balance'])

    if current_balance < total:
        db.close()
        return jsonify({
            'error': f'Số dư không đủ. Cần {total:,.0f}đ, hiện có {current_balance:,.0f}đ'
        }), 400

    # [VULN #6] Delay cố ý để mở rộng cửa sổ Race Condition
    time.sleep(0.3)

    # Step 3: Trừ tiền — KHÔNG CÓ LOCK, dễ bị khai thác song song
    cursor.execute(
        "UPDATE users SET balance = balance - %s WHERE id=%s",
        (total, current['user_id'])
    )

    # Step 4: Tạo đơn hàng
    cursor.execute("""
        INSERT INTO orders (user_id, receiver_name, receiver_phone, receiver_address,
                            total_amount, payment_method, order_status, created_at)
        VALUES (%s, %s, %s, %s, %s, 'wallet', 'Cho xac nhan', NOW())
    """, (
        current['user_id'],
        user['full_name'],
        data.get('phone', ''),
        data.get('address', 'Dia chi mac dinh'),
        total
    ))
    order_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO order_items (order_id, product_id, quantity, price, subtotal)
        VALUES (%s, %s, %s, %s, %s)
    """, (order_id, product_id, quantity, price, total))

    db.close()

    db2 = get_db_connection()
    c2 = db2.cursor()
    c2.execute("SELECT balance FROM users WHERE id=%s", (current['user_id'],))
    new_balance = float(c2.fetchone()['balance'])
    db2.close()

    return jsonify({
        'message': f'Đặt hàng thành công! Mã đơn #{order_id}',
        'order_id': order_id,
        'amount_paid': total,
        'balance_before': current_balance,
        'balance_after': new_balance,
    }), 201


# ─── PROFILE ──────────────────────────────────────────────
@products_bp.route('/profile', methods=['PUT'])
def update_profile():
    """
    [VULN #9] Mass Assignment: Vòng lặp ghép TẤT CẢ key từ body vào SET clause.
    Kẻ tấn công tự set role_id=1 hoặc balance=999999.
    """
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    user_id = current['user_id']

    # Mass assignment: accepts all fields from request body without whitelist
    set_clauses = []
    for key, value in data.items():
        set_clauses.append(f"{key}='{value}'")

    if not set_clauses:
        return jsonify({'error': 'Không có dữ liệu để cập nhật'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    try:
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id={user_id}"
        cursor.execute(query)
        db.close()
        return jsonify({'message': 'Cập nhật thành công'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400


# ─── ADMIN ────────────────────────────────────────────────
@products_bp.route('/admin/users', methods=['GET'])
def get_all_users():
    """
    [VULN #7] API Testing: Endpoint admin không yêu cầu xác thực.
    Bất kỳ ai cũng gọi được và lấy toàn bộ email + password_hash.
    """
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, full_name, email, phone, password_hash, role_id, balance, created_at FROM users"
    )
    users = cursor.fetchall()
    db.close()
    for u in users:
        if u.get('balance'):
            u['balance'] = float(u['balance'])
    return jsonify({'users': users}), 200


@products_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    current = get_current_user(request)
    if not current or current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403
    if user_id == 1:
        return jsonify({'error': 'Không thể xóa Super Admin!'}), 403
    db = get_db_connection()
    cursor = db.cursor()
    try:
        for stmt, params in [
            ("DELETE FROM cart_items WHERE cart_id IN (SELECT id FROM carts WHERE user_id=%s)", (user_id,)),
            ("DELETE FROM carts WHERE user_id=%s", (user_id,)),
            ("DELETE FROM reviews WHERE user_id=%s", (user_id,)),
            ("DELETE FROM posts WHERE author_id=%s", (user_id,)),
            ("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE user_id=%s)", (user_id,)),
            ("DELETE FROM orders WHERE user_id=%s", (user_id,)),
        ]:
            try:
                cursor.execute(stmt, params)
            except Exception:
                pass
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        db.commit()
        db.close()
        return jsonify({'message': 'Đã xóa người dùng'}), 200
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': f'Lỗi CSDL: {str(e)}'}), 500


@products_bp.route('/admin/users/<int:user_id>/money', methods=['POST'])
def add_money_to_user(user_id):
    current = get_current_user(request)
    if not current or current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403
    data = request.get_json()
    amount = float(data.get('amount', 100000))
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id))
    db.close()
    return jsonify({'message': f'Đã nạp {amount:,.0f}đ cho user #{user_id}'}), 200


# ─── ADMIN ORDERS ─────────────────────────────────────────
@products_bp.route('/admin/orders', methods=['GET'])
def admin_get_orders():
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Vui lòng đăng nhập'}), 401
    if current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        SELECT o.*, u.full_name AS customer_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    """)
    orders = cursor.fetchall()
    db.close()
    return jsonify({'orders': orders}), 200


@products_bp.route('/admin/orders/<int:order_id>/status', methods=['POST'])
def admin_update_order_status(order_id):
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Vui lòng đăng nhập'}), 401
    if current.get('role_id') != 1:
        return jsonify({'error': 'Forbidden: Chỉ Admin mới được phép!'}), 403

    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        return jsonify({'error': 'Trạng thái không hợp lệ'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    order = cursor.fetchone()
    if not order:
        db.close()
        return jsonify({'error': 'Đơn hàng không tồn tại'}), 404

    cursor.execute("UPDATE orders SET order_status=%s WHERE id=%s", (new_status, order_id))
    db.close()
    return jsonify({'message': f'Đã cập nhật trạng thái đơn #{order_id} thành "{new_status}"'}), 200
