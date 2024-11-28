from flask import Flask, request, jsonify, redirect, url_for, send_from_directory, render_template
import mysql.connector # type: ignore
import hashlib
import os
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user # type: ignore
from datetime import timedelta

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.secret_key = 'your-secret-key'  # 请更改为安全的密钥
app.config.update(
    SESSION_PERMANENT=False,  # 设置会话为非永久性
    SESSION_COOKIE_SECURE=False,  # 如果使用 HTTPS 则设为 True
    SESSION_COOKIE_HTTPONLY=True,  # 防止会话被篡改
    SESSION_COOKIE_SAMESITE='Lax',  # 防止跨站请求伪造
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)  # 设置会话过期时间
)

# MySQL 配置
db_config = {
    'host': '127.0.0.1',      # MySQL 服务器地址
    'port': 3308,             # MySQL 端口号
    'user': 'root',           # 数据库用户名
    'password': 'root123',    # 数据库密码（注意：mysql-connector-python 使用 'password' 而不是 'passwd'）
    'database': 'game_db',    # 数据库名（注意：使用 'database' 而不是 'db'）
    'charset': 'utf8mb4'      # 字符集
}

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# 用户模型
class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

# 获取数据库连接
def get_db():
    try:
        return mysql.connector.connect(**db_config)
    except Exception as e:
        print(f"数据库连接错误: {str(e)}")
        raise

# 用户加载函数
@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        return User(user[0], user[1])
    return None

# 数据库初始化
def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("数据库初始化成功")
    except Exception as e:
        print(f"数据库初始化错误: {str(e)}")

# 注册路由
@app.route('/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return jsonify({'message': '您已经登录'}), 400
        
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    
    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空'}), 400
        
    if password != confirm_password:
        return jsonify({'message': '两次输入的密码不一致'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)',
                      (username, password))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': '注册成功'}), 200
    except mysql.connector.IntegrityError:
        return jsonify({'message': '用户名已存在'}), 400
    except Exception as e:
        return jsonify({'message': '注册失败'}), 500

# 登录路由
@app.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return jsonify({
            'message': '您已经登录',
            'redirect': url_for('second_page')
        }), 200
        
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'message': '用户名和密码不能为空'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE username = %s AND password = %s',
                      (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            user_obj = User(user[0], user[1])
            login_user(user_obj, remember=False)  # 确保 remember=False
            return jsonify({
                'message': '登录成功',
                'redirect': url_for('second_page')
            }), 200
        else:
            return jsonify({'message': '用户名或密码错误'}), 401
    except Exception as e:
        print(f"登录错误: {str(e)}")
        return jsonify({'message': '服务器错误，请稍后重试'}), 500

# 登出路由
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

# 游戏页面路由
@app.route('/game')
@login_required
def game():
    return send_from_directory('static/pages', 'index.html')

# 添加处理 pages 下的静态资源的路由
@app.route('/static/pages/<path:filename>')
def serve_pages_static(filename):
    return send_from_directory('static/pages', filename)

# 登录页面路由
@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('game'))
    return send_from_directory('static/pages', 'index.html')

# 添加一个查看用户数据的路由
@app.route('/debug/users')
def debug_users():
    if not app.debug:
        return jsonify({'message': '只在调试模式下可用'}), 403
        
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def show_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    
    print("\n=== 用户列表 ===")
    print("ID\t用户名\t\t密码哈希")
    print("-" * 50)
    for user in users:
        print(f"{user[0]}\t{user[1]}\t\t{user[2]}")
    print("-" * 50)
    print(f"总用户数: {len(users)}\n")

# 添加错误处理
@app.errorhandler(401)
def unauthorized(error):
    return redirect(url_for('login_page'))

@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for('login_page'))

# 添加处理 second-page.html 的路由
@app.route('/second-page')
@login_required
def second_page():
    return send_from_directory('static/pages', 'second-page.html')

# 添加图片和音乐资源的专门路由
@app.route('/static/pages/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('static/pages/images', filename)

@app.route('/static/pages/music/<path:filename>')
def serve_music(filename):
    return send_from_directory('static/pages/music', filename)

# 添加游戏信息页面的路由
@app.route('/2048-info')
@login_required
def game_2048_info():
    return send_from_directory('static/pages', '2048-info.html')

@app.route('/gomoku-info')
@login_required
def gomoku_info():
    return send_from_directory('static/pages', 'gomoku-info.html')

@app.route('/game-info')
@login_required
def game_info():
    return send_from_directory('static/pages', 'game-info.html')

@app.route('/mario-info')
@login_required
def mario_info():
    return send_from_directory('static/pages', 'mario-info.html')

@app.route('/pacman-info')
@login_required
def pacman_info():
    return send_from_directory('static/pages', 'pacman-info.html')

@app.route('/space-war-info')
@login_required
def space_war_info():
    return send_from_directory('static/pages', 'space-war-info.html')

@app.route('/snake-info')
@login_required
def snake_info():
    return send_from_directory('static/pages', 'snake-info.html')

# 添加游戏子目录的路由
@app.route('/static/pages/<path:game_name>/<path:filename>')
def serve_game_files(game_name, filename):
    return send_from_directory(f'static/pages/{game_name}', filename)

# 添加反馈页面路由
@app.route('/feedback')
@login_required
def feedback():
    return send_from_directory('static/pages', 'feedback.html')

# 添加查看反馈页面路由
@app.route('/view_feedback')
@login_required
def view_feedback():
    return send_from_directory('static/pages', 'view_feedback.html')

# 添加错误处理路由
@app.errorhandler(500)
def internal_error(error):
    print(f"500错误: {str(error)}")
    return redirect(url_for('login_page'))

# 在需要时调用
if __name__ == '__main__':
    try:
        init_db()
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"启动错误: {str(e)}") 