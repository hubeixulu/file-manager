import os
import shutil
import sqlite3
import mimetypes
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   send_from_directory, flash, session, jsonify, abort, Response)
# 移除 secure_filename 的导入，因为它不再被使用
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect

# --- 配置 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) 
BASE_DIR_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR_ROOT, 'uploads')
DB_PATH = os.path.join(BASE_DIR_ROOT, 'file_manager.db')
os.makedirs(UPLOADS_DIR, exist_ok=True)

csrf = CSRFProtect(app)

# ... 省略其他未改动的函数 ...
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403, "您没有权限访问此页面。")
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
            conn.close()
            if user and user[permission_name]:
                return f(*args, **kwargs)
            else:
                return jsonify({'error': '您没有执行此操作的权限'}), 403
        return decorated_function
    return decorator

def get_current_user_permissions():
    if 'username' not in session: return {}
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
    conn.close()
    if not user: return {}
    return {key: user[key] for key in user.keys()}

def get_user_base_dir():
    if session.get('role') == 'admin':
        return UPLOADS_DIR
    else:
        user_dir = os.path.join(UPLOADS_DIR, session.get('username', ''))
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

def get_safe_path(path):
    user_base_dir = get_user_base_dir()
    full_path = os.path.join(user_base_dir, path)
    abs_path = os.path.abspath(full_path)
    if not abs_path.startswith(os.path.abspath(user_base_dir)):
        abort(403, "禁止访问！检测到非法的路径访问尝试。")
    return abs_path

def get_relative_path(abs_path):
    user_base_dir = get_user_base_dir()
    return os.path.relpath(abs_path, user_base_dir).replace("\\", "/")

def human_readable_size(size, decimal_places=2):
    if size is None: return ""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def is_previewable(filename):
    previewable_extensions = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml'}
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
    _, ext = os.path.splitext(filename.lower())
    return ext in previewable_extensions or ext in image_extensions

def get_directory_size(directory):
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except PermissionError: return -1 
    return total_size

@app.context_processor
def inject_user_permissions():
    if 'logged_in' in session:
        return {'user_permissions': get_current_user_permissions()}
    return {'user_permissions': {}}

# --- 主要路由 ---
# ... /login, /register, /logout, / 等路由保持不变 ...

# *** Bug 修复：从这里移除 secure_filename() ***
@app.route('/upload/', methods=['POST'])
@permission_required('can_upload')
def upload_files():
    destination_path = request.form.get('destination_path', '')
    upload_path = get_safe_path(destination_path)
    if 'files[]' not in request.files: return jsonify({'error': 'No file part'}), 400
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    for file in files:
        if file and file.filename != '':
            # 直接使用原始文件名，不再过滤
            filename = file.filename
            # 基础安全检查，防止路径穿越
            if ".." in filename or filename.startswith("/"):
                return jsonify({'error': f"文件名 '{filename}' 包含非法字符。"}), 400
            file.save(os.path.join(upload_path, filename))
            
    return jsonify({'message': '上传成功'}), 200

