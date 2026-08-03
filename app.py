import os
import uuid
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "vault-pro-super-secret-key"

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            is_private BOOLEAN NOT NULL,
            password_hash TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')

        if not username or not full_name or not password:
            return render_template('register.html', error="All fields are required.")

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, full_name, password_hash) VALUES (?, ?, ?)",
                           (username, full_name, hashed_pw))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username already taken.")

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['full_name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_name = request.form.get('full_name', '').strip()
    if new_name:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET full_name = ? WHERE id = ?", (new_name, session['user_id']))
        conn.commit()
        conn.close()
        session['full_name'] = new_name

    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, original_name, is_private FROM files WHERE user_id = ?", (session['user_id'],))
    user_files = cursor.fetchall()
    conn.close()

    return render_template('dashboard.html', full_name=session['full_name'], files=user_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('file')
    file_password = request.form.get('file_password', '').strip()

    if not file or file.filename == '':
        return redirect(url_for('dashboard'))

    file_id = str(uuid.uuid4())[:8]
    original_name = secure_filename(file.filename)
    saved_filename = f"{file_id}_{original_name}"

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(file_path)

    is_private = bool(file_password)
    password_hash = generate_password_hash(file_password) if is_private else None

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO files (id, user_id, filename, original_name, is_private, password_hash) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, session['user_id'], saved_filename, original_name, is_private, password_hash)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# --- NEW RENAME ROUTE ---
@app.route('/rename/<file_id>', methods=['POST'])
def rename_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_filename = request.form.get('new_name', '').strip()
    if new_filename:
        # Ensure filename keeps extension if omitted
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE files SET original_name = ? WHERE id = ? AND user_id = ?", 
                       (secure_filename(new_filename), file_id, session['user_id']))
        conn.commit()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/file/<file_id>', methods=['GET', 'POST'])
def view_file(file_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT filename, original_name, is_private, password_hash FROM files WHERE id = ?", (file_id,))
    file_data = cursor.fetchone()
    conn.close()

    if not file_data:
        return "File not found", 404

    filename, original_name, is_private, password_hash = file_data

    if not is_private:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    if request.method == 'POST':
        entered_password = request.form.get('password', '')
        if check_password_hash(password_hash, entered_password):
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        else:
            return render_template('password_prompt.html', file_id=file_id, error="Incorrect file password!")

    return render_template('password_prompt.html', file_id=file_id, error=None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

@app.route('/')
def index():
    return "VaultPro is running successfully!"
