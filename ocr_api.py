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

    if 'image' not in request.files:
        return jsonify({"error": "File gambar tidak ditemukan."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "File tidak dipilih."}), 400

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