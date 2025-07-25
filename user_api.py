from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from koneksi import get_conn, Error  # pool koneksi dari db.py
import bcrypt
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended import verify_jwt_in_request
from flask import g
from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        g.user = type('User', (object,), {'id': user_id})()  # Sementara buat object user tiruan
        return f(*args, **kwargs)
    return decorated

# Create the akun blueprint
user_blueprint = Blueprint('user', __name__)

# --- 1. User Registration Endpoint ---
@user_blueprint.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # Validate input data
    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400
    
    username = data['username']
    password = data['password']
    
    # Check if username already exists
    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM akun WHERE username = %s", (username,))
            existing_user = cur.fetchone()

            if existing_user:
                return jsonify({"error": "Username already exists."}), 400

            # Hash the password before saving it (ensure it is bytes)
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            # Create a new akun and add to the database
            cur.execute("INSERT INTO akun (username, password) VALUES (%s, %s)",
                        (username, hashed_password))
            conn.commit()

            # Get the new akun's ID
            cur.execute("SELECT id FROM akun WHERE username = %s", (username,))
            new_user = cur.fetchone()

            # Generate JWT token for the newly registered akun
            access_token = create_access_token(identity=str(new_user['id']),expires_delta=False)

            return jsonify({"message": "User registered successfully!", "access_token": access_token}), 201

    except Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500


# --- 2. User Login Endpoint ---
@user_blueprint.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    # Validate input data
    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400

    username = data['username']
    password = data['password']

    try:
        # Fetch the akun from the database
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM akun WHERE username = %s", (username,))
            akun = cur.fetchone()

            if akun and bcrypt.checkpw(password.encode('utf-8'), akun['password'].encode('utf-8')):

                # Create an access token using JWT (using string user_id)
                access_token = create_access_token(identity=str(akun['id']),expires_delta=False)
                return jsonify({"access_token": access_token}), 200
            else:
                return jsonify({"error": "Invalid credentials"}), 401

    except Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500

# --- 3. Get Current User Profile (Protected) ---
@user_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()

    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, username, full_name, phone_number, photo_url, npwp_number, has_npwp, business_description FROM akun WHERE id = %s", (user_id,))
            user = cur.fetchone()

            if not user:
                return jsonify({"error": "User not found"}), 404

            return jsonify(user), 200

    except Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500
    
    
@user_blueprint.route('/profile/update', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.get_json()

    try:
        with get_conn() as conn:
            cur = conn.cursor()

            cur.execute("""
                UPDATE akun
                SET full_name = %s,
                    email = %s,
                    phone_number = %s,
                    npwp_number = %s,
                    address = %s,
                    photo_url = %s,
                    business_description = %s
                WHERE id = %s
            """, (
                data.get("namaLengkap"),
                data.get("email"),
                data.get("noTelepon"),
                data.get("npwp"),
                data.get("alamat"),
                data.get("fotoProfil"),
                data.get("business_description"),  # tambahkan ini
                user_id
            ))

            conn.commit()
            return jsonify({"message": "Profil berhasil diperbarui."}), 200

    except Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500


__all__ = ["user_blueprint", "token_required"]
