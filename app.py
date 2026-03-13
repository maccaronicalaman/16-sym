from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
from sqlalchemy import or_, and_

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# Настройка SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# Интеграция Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Модели базы данных ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    text = db.Column(db.String(16), nullable=False) # Ограничение 16 символов
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- Роуты ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_id = request.form.get('username')
        code = request.form.get('password')
        if user_id and code:
            if not User.query.filter_by(username=user_id).first():
                new_user = User(username=user_id, password=code)
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))
            return "<h1 style='background-color: #9cb18d; color: #1a1a1a; font-family: Courier New; padding: 20px;'>[ ERROR: USER EXISTS ]</h1>"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('username')
        code = request.form.get('password')
        user = User.query.filter_by(username=user_id, password=code).first()
        if user:
            session['user'] = user.username
            return redirect(url_for('dashboard'))
        return "<h1 style='background-color: #9cb18d; color: #1a1a1a; font-family: Courier New; padding: 20px;'>[ FAILED. WRONG ID OR CODE. ]</h1>"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    current_username = session['user']
    
    # Получаем список всех пользователей, кроме нас самих, для списка контактов
    all_users = User.query.filter(User.username != current_username).all()
    user_list = [u.username for u in all_users]
    
    return render_template('dashboard.html', current_user=current_username, users=user_list)

# --- API для истории сообщений ---

@app.route('/api/history/<contact>')
def get_history(contact):
    if 'user' not in session:
        return jsonify([]), 401
    
    current_user = session['user']
    # Загружаем сообщения между текущим пользователем и выбранным контактом
    messages = Message.query.filter(
        or_(
            and_(Message.sender == current_user, Message.receiver == contact),
            and_(Message.sender == contact, Message.receiver == current_user)
        )
    ).order_by(Message.timestamp.asc()).all()

    return jsonify([{
        'sender': msg.sender,
        'receiver': msg.receiver,
        'text': msg.text,
        'timestamp': msg.timestamp.strftime('%H:%M')
    } for msg in messages])

# --- WebSockets события ---

@socketio.on('join')
def on_join():
    if 'user' in session:
        user_room = session['user']
        join_room(user_room)
        print(f"[SOCKET] User {user_room} connected to their private room.")

@socketio.on('send_message')
def handle_send_message(data):
    sender = session.get('user')
    receiver = data.get('receiver')
    text = data.get('text', '')[:16] # Жесткая обрезка до 16 симв.

    if sender and receiver and text:
        # 1. Сохраняем в базу данных
        new_msg = Message(sender=sender, receiver=receiver, text=text)
        db.session.add(new_msg)
        db.session.commit()

        # 2. Формируем данные для отправки
        msg_payload = {
            'sender': sender,
            'receiver': receiver,
            'text': text,
            'timestamp': datetime.utcnow().strftime('%H:%M')
        }

        # 3. Отправляем получателю (в его комнату) и себе (для мгновенного обновления)
        emit('new_message', msg_payload, room=receiver)
        emit('new_message', msg_payload, room=sender)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port)