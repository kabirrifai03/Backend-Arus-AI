<<<<<<< HEAD
from flask import Blueprint, request, jsonify, g
from app.models import db, Transaction  # pastikan Transaction juga diimport di sini
from groq_service import structure_receipt_from_image, classify_transaction
from user_api import token_required
import json
from datetime import datetime # Import datetime for current date and parsing

ocr_blueprint = Blueprint('ocr', __name__)

@ocr_blueprint.route('/process-receipt', methods=['POST'])
@token_required
def process_receipt_endpoint():
    user_id = g.user.id
=======
# ocr_api.py

import os
import base64
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from groq import Groq
from datetime import datetime

# Impor model dan session database dari proyek utama
from app.models import db, Transaction

# Inisialisasi Klien Groq (pastikan GROQ_API_KEY ada di file .env Anda)
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception as e:
    print(f"❌ Peringatan: Gagal menginisialisasi Groq Client. Error: {e}")
    client = None

# Buat Blueprint untuk OCR
ocr_blueprint = Blueprint('ocr', __name__)


# --- Helper Functions (dari groq_service.py) ---

def structure_receipt_from_image(image_file):
    """
    AI #1: Mengubah gambar nota/laporan menjadi JSON terstruktur.
    """
    image_bytes = base64.b64encode(image_file.read()).decode('utf-8')
    mime_type = image_file.mimetype
    
    prompt = """
        Anda adalah AI akuntan yang sangat teliti.
        Analisis gambar laporan keuangan ini baris per baris.
        Untuk setiap baris transaksi yang valid (abaikan 'Saldo' atau 'Total'), ekstrak informasi berikut:
        1. `date`: Tanggal transaksi dalam format YYYY-MM-DD. Jika tahun tidak ada, asumsikan tahun berjalan.
        2. `description`: Teks lengkap dari kolom 'Keterangan'.
        3. `income`: Angka dari kolom 'Pemasukan'. Jika kosong, nilainya 0.
        4. `expense`: Angka dari kolom 'Pengeluaran'. Jika kosong, nilainya 0.

        Hasilkan output HANYA dalam format JSON yang berisi satu kunci utama "transactions"
        yang nilainya adalah sebuah ARRAY dari objek transaksi. Contoh: {"transactions": [{"date": ...}, ...]}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_bytes}"},
                    },
                ],
            }
        ],
        model="llama3-groq-8b-8192-tool-use-preview", # Model yang support JSON mode
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2048,
    )
    
    return chat_completion.choices[0].message.content

# Catatan: Model 'Transaction' Anda tidak punya kolom 'category'.
# Fungsi 'classify_transaction' tidak akan digunakan untuk menyimpan ke DB,
# tapi bisa dipakai jika Anda ingin menampilkan kategori di response.
# Jika ingin menyimpan kategori, tambahkan kolom 'category' di model Transaction.

# --- API Endpoint ---

@ocr_blueprint.route('/process-receipt', methods=['POST'])
@jwt_required() # ✅ Menggunakan decorator dari Flask-JWT-Extended
def process_receipt_endpoint():
    # ✅ Mengambil user_id dari token JWT
    user_id = get_jwt_identity()
    
    if not client:
        return jsonify({"error": "Layanan AI tidak terkonfigurasi. Periksa GROQ_API_KEY."}), 503

>>>>>>> 4b73e29c84ae99afa1155b8cfa09a32981670d65
    if 'image' not in request.files:
        return jsonify({"error": "File gambar tidak ditemukan."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "File tidak dipilih."}), 400

<<<<<<< HEAD
    json_string = None 
    try:
        json_string = structure_receipt_from_image(file)
        data = json.loads(json_string) 

        transactions_data = data.get('transactions', [])
        
        transactions_to_save = []

        if isinstance(transactions_data, list):
            for trx in transactions_data:
                description = trx.get('description', '')
                amount_raw = trx.get('amount', 0) 
                # Langsung gunakan 'type' dari output AI. Default ke 'pengeluaran' jika tidak ada (walaupun prompt sudah mengaturnya)
                trx_type = trx.get('type', 'pengeluaran') 
                
                def clean_amount(value):
                    if isinstance(value, (int, float)): return value
                    if isinstance(value, str):
                        try:
                            # Menggunakan int(float(...)) untuk memastikan handling desimal jika ada, lalu ke integer
                            return int(float(value.replace('Rp', '').replace('.', '').replace(',', '').strip()))
                        except (ValueError, AttributeError): return 0
                    return 0
                
                amount = clean_amount(amount_raw)
                
                # Pastikan amount tidak negatif jika AI entah bagaimana mengembalikan negatif
                if amount < 0:
                    amount = 0

                # Periksa apakah tipe valid dan jumlahnya masuk akal
                if trx_type in ['pemasukan', 'pengeluaran']: 
                    transaction_date_str = trx.get('date')
                    transaction_date = datetime.now().date() 
                    if transaction_date_str:
                        try:
                            # Parsing tanggal yang lebih robust jika diperlukan, atau cukup percaya AI
                            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            # Jika format dari AI salah, fallback ke tanggal sekarang
                            pass 
                    
                    new_transaction = Transaction(
                        user_id=user_id,
                        description=description,
                        amount=float(amount), # Pastikan ini float sesuai model
                        type=trx_type, 
                        # Tidak ada 'category' yang dikirim ke model jika memang tidak ada kolomnya
                        date=transaction_date
                    )
                    transactions_to_save.append(new_transaction)
                else:
                    print(f"Skipping transaction due to invalid type: {trx_type} for description: {description}")


        if transactions_to_save:
            db.session.add_all(transactions_to_save)
            db.session.commit()
            
            return jsonify({
                "message": "Laporan berhasil diproses dan disimpan.",
                "saved_count": len(transactions_to_save)
            }), 201
        else:
            return jsonify({"message": "Tidak ada transaksi valid yang terdeteksi untuk disimpan."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "raw_output_from_ai": json_string}), 500
=======
    json_string_from_ai = ""
    try:
        # 1. Panggil AI untuk mengekstrak data dari gambar
        json_string_from_ai = structure_receipt_from_image(file)
        data = json.loads(json_string_from_ai)

        # Ambil list transaksi dari kunci 'transactions'
        transactions = data.get('transactions', [])
        
        if not isinstance(transactions, list):
             return jsonify({
                 "error": "Format JSON dari AI tidak sesuai, array 'transactions' tidak ditemukan.",
                 "raw_output_from_ai": json_string_from_ai
            }), 500

        saved_count = 0
        for item in transactions:
            # 2. Proses setiap item transaksi
            description = item.get('description', '')
            income = float(item.get('income', 0))
            expense = float(item.get('expense', 0))
            date_str = item.get('date')

            if not date_str or not description:
                continue # Lewati jika data penting tidak ada

            # Tentukan tipe dan jumlah
            trx_type = None
            amount = 0
            if income > 0:
                trx_type = 'pemasukan'
                amount = income
            elif expense > 0:
                trx_type = 'pengeluaran'
                amount = expense
            
            if not trx_type or amount <= 0:
                continue # Lewati jika tidak ada jumlah yang valid
            
            # 3. Simpan ke database menggunakan SQLAlchemy
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                new_transaction = Transaction(
                    user_id=user_id,
                    type=trx_type,
                    description=description.strip(),
                    amount=amount,
                    date=date_obj
                )
                db.session.add(new_transaction)
                saved_count += 1
            except (ValueError, TypeError) as e:
                # Lewati item ini jika tanggal tidak valid
                print(f"Skipping item due to invalid date: {date_str}, Error: {e}")
                continue

        if saved_count > 0:
            db.session.commit()
            return jsonify({
                "message": f"{saved_count} transaksi berhasil diproses dan disimpan."
            }), 201
        else:
            return jsonify({"message": "Tidak ada transaksi valid yang dapat disimpan dari gambar."}), 200

    except Exception as e:
        db.session.rollback() # ✅ Rollback jika terjadi kesalahan
        return jsonify({
            "error": f"Terjadi kesalahan: {str(e)}",
            "raw_output_from_ai": json_string_from_ai
        }), 500
>>>>>>> 4b73e29c84ae99afa1155b8cfa09a32981670d65