# ... 其余所有路由保持不变 ...
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'user':
                user_dir = os.path.join(UPLOADS_DIR, user['username'])
                os.makedirs(user_dir, exist_ok=True)
            flash('登录成功!', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')
    conn = get_db_connection()
    reg_setting = conn.execute("SELECT value FROM settings WHERE key = 'registration_enabled'").fetchone()
    conn.close()
    registration_enabled = reg_setting['value'] == 'true' if reg_setting else False
    return render_template('login.html', registration_enabled=registration_enabled)

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    reg_setting = conn.execute("SELECT value FROM settings WHERE key = 'registration_enabled'").fetchone()
    conn.close()
    registration_enabled = reg_setting['value'] == 'true' if reg_setting else False
    if not registration_enabled:
        flash('管理员已关闭新用户注册功能。', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, generate_password_hash(password), 'user'))
            conn.commit()
            os.makedirs(os.path.join(UPLOADS_DIR, username), exist_ok=True)
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('该用户名已被注册。', 'danger')
            return redirect(url_for('register'))
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('您已登出', 'info')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/<path:subpath>')
@login_required
def index(subpath=''):
    current_path_abs = get_safe_path(subpath)
    if not os.path.exists(current_path_abs) or not os.path.isdir(current_path_abs):
        flash('路径不存在或不是一个目录', 'danger')
        return redirect(url_for('index'))
    breadcrumbs, path_parts = [], subpath.split('/') if subpath else []
    for i, part in enumerate(path_parts):
        if part:
            breadcrumbs.append({'name': part, 'path': '/'.join(path_parts[:i+1])})
    items = []
    try:
        for item_name in sorted(os.listdir(current_path_abs)):
            item_path_abs = os.path.join(current_path_abs, item_name)
            is_dir = os.path.isdir(item_path_abs)
            size = None
            if not is_dir:
                try: size = os.path.getsize(item_path_abs)
                except (OSError, FileNotFoundError): pass
            items.append({
                'name': item_name, 'is_dir': is_dir, 'path': get_relative_path(item_path_abs),
                'size': human_readable_size(size), 'previewable': not is_dir and is_previewable(item_name)
            })
    except PermissionError:
        flash('没有权限访问该目录', 'danger')
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return render_template('index.html', items=items, current_path=subpath, breadcrumbs=breadcrumbs)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query: return redirect(url_for('index'))
    results, search_root = [], get_user_base_dir()
    for root, dirs, files in os.walk(search_root):
        for name in dirs + files:
            if query.lower() in name.lower():
                full_path = os.path.join(root, name)
                results.append({
                    'name': name, 'is_dir': os.path.isdir(full_path),
                    'path': get_relative_path(full_path),
                    'parent': get_relative_path(os.path.dirname(full_path))
                })
    return render_template('search.html', query=query, results=results)

@app.route('/view/<path:filepath>')
@login_required
def view_file(filepath):
    abs_path = get_safe_path(filepath)
    if not os.path.exists(abs_path): abort(404)
    mime_type, _ = mimetypes.guess_type(abs_path)
    if mime_type and mime_type.startswith('image/'):
        return send_from_directory(os.path.dirname(abs_path), os.path.basename(abs_path))
    elif mime_type and (mime_type.startswith('text/') or _ == 'gzip'):
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return Response(f"<pre>{content}</pre>", mimetype='text/html')
        except Exception: return "无法读取文件内容。", 500
    else: return "此文件类型无法预览。", 415

@app.route('/download/<path:filepath>')
@login_required
def download_file(filepath):
    abs_path = get_safe_path(filepath)
    if not os.path.isfile(abs_path): abort(404)
    return send_from_directory(os.path.dirname(abs_path), os.path.basename(abs_path), as_attachment=True)

@app.route('/admin')
@admin_required
def admin_panel():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    reg_setting = conn.execute("SELECT value FROM settings WHERE key = 'registration_enabled'").fetchone()
    conn.close()
    registration_enabled = reg_setting['value'] == 'true' if reg_setting else False
    return render_template('admin.html', users=users, registration_enabled=registration_enabled)

