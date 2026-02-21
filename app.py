from flask import Flask, jsonify, request, render_template, redirect, url_for
import requests, sqlite3, webbrowser, os, json
from googletrans import Translator

app = Flask(__name__)
DB_PATH = "reviews.db"
translator = Translator()

# ---------- INITIAL DATABASE ----------

# ---------- INITIAL DATABASE ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT
        )
    """)
    # Add a default admin user if not exists
    cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ('admin', '1234'))
    conn.commit()
    conn.close()

init_db()

# ---------- HELPER: Export to Text File ----------
def export_to_textfile():
    """Exports DB content to a readable table format in a text file."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        with open("DATABASE_LOG.txt", "w", encoding="utf-8") as f:
            f.write("==================================================================================\n")
            f.write("                             MOBILITY ASSISTANCE DATABASE                         \n")
            f.write("==================================================================================\n\n")
            
            # --- USERS TABLE ---
            f.write("REGISTERED USERS\n")
            f.write(f"{'ID':<5} | {'USERNAME':<20} | {'PASSWORD':<15} | {'EMAIL'}\n")
            f.write("-" * 80 + "\n")
            
            cursor.execute("SELECT id, username, password, email FROM users")
            users = cursor.fetchall()
            if users:
                for u in users:
                    uid = str(u[0])
                    name = str(u[1]) if u[1] else ""
                    pwd = str(u[2]) if u[2] else ""
                    eml = str(u[3]) if u[3] else ""
                    f.write(f"{uid:<5} | {name:<20} | {pwd:<15} | {eml}\n")
            else:
                f.write("(No users found)\n")
            f.write("-" * 80 + "\n\n")
            
            # --- REVIEWS TABLE ---
            f.write("USER REVIEWS\n")
            f.write(f"{'ID':<5} | {'USERNAME':<20} | {'MESSAGE'}\n")
            f.write("-" * 80 + "\n")
            
            cursor.execute("SELECT id, username, message FROM reviews")
            reviews = cursor.fetchall()
            if reviews:
                for r in reviews:
                    rid = str(r[0])
                    rname = str(r[1]) if r[1] else "Anonymous"
                    rmsg = str(r[2]).replace("\n", " ") if r[2] else ""
                    f.write(f"{rid:<5} | {rname:<20} | {rmsg}\n")
            else:
                f.write("(No reviews found)\n")
            f.write("-" * 80 + "\n")
        
        conn.close()
    except Exception as e:
        print(f"Error exporting data: {e}")

# ---------- LOGIN ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
    return render_template('login.html')

# ---------- REGISTER ----------
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, password, email))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    
    if success:
        export_to_textfile() # <--- Export data immediately
        return jsonify({'success': True, 'message': 'Registration successful! Redirecting to login...', 'redirect': url_for('login')})
    else:
        return jsonify({'success': False, 'error': 'Username already exists'}), 409

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ---------- REVIEWS ----------
@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        username = request.form.get('username', 'Anonymous')
        message = request.form.get('message')
        if message:
            cursor.execute("INSERT INTO reviews (username, message) VALUES (?, ?)", (username, message))
            conn.commit()
            export_to_textfile() # <--- Export data immediately

    cursor.execute("SELECT username, message FROM reviews ORDER BY id DESC")
    all_reviews = cursor.fetchall()
    conn.close()
    return render_template('reviews.html', reviews=all_reviews)

# ---------- NAVIGATION ----------
@app.route('/navigation')
def navigation():
    return render_template('navigation.html')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    return redirect(url_for('login'))

# ---------- OVERPASS API PROXY (Real-Time Data) ----------
@app.route('/api/wheelmap')
def overpass_proxy():
    """
    Fetches real-time accessibility data from OpenStreetMap via Overpass API.
    """
    bbox = request.args.get('bbox')
    if not bbox:
        return jsonify({"error": "No bbox provided"}), 400

    # Convert bbox "min_lon,min_lat,max_lon,max_lat" -> "south,west,north,east"
    try:
        min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
    except ValueError:
        return jsonify({"error": "Invalid bbox format"}), 400

    # Overpass QL Query
    # Fetch all public places: amenities, shops, tourism, AND wheelchair-tagged places
    query = f"""
    [out:json][timeout:30];
    (
      node["amenity"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["tourism"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["wheelchair"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["wheelchair"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center tags;
    """

    overpass_url = "https://overpass-api.de/api/interpreter"
    
    try:
        response = requests.get(overpass_url, params={'data': query}, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return jsonify(data) # Direct pass-through of Overpass JSON
        else:
            return jsonify({"error": "Overpass API failed", "status": response.status_code})
    except Exception as e:
        print(f"Overpass Error: {e}")
        return jsonify({"error": str(e)})

# ---------- ADMIN DATA VIEW ----------
@app.route('/admin/data')
def admin_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM reviews")
    reviews = cursor.fetchall()
    
    conn.close()
    return render_template('admin_data.html', users=users, reviews=reviews)

# ---------- SPEECH TRANSLATION API ----------
@app.route('/api/translate', methods=['POST'])
def translate_text():
    try:
        data = request.get_json()
        text = data.get('text')
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400
        
        translator = Translator()
        # Detect and translate to English
        translation = translator.translate(text, dest='en')
        
        return jsonify({
            'success': True, 
            'original_text': text,
            'translated_text': translation.text,
            'src_lang': translation.src
        })
    except Exception as e:
        print(f"Translation Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------- MAIN ----------
if __name__ == '__main__':
    print("🚀 Server running at http://127.0.0.1:5000")
    print("📂 View Database Data at http://127.0.0.1:5000/admin/data")
    # Only open browser in the FIRST process, not in the Flask reloader subprocess
    import os
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)
