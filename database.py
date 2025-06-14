import sqlite3
import os
from werkzeug.security import generate_password_hash

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'file_manager.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

def create_database():
    """
    创建或更新数据库、用户表和设置表。
    """
    print("正在连接数据库...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- 创建 users 表 (带有权限列) ---
    print("正在创建 'users' 表...")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        can_upload BOOLEAN NOT NULL DEFAULT 1,
        can_delete BOOLEAN NOT NULL DEFAULT 1,
        can_rename BOOLEAN NOT NULL DEFAULT 1,
        can_move BOOLEAN NOT NULL DEFAULT 1,
        can_create_folder BOOLEAN NOT NULL DEFAULT 1
    )
    ''')
    print(" 'users' 表创建成功。")

    # --- 插入默认管理员用户 ---
    print("正在插入默认管理员 'admin'...")
    admin_password = generate_password_hash('admin')
    # 管理员所有权限默认为 True (1)
    cursor.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ('admin', admin_password, 'admin')
    )
    
    # --- 创建 settings 表 ---
    print("正在创建 'settings' 表...")
    cursor.execute("DROP TABLE IF EXISTS settings")
    cursor.execute('''
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ''')
    # 默认禁止新用户注册
    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('registration_enabled', 'false'))
    print(" 'settings' 表创建成功，并设置默认禁止注册。")

    conn.commit()
    conn.close()
    print("数据库初始化完成。")
    
    # --- 确保 uploads 目录存在 ---
    if not os.path.exists(UPLOADS_DIR):
        print(f"正在创建主上传目录: {UPLOADS_DIR}")
        os.makedirs(UPLOADS_DIR)

if __name__ == '__main__':
    create_database()