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
        abort(403, "禁止访问！检测到非法的路径访问尝试。")
    return abs_path

def human_readable_size(size, decimal_places=2):
    if size is None: return ""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def get_dir_tree(start_path, relative_path=''):
    tree = []
    try:
        for item in sorted(os.listdir(start_path)):
            abs_item_path = os.path.join(start_path, item)
            relative_item_path = os.path.join(relative_path, item)
            if os.path.isdir(abs_item_path):
                dir_node = {
                    'name': item, 
                    'path': relative_item_path, 
                    'children': get_dir_tree(abs_item_path, relative_item_path)
                }
                tree.append(dir_node)
    except FileNotFoundError:
        pass
    return tree

def get_directory_size(directory):
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except PermissionError:
        return -1 
    return total_size

# --- 路由 ---

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
    current_path_abs = get_safe_path(subpath)

    if not os.path.exists(current_path_abs) or not os.path.isdir(current_path_abs):
        flash('路径不存在或不是一个目录', 'danger')
        return redirect(url_for('index'))

    breadcrumbs = []
    path_parts = subpath.split('/') if subpath else []
    for i, part in enumerate(path_parts):
        if part:
            breadcrumbs.append({'name': part, 'path': '/'.join(path_parts[:i+1])})

    items = []
    try:
        for item in sorted(os.listdir(current_path_abs)):
            item_path_abs = os.path.join(current_path_abs, item)
            is_dir = os.path.isdir(item_path_abs)
            try:
                size = os.path.getsize(item_path_abs) if not is_dir else None
            except (OSError, FileNotFoundError):
                size = None
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

# --- NEW: 新增的搜索路由 ---
@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        flash('请输入搜索关键词', 'warning')
        return redirect(request.referrer or url_for('index'))

    results = []
    for root, dirs, files in os.walk(BASE_DIR):
        # 搜索目录
        for name in dirs:
            if query.lower() in name.lower():
                item_path_abs = os.path.join(root, name)
                relative_path = os.path.relpath(item_path_abs, BASE_DIR)
                results.append({
                    'name': name,
                    'is_dir': True,
                    'path': relative_path.replace('\\', '/'), # 统一路径分隔符为'/'
                    'size': '' # 目录大小暂不计算
                })
        # 搜索文件
        for name in files:
            if query.lower() in name.lower():
                item_path_abs = os.path.join(root, name)
                relative_path = os.path.relpath(item_path_abs, BASE_DIR)
                try:
                    size = os.path.getsize(item_path_abs)
                except (OSError, FileNotFoundError):
                    size = None
                results.append({
                    'name': name,
                    'is_dir': False,
                    'path': relative_path.replace('\\', '/'),
                    'size': human_readable_size(size)
                })
    
    results.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return render_template('search_results.html', results=results, query=query)


@app.route('/upload/', methods=['POST'])
@app.route('/upload/<path:subpath>', methods=['POST'])
@login_required
def upload_files(subpath=''):
    destination_path = request.form.get('destination_path', subpath)
    upload_path = get_safe_path(destination_path)
    if 'files[]' not in request.files: return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
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
    if '/' in folder_name or '\\' in folder_name:
        flash('文件夹名称不能包含斜杠', 'danger')
        return redirect(url_for('index', subpath=subpath))

    new_folder_path = os.path.join(parent_dir, folder_name)
    try:
        os.makedirs(new_folder_path)
        flash(f"文件夹 '{folder_name}' 创建成功", 'success')
    except FileExistsError:
        flash(f"创建失败： '{folder_name}' 已存在", 'warning')
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
        relative_item_path = os.path.join(subpath, item_name)
        item_path = get_safe_path(relative_item_path)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
                flash(f"文件 '{item_name}' 已删除", 'success')
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                flash(f"文件夹 '{item_name}' 及其所有内容已删除", 'success')
        except Exception as e:
            flash(f"删除 '{item_name}' 时出错: {e}", 'danger')
            
    return redirect(url_for('index', subpath=subpath))

@app.route('/rename', methods=['POST'])
@login_required
def rename_item():
    current_path = request.form.get('current_path', '')
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name', '').strip()

    if not all([old_name, new_name]):
        flash('缺少旧名称或新名称', 'danger')
        return redirect(url_for('index', subpath=current_path))
    
    if new_name == old_name:
        return redirect(url_for('index', subpath=current_path))

    if not new_name or '/' in new_name or '\\' in new_name:
        flash('新名称无效或包含非法字符', 'danger')
        return redirect(url_for('index', subpath=current_path))
    
    old_path = get_safe_path(os.path.join(current_path, old_name))
    new_path = get_safe_path(os.path.join(current_path, new_name))

    if not os.path.exists(old_path):
        flash(f"重命名失败：源 '{old_name}' 不存在", 'warning')
        return redirect(url_for('index', subpath=current_path))

    if os.path.exists(new_path):
        flash(f"重命名失败：目标 '{new_name}' 已存在", 'warning')
        return redirect(url_for('index', subpath=current_path))

    try:
        os.rename(old_path, new_path)
        flash(f"'{old_name}' 已成功重命名为 '{new_name}'", 'success')
    except OSError as e:
        flash(f"重命名时出错: {e}", 'danger')

    return redirect(url_for('index', subpath=current_path))

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
        
        if not os.path.exists(source_item_path):
            flash(f"移动失败：源 '{item_name}' 不存在", 'warning')
            continue

        if os.path.abspath(source_item_path) == os.path.abspath(dest_path):
            flash(f"无法将文件夹 '{item_name}' 移动到其自身", 'danger')
            continue
        if os.path.abspath(dest_path).startswith(os.path.abspath(source_item_path)):
            flash(f"无法将 '{item_name}' 移动到其子目录中", 'danger')
            continue
        if os.path.exists(dest_item_path):
            flash(f"移动失败：目标位置已存在同名文件或文件夹 '{item_name}'", 'warning')
            continue
        try:
            shutil.move(source_item_path, dest_path)
            flash(f"'{item_name}' 已成功移动到 '{destination_folder}'", 'success')
        except Exception as e:
            flash(f"移动 '{item_name}' 时出错: {e}", 'danger')
            
    return redirect(url_for('index', subpath=destination_folder))

# --- API 路由 ---
@app.route('/api/get_dirs')
@login_required
def api_get_dirs():
    tree = get_dir_tree(BASE_DIR)
    return jsonify(tree)

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
