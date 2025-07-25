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
    if 'image' not in request.files:
        return jsonify({"error": "File gambar tidak ditemukan."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "File tidak dipilih."}), 400

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