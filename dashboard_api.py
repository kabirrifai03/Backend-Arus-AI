from flask import Blueprint, jsonify, request # <--- PASTIKAN 'request' ADA DI SINI!
from flask_jwt_extended import jwt_required, get_jwt_identity
from koneksi import get_conn
from datetime import datetime, timedelta
import random
from collections import defaultdict # Pastikan ini diimpor jika digunakan di run_prediction_model
import decimal # <-- Tambahkan impor ini
import os # Add this import
import google.generativeai as genai # Add this import
import requests # Add this import for making HTTP requests (though genai handles it)
from dotenv import load_dotenv # Add this import
import json


# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your .env file.")
genai.configure(api_key=GEMINI_API_KEY)

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    print(f"Menggunakan model Gemini: {model.model_name}")
except Exception as e:
    print(f"Gagal menginisialisasi model Gemini: {e}")
    model = None


dashboard_blueprint = Blueprint('dashboard', __name__)

@dashboard_blueprint.route('/dashboard/summary', methods=['GET'])
@jwt_required()
def dashboard_summary():
    user_id = get_jwt_identity()

    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)

            # Total aplikasi
            cur.execute("SELECT COUNT(*) as total FROM applications WHERE user_id = %s", (user_id,))
            total_applications = cur.fetchone()['total']

            # Jumlah fraud
            cur.execute("SELECT COUNT(*) as fraud FROM applications WHERE user_id = %s AND is_fraud = 1", (user_id,))
            fraud_count = cur.fetchone()['fraud']

            # Fraud rate
            fraud_rate = int((fraud_count / total_applications) * 100) if total_applications > 0 else 0

            # Chart data (per bulan)
            cur.execute("""
                SELECT DATE_FORMAT(date, '%%b') as month, COUNT(*) as value
                FROM applications
                WHERE user_id = %s
                GROUP BY DATE_FORMAT(date, '%%b')
                ORDER BY MIN(date)

            """, (user_id,))
            chart_data = cur.fetchall()

            # Customer composition
            cur.execute("""
                SELECT category AS name, COUNT(*) as value
                FROM customers
                WHERE user_id = %s
                GROUP BY category
            """, (user_id,))
            customer_composition = cur.fetchall()

            # Recent activities
            cur.execute("""
                SELECT id, title, timestamp, description
                FROM activities
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 5
            """, (user_id,))
            recent_activities = cur.fetchall()

            # Latest applications
            cur.execute("""
                SELECT id, borrower, amount, status, date
                FROM applications
                WHERE user_id = %s
                ORDER BY date DESC
                LIMIT 5
            """, (user_id,))
            latest_applications = cur.fetchall()

            # ✅ Hitung pemasukan dan pengeluaran
            cur.execute("""
                SELECT SUM(amount) AS income
                FROM transactions
                WHERE user_id = %s AND type = 'pemasukan'
            """, (user_id,))
            income = cur.fetchone()['income'] or 0

            cur.execute("""
                SELECT SUM(amount) AS expense
                FROM transactions
                WHERE user_id = %s AND type = 'pengeluaran'
            """, (user_id,))
            expense = cur.fetchone()['expense'] or 0

            margin = round(((income - expense) / income) * 100, 2) if income > 0 else 0

            # ✅ Tambahkan 'margin' ke response
            return jsonify({
            "fraud_count": fraud_count,
            "total_applications": total_applications,
            "fraud_rate": fraud_rate,
            "growth_percentage": 15,
            "chart_data": chart_data,
            # "customer_composition": customer_composition,
            "recent_activities": recent_activities,
            "latest_applications": latest_applications,
            "income": income,                 # ← Ditambahkan
            "expense": expense,              # ← Ditambahkan
            "margin": margin                 # ← Sudah ada
        })


    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_blueprint.route('/summary', methods=['GET'])
def get_summary():
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM summary_data")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(results)