@app.route('/admin/toggle_registration', methods=['POST'])
@admin_required
def toggle_registration():
    is_enabled = request.form.get('enabled') == 'true'
    conn = get_db_connection()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'registration_enabled'", (str(is_enabled).lower(),))
    conn.commit()
    conn.close()
    return jsonify({'message': '注册设置已更新'})

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def add_user():
    username, password, role = request.form.get('username'), request.form.get('password'), request.form.get('role', 'user')
    if not username or not password: return jsonify({'error': '用户名和密码不能为空'}), 400
    if role not in ['admin', 'user']: return jsonify({'error': '无效的角色'}), 400
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, generate_password_hash(password), role))
        conn.commit()
        if role == 'user': os.makedirs(os.path.join(UPLOADS_DIR, username), exist_ok=True)
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'message': '用户添加成功', 'user': {'id': user_id, 'username': username, 'role': role}}), 201
    except sqlite3.IntegrityError: return jsonify({'error': '用户名已存在'}), 409
    finally: conn.close()

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    username, password, role = request.form.get('username'), request.form.get('password'), request.form.get('role', 'user')
    if not username or role not in ['admin', 'user']: return jsonify({'error': '无效的用户名或角色'}), 400
    conn = get_db_connection()
    try:
        current_user_id = conn.execute('SELECT id FROM users WHERE username = ?', (session['username'],)).fetchone()['id']
        if user_id == current_user_id and role == 'user': return jsonify({'error': '不能将自己的角色从管理员降级'}), 403
        sql = "UPDATE users SET username = ?, role = ?, can_upload = ?, can_delete = ?, can_rename = ?, can_move = ?, can_create_folder = ?"
        params = [
            username, role, request.form.get('can_upload') == 'true', request.form.get('can_delete') == 'true',
            request.form.get('can_rename') == 'true', request.form.get('can_move') == 'true', request.form.get('can_create_folder') == 'true'
        ]
        if password:
            sql += ", password = ?"
            params.append(generate_password_hash(password))
        sql += " WHERE id = ?"
        params.append(user_id)
        conn.execute(sql, tuple(params))
        conn.commit()
        return jsonify({'message': '用户更新成功'}), 200
    except sqlite3.IntegrityError: return jsonify({'error': '用户名已存在'}), 409
    finally: conn.close()

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    user_to_delete = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    current_user_id = conn.execute('SELECT id FROM users WHERE username = ?', (session['username'],)).fetchone()['id']
    if user_id == current_user_id:
        conn.close()
        return jsonify({'error': '不能删除自己'}), 403
    if user_to_delete:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        if user_to_delete['role'] == 'user':
            user_dir = os.path.join(UPLOADS_DIR, user_to_delete['username'])
            if os.path.exists(user_dir): shutil.rmtree(user_dir)
    conn.close()
    return jsonify({'message': '用户删除成功'}), 200

@app.route('/create_folder', methods=['POST'])
@permission_required('can_create_folder')
def create_folder():
    subpath, folder_name = request.form.get('current_path', ''), request.form.get('folder_name', '').strip()
    if not folder_name: return jsonify({'error': '文件夹名称不能为空'}), 400
    if '/' in folder_name or '\\' in folder_name: return jsonify({'error': '文件夹名称不能包含斜杠'}), 400
    new_folder_path_abs = os.path.join(get_safe_path(subpath), folder_name)
    if os.path.exists(new_folder_path_abs): return jsonify({'error': f"创建失败： '{folder_name}' 已存在"}), 409
    try:
        os.makedirs(new_folder_path_abs)
        new_folder_path_rel = get_relative_path(new_folder_path_abs)
        return jsonify({'message': f"文件夹 '{folder_name}' 创建成功", 'item': {'name': folder_name, 'is_dir': True, 'path': new_folder_path_rel, 'size': '-', 'previewable': False}}), 201
    except OSError as e: return jsonify({'error': f"创建文件夹失败: {e}"}), 500

@app.route('/delete', methods=['POST'])
@permission_required('can_delete')
def delete_items():
    subpath, items_to_delete = request.form.get('current_path', ''), request.form.getlist('items[]')
    if not items_to_delete: return jsonify({'error': '没有选择要删除的项目'}), 400
    success_list, error_list = [], []
    for item_name in items_to_delete:
        item_path = get_safe_path(os.path.join(subpath, item_name))
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path): os.remove(item_path)
            elif os.path.isdir(item_path): shutil.rmtree(item_path)
            success_list.append(item_name)
        except Exception as e: error_list.append({'name': item_name, 'error': str(e)})
    if not error_list: return jsonify({'message': '所有选中项目已成功删除', 'deleted': success_list}), 200
    else: return jsonify({'error': '部分项目删除失败', 'deleted': success_list, 'errors': error_list}), 207

