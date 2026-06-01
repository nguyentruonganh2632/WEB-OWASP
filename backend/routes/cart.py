from flask import Blueprint, request, jsonify
from models.db import get_db_connection
from routes.products import get_current_user
import time

cart_bp = Blueprint('cart', __name__)


@cart_bp.route('/cart', methods=['GET'])
def get_cart():
    """
    [VULN #10] IDOR: Truyền ?uuid=<uuid_của_user_khác> để xem giỏ hàng người đó.
    Server xác thực đăng nhập nhưng KHÔNG kiểm tra uuid có thuộc về user đang đăng nhập không.
    """
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    uuid = request.args.get('uuid')

    db = get_db_connection()
    cursor = db.cursor()

    if uuid:
        # [VULN #10] IDOR: Lấy giỏ hàng theo UUID bất kỳ, không check quyền
        cursor.execute(
            "SELECT c.id FROM carts c JOIN users u ON c.user_id = u.id WHERE u.uuid=%s",
            (uuid,)
        )
    else:
        cursor.execute("SELECT id FROM carts WHERE user_id=%s", (current['user_id'],))

    cart = cursor.fetchone()
    if not cart:
        return jsonify({'items': [], 'total': 0}), 200

    cart_id = cart['id']

    cursor.execute("""
        SELECT ci.id as cart_item_id, ci.quantity, p.id as product_id,
               p.name, p.sale_price, p.price, p.slug
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.cart_id = %s
    """, (cart_id,))
    items = cursor.fetchall()
    db.close()

    total = 0
    for item in items:
        actual_price = float(item['sale_price'] or item['price'])
        item['actual_price'] = actual_price
        total += actual_price * item['quantity']

    return jsonify({'items': items, 'total': total, 'cart_id': cart_id}), 200


@cart_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if quantity < 1:
        return jsonify({'error': 'Số lượng không hợp lệ'}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("SELECT id FROM carts WHERE user_id=%s", (current['user_id'],))
        cart = cursor.fetchone()
        if not cart:
            cursor.execute("INSERT INTO carts (user_id) VALUES (%s)", (current['user_id'],))
            cart_id = cursor.lastrowid
        else:
            cart_id = cart['id']

        cursor.execute(
            "SELECT id, quantity FROM cart_items WHERE cart_id=%s AND product_id=%s",
            (cart_id, product_id)
        )
        item = cursor.fetchone()

        if item:
            cursor.execute(
                "UPDATE cart_items SET quantity = quantity + %s WHERE id=%s",
                (quantity, item['id'])
            )
        else:
            cursor.execute(
                "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)",
                (cart_id, product_id, quantity)
            )

        db.close()
        return jsonify({'message': 'Đã thêm vào giỏ hàng'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': 'Tài khoản không tồn tại hoặc phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại!'}), 400


@cart_bp.route('/cart/remove/<int:item_id>', methods=['DELETE'])
def remove_from_cart(item_id):
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db_connection()
    cursor = db.cursor()
    # Kiểm tra item có thuộc cart của user hiện tại không
    cursor.execute("""
        DELETE FROM cart_items
        WHERE id=%s AND cart_id IN (SELECT id FROM carts WHERE user_id=%s)
    """, (item_id, current['user_id']))
    db.close()
    return jsonify({'message': 'Đã xóa khỏi giỏ hàng'}), 200


@cart_bp.route('/cart/checkout', methods=['POST'])
def checkout_cart():
    """
    [VULN #6] Race Condition: check balance → sleep(0.3) → deduct
    Không dùng DB transaction hay SELECT FOR UPDATE.
    """
    current = get_current_user(request)
    if not current:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT balance, full_name FROM users WHERE id=%s", (current['user_id'],))
    user = cursor.fetchone()
    current_balance = float(user['balance'])

    cursor.execute("SELECT id FROM carts WHERE user_id=%s", (current['user_id'],))
    cart = cursor.fetchone()
    if not cart:
        db.close()
        return jsonify({'error': 'Giỏ hàng trống'}), 400

    cart_id = cart['id']
    cursor.execute("""
        SELECT ci.quantity, p.id as product_id, p.sale_price, p.price
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.cart_id = %s
    """, (cart_id,))
    items = cursor.fetchall()

    if not items:
        db.close()
        return jsonify({'error': 'Giỏ hàng trống'}), 400

    total = sum(float(item['sale_price'] or item['price']) * item['quantity'] for item in items)

    if current_balance < total:
        db.close()
        return jsonify({'error': f'Số dư không đủ. Cần {total:,.0f}đ, hiện có {current_balance:,.0f}đ'}), 400

    # [VULN #6] Delay cố ý — mở rộng cửa sổ Race Condition
    time.sleep(0.3)

    # Trừ tiền — KHÔNG CÓ LOCK
    cursor.execute(
        "UPDATE users SET balance = balance - %s WHERE id=%s",
        (total, current['user_id'])
    )

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

    for item in items:
        actual_price = float(item['sale_price'] or item['price'])
        subtotal = actual_price * item['quantity']
        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, quantity, price, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, item['product_id'], item['quantity'], actual_price, subtotal))

    cursor.execute("DELETE FROM cart_items WHERE cart_id=%s", (cart_id,))
    db.close()

    return jsonify({
        'message': f'Đặt hàng thành công! Mã đơn #{order_id}',
        'order_id': order_id,
        'amount_paid': total
    }), 201