@dashboard_blueprint.route('/dashboard/financial-health', methods=['GET'])
@jwt_required()
def financial_health():
    user_id = get_jwt_identity()

    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)

            cur.execute("""
                SELECT SUM(amount) AS income
                FROM transactions
                WHERE user_id = %s AND type = 'pemasukan'
            """, (user_id,))
            income = cur.fetchone()['income'] or 0

            cur.execute("""
                SELECT SUM(amount) AS expense
                FROM transactions
                WHERE user_id = %s AND type = 'pengeluaran'
            """, (user_id,))
            expense = cur.fetchone()['expense'] or 0

            margin = round(((income - expense) / income) * 100, 2) if income > 0 else 0

            return jsonify({
                "income": income,
                "expense": expense,
                "margin": margin
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Fungsi-fungsi Pembantu (Harus Didefinisikan di Awal) ---

def get_recent_transactions_for_ai(user_id, days=90):
    """
    Mengambil data transaksi terbaru dari database untuk user_id tertentu.
    Akan digunakan sebagai konteks untuk model AI.
    """
    try:
        with get_conn() as conn:
            cur = conn.cursor(dictionary=True)
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cur.execute("""
                SELECT date, amount, type
                FROM transactions
                WHERE user_id = %s AND date >= %s
                ORDER BY date ASC
            """, (user_id, cutoff_date))
            
            transactions_raw = cur.fetchall()
            
            formatted_transactions = []
            for tx in transactions_raw:
                formatted_tx = tx.copy()
                if isinstance(formatted_tx.get("amount"), decimal.Decimal):
                    formatted_tx["amount"] = float(formatted_tx["amount"])
                if isinstance(formatted_tx.get("date"), datetime):
                    formatted_tx["date"] = formatted_tx["date"].strftime("%Y-%m-%d")
                formatted_transactions.append(formatted_tx)
                
            return formatted_transactions
    except Exception as e:
        print(f"Error in get_recent_transactions_for_ai: {e}")
        return [] # Return empty list on error


# --- REVISI UTAMA DI SINI: ENDPOINT KONSULTASI AI ---
@dashboard_blueprint.route("/dashboard/predict", methods=["GET", "POST"])
@jwt_required()
def get_ai_consultation():
    print(f"[{datetime.now()}] Request received for /dashboard/predict ({request.method})")
    
    if model is None:
        print(f"[{datetime.now()}] Error: AI model is not initialized.")
        return jsonify({"error": "Failed to initialize AI model. Please check server logs."}), 500

    # Pastikan blok try ini memiliki indentasi yang benar (di bawah fungsi)
    try: # <--- INDENTASI TRY INI PENTING
        user_id = get_jwt_identity()
        print(f"[{datetime.now()}] User ID: {user_id}")

        if request.method == 'GET':
            print(f"[{datetime.now()}] Handling GET request for initial message.")
            return jsonify({
                "message": "Silakan masukkan detail bisnis Anda untuk mendapatkan saran AI.",
                "ai_advice": "Masukkan detail bisnis Anda di kolom yang tersedia dan klik 'Dapatkan Saran AI'."
            })

        if request.method == 'POST':
            print(f"[{datetime.now()}] Handling POST request for business consultation.")
            data = request.get_json()
            user_business_details = data.get('business_details', '')

            if not user_business_details:
                print(f"[{datetime.now()}] Error: business_details is empty.")
                return jsonify({"error": "Detail bisnis tidak boleh kosong."}), 400

            prompt = f"""
            Sebagai seorang ahli S3 konsultan bisnis AI yang memilik banyak pengalaman membantu bisnis hingga sukses, saya akan menganalisis informasi yang diberikan oleh seorang pengusaha UMKM (Usaha Mikro Kecil Menengah).
            Berikut adalah detail yang diberikan pengusaha tentang bisnis mereka:

            "{user_business_details}"

            Berdasarkan informasi ini, berikan analisis singkat dan saran strategis yang relevan dan personal untuk bisnis tersebut.
            Fokus pada area seperti potensi pertumbuhan, manajemen keuangan, strategi pemasukan, dan efisiensi pengeluaran.
            Berikan jawaban yang ramah, mudah dimengerti, dan langsung pada intinya serta jangan bertele tele. jangan gunakan teks bold karena nanti akan keluar **

            Format respons Anda dalam JSON berikut:
            {{
                "analysis_summary": "Ringkasan analisis singkat tentang kondisi bisnis yang diceritakan.",
                "strategic_advice": "Saran strategis personal untuk bisnis ini. (maksimal 200 kata, gunakan bullet points jika cocok)"
            }}

            Pastikan respons Anda dalam bahasa Indonesia yang baik dan benar.
            """
            
            print(f"[{datetime.now()}] Sending prompt to Gemini. Prompt length: {len(prompt)} chars.")
            response = model.generate_content(prompt, request_options={"timeout": 60})
            print(f"[{datetime.now()}] Received response from Gemini. Text length: {len(response.text)} chars.")

            response_text = response.text.strip()
            if response_text.startswith("```json") and response_text.endswith("```"):
                json_str = response_text[7:-3].strip()
            else:
                json_str = response_text
            
            print(f"[{datetime.now()}] Attempting to parse JSON string: {json_str[:500]}...")
            
            ai_consultation_data = json.loads(json_str)

            if not all(k in ai_consultation_data for k in ["analysis_summary", "strategic_advice"]):
                raise ValueError("AI response format is incorrect or incomplete. Missing keys.")

            print(f"[{datetime.now()}] Successfully parsed AI response.")
            return jsonify(ai_consultation_data)

    # Pastikan SEMUA blok 'except' ini memiliki indentasi yang SAMA dengan blok 'try' di atasnya.
    # INI ADALAH PENYEBAB PALING MUNGKIN DARI SYNTAXERROR.
    except json.JSONDecodeError as e: # <--- Perhatikan Indentasi Baris Ini
        print(f"[{datetime.now()}] Error parsing AI response JSON: {e}")
        print(f"[{datetime.now()}] Raw AI response (potentially truncated or malformed): {response_text}")
        return jsonify({
            "error": "Failed to parse AI consultation. Response might be incomplete or malformed JSON. Raw: " + response_text[:500]
        }), 500
    except ValueError as e: # <--- Perhatikan Indentasi Baris Ini
        print(f"[{datetime.now()}] AI response validation error: {e}")
        print(f"[{datetime.now()}] Raw AI response: {response_text}")
        return jsonify({
            "error": "AI provided an invalid format or incomplete data: " + str(e) + ". Raw: " + response_text[:500]
        }), 500
    except Exception as e: # <--- Perhatikan Indentasi Baris Ini
        print(f"[{datetime.now()}] Unexpected error during AI consultation: {e}")
        return jsonify({"error": f"Failed to get AI consultation: {str(e)}"}), 500
