import os
import shutil
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   send_from_directory, flash, session, jsonify, abort)
from werkzeug.utils import secure_filename

# --- 配置 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_and_complex_key'
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(BASE_DIR, exist_ok=True)

# --- 用户系统 ---
USERS = {'admin': 'admin'}

# --- 辅助函数和装饰器 ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_safe_path(path):
    full_path = os.path.join(BASE_DIR, path)
    abs_path = os.path.abspath(full_path)
    if not abs_path.startswith(os.path.abspath(BASE_DIR)):
        abort(403)
    return abs_path

def human_readable_size(size, decimal_places=2):
    if size is None: return ""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def get_dir_tree(start_path, relative_path=''):
    tree = []
    abs_start_path = get_safe_path(start_path)
    for item in sorted(os.listdir(abs_start_path)):
        abs_item_path = os.path.join(abs_start_path, item)
        relative_item_path = os.path.join(relative_path, item)
        if os.path.isdir(abs_item_path):
            dir_node = {'name': item, 'path': relative_item_path, 'children': get_dir_tree(abs_item_path, relative_item_path)}
            tree.append(dir_node)
    return tree

# --- 新增：计算目录大小的函数 ---
def get_directory_size(directory):
    """递归计算目录大小"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # 跳过符号链接等，以防无限循环
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except PermissionError:
        return -1 # 返回-1表示权限错误
    return total_size

# --- 路由 ---

# ... login, logout 路由保持不变 ...
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if USERS.get(username) == password:
            session['logged_in'] = True
            flash('登录成功!', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('您已登出', 'info')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/<path:subpath>')
@login_required
def index(subpath=''):
    current_path = get_safe_path(subpath)
    if not os.path.exists(current_path) or not os.path.isdir(current_path):
        flash('路径不存在', 'danger')
        return redirect(url_for('index'))

    breadcrumbs = []
    path_parts = subpath.split('/') if subpath else []
    for i, part in enumerate(path_parts):
        breadcrumbs.append({'name': part, 'path': '/'.join(path_parts[:i+1])})

    items = []
    try:
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            is_dir = os.path.isdir(item_path)
            size = os.path.getsize(item_path) if not is_dir else None
            items.append({
                'name': item,
                'is_dir': is_dir,
                'path': os.path.join(subpath, item),
                'size': human_readable_size(size)
            })
    except PermissionError:
        flash('没有权限访问该目录', 'danger')
    
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return render_template('index.html', items=items, current_path=subpath, breadcrumbs=breadcrumbs)

# ... upload_files, download_file, create_folder, delete_items, move_items 路由保持不变 ...
# (此处省略未改变的路由代码以保持简洁，实际文件中应保留它们)

@app.route('/upload/', methods=['POST'])
@app.route('/upload/<path:subpath>', methods=['POST'])
@login_required
def upload_files(subpath=''):
    destination_path = request.form.get('destination_path', subpath)
    upload_path = get_safe_path(destination_path)
    if 'files[]' not in request.files: return jsonify({'error': 'No file part'}), 400
    files = request.files.getlist('files[]')
    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, filename))
    return jsonify({'message': '上传成功'}), 200

@app.route('/download/<path:filepath>')
@login_required
def download_file(filepath):
    dir_path = get_safe_path(os.path.dirname(filepath))
    filename = os.path.basename(filepath)
    try:
        return send_from_directory(dir_path, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/create_folder/', methods=['POST'])
@app.route('/create_folder/<path:subpath>', methods=['POST'])
@login_required
def create_folder(subpath=''):
    parent_dir = get_safe_path(subpath)
    folder_name = request.form.get('folder_name', '').strip()
    if not folder_name:
        flash('文件夹名称不能为空', 'warning')
        return redirect(url_for('index', subpath=subpath))
    safe_folder_name = secure_filename(folder_name)
    new_folder_path = os.path.join(parent_dir, safe_folder_name)
    try:
        os.makedirs(new_folder_path)
        flash(f"文件夹 '{safe_folder_name}' 创建成功", 'success')
    except FileExistsError:
        flash(f"创建失败： '{safe_folder_name}' 已存在", 'warning')
    except OSError as e:
        flash(f"创建文件夹失败: {e}", 'danger')
    return redirect(url_for('index', subpath=subpath))

@app.route('/delete', methods=['POST'])
@login_required
def delete_items():
    subpath = request.form.get('current_path', '')
    items_to_delete = request.form.getlist('items[]')
    if not items_to_delete:
        flash('没有选择要删除的项目', 'warning')
        return redirect(url_for('index', subpath=subpath))
    for item_name in items_to_delete:
        item_path = get_safe_path(os.path.join(subpath, item_name))
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
                flash(f"文件 '{item_name}' 已删除", 'success')
            elif os.path.isdir(item_path):
                if not os.listdir(item_path):
                    os.rmdir(item_path)
                    flash(f"空文件夹 '{item_name}' 已删除", 'success')
                else:
                    flash(f"删除失败：文件夹 '{item_name}' 非空。", 'danger')
        except Exception as e:
            flash(f"删除 '{item_name}' 时出错: {e}", 'danger')
    return redirect(url_for('index', subpath=subpath))

@app.route('/move', methods=['POST'])
@login_required
def move_items():
    current_path = request.form.get('current_path', '')
    items_to_move = request.form.getlist('items[]')
    destination_folder = request.form.get('destination_folder')
    if not items_to_move or destination_folder is None:
        flash('未选择项目或目标目录', 'warning')
        return redirect(url_for('index', subpath=current_path))
    dest_path = get_safe_path(destination_folder)
    if not os.path.isdir(dest_path):
        flash('目标路径不是一个有效的文件夹', 'danger')
        return redirect(url_for('index', subpath=current_path))
    for item_name in items_to_move:
        source_item_path = get_safe_path(os.path.join(current_path, item_name))
        dest_item_path = os.path.join(dest_path, item_name)
        if os.path.abspath(dest_path).startswith(os.path.abspath(source_item_path)):
            flash(f"无法将 '{item_name}' 移动到其自身或其子目录中", 'danger')
            continue
        if os.path.exists(dest_item_path):
            flash(f"移动失败：目标位置已存在同名文件或文件夹 '{item_name}'", 'warning')
            continue
        try:
            shutil.move(source_item_path, dest_path)
            flash(f"'{item_name}' 已成功移动到 '{destination_folder}'", 'success')
        except Exception as e:
            flash(f"移动 '{item_name}' 时出错: {e}", 'danger')
    return redirect(url_for('index', subpath=current_path))

# --- API 路由 ---
@app.route('/api/get_dirs')
@login_required
def api_get_dirs():
    tree = get_dir_tree(BASE_DIR)
    return jsonify(tree)

# --- 新增：计算目录大小的API ---
@app.route('/api/get_dir_size/<path:subpath>')
@login_required
def api_get_dir_size(subpath):
    dir_path = get_safe_path(subpath)
    if not os.path.isdir(dir_path):
        return jsonify({'error': 'Not a directory'}), 400
    
    size_in_bytes = get_directory_size(dir_path)
    
    if size_in_bytes == -1:
        return jsonify({'size': '无权限'})
        
    return jsonify({'size': human_readable_size(size_in_bytes)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
