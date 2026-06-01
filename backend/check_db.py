"""
Script kiểm tra & hướng dẫn setup DB cho CMS-OWASP Lab.
"""
from dotenv import load_dotenv
import os
import pymysql

load_dotenv()

MYSQL_HOST     = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER     = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_PORT     = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_DB       = os.getenv('MYSQL_DB', 'cat_food_shop')

print("=" * 60)
print("CMS OWASP - Database Setup Check")
print(f"  Host: {MYSQL_HOST}:{MYSQL_PORT}  DB: {MYSQL_DB}")
print("=" * 60)

try:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        port=MYSQL_PORT,
        charset='utf8mb4'
    )
    print("[OK] Ket noi MySQL thanh cong!")
    cursor = conn.cursor()

    cursor.execute(f"SHOW DATABASES LIKE '{MYSQL_DB}'")
    if not cursor.fetchone():
        print(f"[!] Database '{MYSQL_DB}' chua ton tai")
        print("    Chay: mysql -u root -p < backend/database/init_db.sql")
        conn.close()
        exit(1)

    cursor.execute(f"USE {MYSQL_DB}")
    print(f"[OK] Database '{MYSQL_DB}' da ton tai")

    checks = [
        ("products",   "SELECT COUNT(*) FROM products"),
        ("users",      "SELECT COUNT(*) FROM users"),
        ("carts",      "SELECT COUNT(*) FROM carts"),
        ("cart_items", "SELECT COUNT(*) FROM cart_items"),
        ("posts",      "SELECT COUNT(*) FROM posts"),
        ("reviews",    "SELECT COUNT(*) FROM reviews"),
    ]

    all_ok = True
    for table, query in checks:
        cursor.execute(query)
        count = cursor.fetchone()[0]
        status = "[OK]" if count > 0 else "[!] TRONG"
        print(f"  {status} {table}: {count} ban ghi")
        if count == 0:
            all_ok = False

    # Kiem tra UUID (can cho Lab IDOR #10)
    cursor.execute("SELECT COUNT(*) FROM users WHERE uuid IS NOT NULL")
    uuid_count = cursor.fetchone()[0]
    if uuid_count == 0:
        print("  [!] Khong co user nao co UUID → Lab IDOR #10 se bi hong!")
        all_ok = False
    else:
        print(f"  [OK] UUID: {uuid_count} users co uuid")

    if not all_ok:
        print("\n[!] Du lieu thieu - chay lai seed:")
        print("    python backend/seed.py")
    else:
        print("\n[DONE] Tat ca bang da co du lieu. San sang demo lab!")

    conn.close()

except Exception as e:
    print(f"[FAIL] Khong ket noi duoc: {e}")
    print("\nGiai phap:")
    print("1. Kiem tra MySQL dang chay")
    print(f"2. Kiem tra MYSQL_PASSWORD trong .env (hien tai: '{MYSQL_PASSWORD}')")
    print("3. Neu dung Docker: docker-compose up -d")
