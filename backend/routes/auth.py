"""
Auth routes - CatFood Shop CMS
"""

from flask import Blueprint, request, jsonify
import jwt
import datetime
from models.db import get_db_connection
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '')
    password = data.get('password', '')

    db = get_db_connection()
    if not db:
        return jsonify({'error': 'Lỗi hệ thống, vui lòng thử lại sau'}), 500

    cursor = db.cursor()

    # [VULN #1] SQL Injection - Login (Medium difficulty)
    # Filter chặn: comment (--  # /*) và các toán tử viết HOA (OR, AND)
    # Bypass: dùng chữ thường → MySQL không phân biệt hoa thường với keyword SQL
    # Payload: email = admin@catfood.com' or '1'='1   (password = bất kỳ)
    blocked_patterns = ['--', '#', '/*', ' OR ', ' AND ']
    if any(p in email for p in blocked_patterns):
        return jsonify({'error': 'Phát hiện ký tự nghi vấn!'}), 400

    query = f"SELECT * FROM users WHERE email='{email}' AND (password_hash='{password}' OR password_hash='plain:{password}')"
    try:
        cursor.execute(query)
    except Exception:
        db.close()
        return jsonify({'error': 'Email hoặc mật khẩu không chính xác'}), 401

    user = cursor.fetchone()
    db.close()

    if not user:
        return jsonify({'error': 'Email hoặc mật khẩu không chính xác'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'email': user['email'],
        'role_id': user['role_id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }, Config.SECRET_KEY, algorithm='HS256')

    return jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'uuid': user.get('uuid'),
            'email': user['email'],
            'full_name': user['full_name'],
            'phone': user.get('phone'),
            'role_id': user['role_id'],
            'balance': float(user.get('balance', 100000)),
        }
    }), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    full_name = data.get('full_name', '')
    email = data.get('email', '')
    password = data.get('password', '')
    phone = data.get('phone', '')

    # Lưu mật khẩu dạng plain: để tương thích với seed data
    plain_password_stored = f"plain:{password}"

    db = get_db_connection()
    if not db:
        return jsonify({'error': 'Lỗi hệ thống'}), 500

    cursor = db.cursor()

    import uuid
    new_uuid = str(uuid.uuid4())

    # Dùng parameterized query — không có SQLi
    try:
        cursor.execute("""
            INSERT INTO users (full_name, email, phone, password_hash, role_id, balance, status, uuid, created_at)
            VALUES (%s, %s, %s, %s, 2, 100000.00, 1, %s, NOW())
        """, (full_name, email, phone, plain_password_stored, new_uuid))
        db.close()
        return jsonify({'message': 'Đăng ký thành công! Bạn nhận được 100,000 VNĐ vào ví.'}), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/me', methods=['GET'])
def get_me():
    """Get current user info including balance"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        # [VULN #5] JWT Algorithm Confusion: cho phép alg=none, tắt verify signature
        payload = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=['HS256', 'none'],
            options={"verify_signature": False}
            if jwt.get_unverified_header(token).get('alg') == 'none'
            else {}
        )
    except:
        return jsonify({'error': 'Token không hợp lệ'}), 401

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, full_name, email, phone, role_id, balance FROM users WHERE id=%s",
        (payload['user_id'],)
    )
    user = cursor.fetchone()
    db.close()

    if not user:
        return jsonify({'error': 'Người dùng không tồn tại'}), 404

    return jsonify({'user': {**user, 'balance': float(user['balance'])}}), 200
