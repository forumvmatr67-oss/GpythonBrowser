import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'gpython-super-secret-key-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------- Модели БД ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(10), default='dark')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    searches = db.relationship('SearchHistory', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    query = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------- Функция поиска (реальный через DuckDuckGo API) ----------
def perform_search(query):
    """Поиск через DuckDuckGo Instant Answer API (без рекламы, бесплатно)"""
    try:
        url = 'https://api.duckduckgo.com/'
        params = {
            'q': query,
            'format': 'json',
            'no_html': 1,
            'skip_disambig': 1
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        results = []
        # Основной ответ (определение или прямое резюме)
        if data.get('AbstractText'):
            results.append({
                'title': data.get('AbstractTitle') or 'Результат',
                'snippet': data.get('AbstractText'),
                'url': data.get('AbstractURL') or '#',
                'icon': '📖'
            })
        # Результаты из RelatedTopics
        if data.get('RelatedTopics'):
            for topic in data['RelatedTopics'][:8]:
                if isinstance(topic, dict) and 'Text' in topic and 'FirstURL' in topic:
                    results.append({
                        'title': topic['Text'].split(' - ')[0][:80],
                        'snippet': topic['Text'][:200],
                        'url': topic['FirstURL'],
                        'icon': '🔗'
                    })
        if not results:
            results = [{
                'title': f'Результаты для "{query}"',
                'snippet': 'Попробуйте уточнить запрос или воспользуйтесь другим источником.',
                'url': '#',
                'icon': 'ℹ️'
            }]
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return [{'title': 'Ошибка подключения', 'snippet': 'Не удалось выполнить поиск. Проверьте интернет.', 'url': '#', 'icon': '⚠️'}]

# ---------- Маршруты ----------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', username=current_user.username, theme=current_user.theme)
    return render_template('index.html', username=None, theme='dark')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('index'))
    
    results = perform_search(query)
    
    # Сохраняем историю, если пользователь авторизован
    if current_user.is_authenticated and len(query) > 0:
        try:
            history = SearchHistory(user_id=current_user.id, query=query)
            db.session.add(history)
            db.session.commit()
        except:
            db.session.rollback()
    
    return render_template('index.html', query=query, results=results, 
                           username=current_user.username if current_user.is_authenticated else None,
                           theme=current_user.theme if current_user.is_authenticated else 'dark')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('✅ Успешный вход!', 'success')
            return redirect(url_for('index'))
        flash('❌ Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('⚠️ Пользователь с таким именем уже существует', 'warning')
        elif User.query.filter_by(email=email).first():
            flash('⚠️ Email уже зарегистрирован', 'warning')
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('🎉 Регистрация успешна! Теперь войдите.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('👋 Вы вышли из аккаунта', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_theme':
            new_theme = request.form.get('theme')
            if new_theme in ['dark', 'light']:
                current_user.theme = new_theme
                db.session.commit()
                flash('🎨 Тема изменена', 'success')
        elif action == 'delete_account':
            # Удаляем все поиски пользователя, затем самого пользователя
            SearchHistory.query.filter_by(user_id=current_user.id).delete()
            db.session.delete(current_user)
            db.session.commit()
            logout_user()
            flash('🗑️ Аккаунт удалён. Нам жаль прощаться!', 'info')
            return redirect(url_for('index'))
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user, theme=current_user.theme)

@app.route('/history')
@login_required
def history():
    searches = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).all()
    return render_template('history.html', searches=searches, theme=current_user.theme)

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    SearchHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('🧹 История поиска очищена', 'success')
    return redirect(url_for('history'))

# Подсказки (AJAX) - популярные запросы
@app.route('/suggest')
def suggest():
    prefix = request.args.get('q', '').strip()
    if len(prefix) < 2:
        return jsonify([])
    # Простая подсказка из заранее заданных или из истории популярных (можно расширить)
    suggestions = [
        'GPT chat', 'Python tutorial', 'Flask framework', 'YouTube music', 'GitHub',
        'VS Code download', 'GPython browser', 'AI news', 'spaceX launch'
    ]
    results = [s for s in suggestions if s.lower().startswith(prefix.lower())]
    return jsonify(results[:5])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
