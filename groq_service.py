# app/services/groq_service.py
import os
import base64
from groq import Groq
import json


# Inisialisasi Klien Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def structure_receipt_from_image(image_file):
    """
    AI #1: Mengubah gambar nota/laporan menjadi JSON terstruktur.
    Mengekstrak tanggal, deskripsi, jumlah, dan menentukan tipe (pemasukan/pengeluaran).
    Desain untuk robust terhadap error deteksi.
    """
    image_bytes = base64.b64encode(image_file.read()).decode('utf-8')
    mime_type = image_file.mimetype
    
    # PROMPT YANG DIPERBARUI
    prompt = """
    Anda adalah AI akuntan yang sangat teliti dan selalu berusaha menghasilkan data yang akurat dari laporan keuangan.
    Analisis setiap baris transaksi pada gambar laporan ini secara seksama.
    Abaikan baris yang berisi 'Saldo bulan lalu' atau 'Total'.

    Untuk setiap transaksi yang terdeteksi, ekstrak informasi berikut dengan instruksi spesifik untuk penanganan error:

    1.  ⁠ date ⁠:
        -   Ambil tanggal dari kolom 'Tgl'.
        -   *Format Wajib:* YYYY-MM-DD.
        -   *Penanganan Error:* Jika tahun tidak terdeteksi, asumsikan tahunnya 2020. Jika tanggal tidak ada sama sekali atau tidak terbaca, gunakan tanggal saat ini (format YYYY-MM-DD). Jangan biarkan kosong.

    2.  ⁠ description ⁠:
        -   Ambil teks lengkap dari kolom 'Keterangan'.
        -   *Penanganan Error:* Jika kosong atau tidak terbaca, gunakan string kosong "".

    3.  ⁠ amount ⁠:
        -   Ini adalah *nilai numerik tunggal* dari transaksi.
        -   Prioritaskan angka dari kolom 'Pemasukan' jika ada nilai positif di sana.
        -   Jika 'Pemasukan' kosong atau nol, prioritaskan angka dari kolom 'Pengeluaran'.
        -   *PENTING:* Ekstrak *hanya angka murni*. Hapus semua simbol mata uang (seperti 'Rp'), pemisah ribuan (titik '.' atau koma ','), atau teks lain yang tidak numerik.
        -   *Penanganan Error:* Jika angka tidak terdeteksi dengan jelas atau tidak valid di kedua kolom, nilai ⁠ amount ⁠ *harus 0 (nol)*. Jangan mencoba menebak angka.

    4.  ⁠ type ⁠:
        -   Tentukan apakah transaksi ini adalah 'pemasukan' atau 'pengeluaran'.
        -   *Prioritas Deteksi:*
            -   Jika nilai ⁠ amount ⁠ diambil dari kolom 'Pemasukan' (yaitu, ⁠ Pemasukan ⁠ > 0 dan ⁠ Pengeluaran ⁠ = 0), maka ⁠ type ⁠ adalah 'pemasukan'.
            -   Jika nilai ⁠ amount ⁠ diambil dari kolom 'Pengeluaran' (yaitu, ⁠ Pengeluaran ⁠ > 0 dan ⁠ Pemasukan ⁠ = 0), maka ⁠ type ⁠ adalah 'pengeluaran'.
        -   *Penanganan Konflik/Ambiguitas (Penting):*
            -   Jika *kedua kolom 'Pemasukan' dan 'Pengeluaran' memiliki angka positif* (misalnya, ada koreksi), tentukan ⁠ type ⁠ berdasarkan nilai yang *lebih dominan*. Jika 'Pemasukan' lebih besar, ⁠ type ⁠ adalah 'pemasukan'. Jika 'Pengeluaran' lebih besar, ⁠ type ⁠ adalah 'pengeluaran'.
            -   Jika *nilai ⁠ amount ⁠ adalah 0* (karena tidak terdeteksi), tentukan ⁠ type ⁠ berdasarkan analisis ⁠ description ⁠:
                -   'pemasukan' jika ⁠ description ⁠ sangat jelas menunjukkan penjualan, penerimaan uang, pinjaman yang masuk, atau setoran modal (contoh: "Penjualan...", "Terima transfer...", "Pinjaman masuk...", "Setoran dana...").
                -   'pengeluaran' jika ⁠ description ⁠ sangat jelas menunjukkan pembelian, pembayaran biaya, gaji, sewa, atau pengeluaran operasional (contoh: "Beli...", "Bayar listrik...", "Gaji karyawan...", "Sewa kantor...").
            -   *DEFAULT (Jika Masih Tidak Jelas):* Jika setelah semua analisis ⁠ type ⁠ masih tidak dapat ditentukan dengan yakin atau ⁠ description ⁠ juga ambigu, ⁠ type ⁠ *harus diatur ke 'pengeluaran'* sebagai default yang aman.

    Hasilkan output HANYA dalam format JSON. Formatnya harus berupa array valid dari objek transaksi, yang kemudian dibungkus dalam sebuah objek JSON dengan kunci 'transactions'.

    Contoh format output:
    ⁠ json
    {
      "transactions": [
        {
          "date": "2020-09-02",
          "description": "Penjualan cat 2.5L (1 buah)",
          "amount": 190000,
          "type": "pemasukan"
        },
        {
          "date": "2020-09-05",
          "description": "Pembayaran invoice stok tanki 600L (5 buah)",
          "amount": 4500000,
          "type": "pengeluaran"
        },
        {
          "date": "2020-09-10",
          "description": "Penjualan baut",
          "amount": 70000,
          "type": "pemasukan"
        },
        {
          "date": "2020-09-28",
          "description": "Biaya tak terduga",
          "amount": 0,
          "type": "pengeluaran"
        }
      ]
    }
     ⁠
    Pastikan setiap angka adalah integer atau float, bukan string.
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
        model="meta-llama/llama-4-scout-17b-16e-instruct", # Pastikan ini model yang kuat untuk visi dan JSON
        response_format={"type": "json_object"}, 
        temperature=0.1, # Rendah untuk konsistensi data
        max_tokens=2048,
    )
    
    raw_content = chat_completion.choices[0].message.content
    try:
        parsed_data = json.loads(raw_content)
        # Pastikan output selalu dalam format {"transactions": [...]}, bahkan jika AI hanya mengembalikan array
        if 'transactions' not in parsed_data:
            return json.dumps({"transactions": parsed_data}) 
        return raw_content # Jika sudah dalam format yang benar
    except json.JSONDecodeError as e:
        print(f"Warning: AI output not valid JSON. Error: {e}. Raw output: {raw_content}")
        # Jika AI gagal memberikan JSON yang valid, berikan struktur kosong untuk menghindari crash
        return json.dumps({"transactions": []})


def classify_transaction(description: str) -> str:
    """
    AI #2: Mengklasifikasikan deskripsi transaksi ke dalam kategori yang ditentukan.
    """
    categories = "Penjualan, Bahan Baku, Gaji, Sewa, Utilitas, Marketing, Aset Tetap, Suntikan Dana, Pinjaman, Lainnya"
    
    prompt = f"""
        Anda adalah AI akuntan. Klasifikasikan deskripsi transaksi ini ke dalam SATU kategori dari daftar berikut: [{categories}].
        Deskripsi: '{description}'.
        Kembalikan hanya nama kategorinya saja.
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0,
        )
        category = chat_completion.choices[0].message.content.strip()
        
        return category if category in categories.split(', ') else "Lainnya"
    except Exception:
        return "Lainnya"