@app.route('/rename', methods=['POST'])
@permission_required('can_rename')
def rename_item():
    current_path, old_name, new_name = request.form.get('current_path', ''), request.form.get('old_name'), request.form.get('new_name', '').strip()
    if not all([old_name, new_name]): return jsonify({'error': '缺少旧名称或新名称'}), 400
    if new_name == old_name: return jsonify({'message': '名称未改变'}), 200
    if not new_name or '/' in new_name or '\\' in new_name: return jsonify({'error': '新名称无效或包含非法字符'}), 400
    old_path, new_path = get_safe_path(os.path.join(current_path, old_name)), get_safe_path(os.path.join(current_path, new_name))
    if not os.path.exists(old_path): return jsonify({'error': f"重命名失败：源 '{old_name}' 不存在"}), 404
    if os.path.exists(new_path): return jsonify({'error': f"重命名失败：目标 '{new_name}' 已存在"}), 409
    try:
        os.rename(old_path, new_path)
        return jsonify({'message': f"'{old_name}' 已成功重命名为 '{new_name}'"}), 200
    except OSError as e: return jsonify({'error': f"重命名时出错: {e}"}), 500

@app.route('/move', methods=['POST'])
@permission_required('can_move')
def move_items():
    current_path, items_to_move, destination_folder = request.form.get('current_path', ''), request.form.getlist('items[]'), request.form.get('destination_folder')
    if not items_to_move or destination_folder is None: return jsonify({'error': '未选择项目或目标目录'}), 400
    dest_path_abs = get_safe_path(destination_folder)
    if not os.path.isdir(dest_path_abs): return jsonify({'error': '目标路径不是一个有效的文件夹'}), 400
    success_list, error_list = [], []
    for item_name in items_to_move:
        source_item_path = get_safe_path(os.path.join(current_path, item_name))
        dest_item_path = os.path.join(dest_path_abs, item_name)
        if not os.path.exists(source_item_path): error_list.append({'name': item_name, 'error': '源文件不存在'}); continue
        if os.path.abspath(source_item_path) == os.path.abspath(dest_path_abs): error_list.append({'name': item_name, 'error': '无法将文件夹移动到其自身'}); continue
        if os.path.abspath(dest_path_abs).startswith(os.path.abspath(source_item_path) + os.sep): error_list.append({'name': item_name, 'error': '无法移动到其子目录中'}); continue
        if os.path.exists(dest_item_path): error_list.append({'name': item_name, 'error': '目标位置已存在同名项目'}); continue
        try:
            shutil.move(source_item_path, dest_path_abs)
            success_list.append(item_name)
        except Exception as e: error_list.append({'name': item_name, 'error': str(e)})
    if not error_list: return jsonify({'message': '所有选中项目已成功移动', 'moved': success_list}), 200
    else: return jsonify({'error': '部分项目移动失败', 'moved': success_list, 'errors': error_list}), 207

@app.route('/api/get_dir_size/<path:subpath>')
@login_required
def api_get_dir_size(subpath):
    dir_path = get_safe_path(subpath)
    if not os.path.isdir(dir_path): return jsonify({'error': 'Not a directory'}), 400
    size_in_bytes = get_directory_size(dir_path)
    if size_in_bytes == -1: return jsonify({'size': '无权限'})
    return jsonify({'size': human_readable_size(size_in_bytes)})

@app.route('/api/get_dirs')
@login_required
def api_get_dirs():
    user_base_dir = get_user_base_dir()
    def get_dir_tree_api(start_path):
        tree, rel_start_path = [], os.path.relpath(start_path, user_base_dir)
        try:
            for item in sorted(os.listdir(start_path)):
                abs_item_path = os.path.join(start_path, item)
                if os.path.isdir(abs_item_path):
                    relative_item_path = get_relative_path(abs_item_path)
                    dir_node = {'name': item, 'path': relative_item_path, 'children': get_dir_tree_api(abs_item_path)}
                    tree.append(dir_node)
        except FileNotFoundError: pass
        return tree
    return jsonify(get_dir_tree_api(user_base_dir))

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("="*50); print("警告: 数据库 'file_manager.db' 不存在。"); print("请先运行 'python database.py' 来初始化数据库。"); print("="*50)
    else:
        app.run(debug=True, host='0.0.0.0', port=80)