import os
from datetime import datetime
import qrcode
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, session
from flask_sqlalchemy import SQLAlchemy
import io
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__) 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "mektan_inventory_secret_2026"
db = SQLAlchemy(app)



USERNAME = "admin"
PASSWORD = "@12345"

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == USERNAME and request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            session["username"] = USERNAME
            return redirect("/dashboard")
        return render_template("login.html", error="Username atau password salah")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.before_request
def require_login():
    allowed = ["login", "static"]
    if request.endpoint in allowed:
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


# DATABASE MODELS

class Ruangan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_ruangan = db.Column(db.String(100), unique=True, nullable=False)
    barang_barang = db.relationship('Barang', backref='lokasi_ruangan', lazy=True)

class Barang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nup = db.Column(db.String(100), unique=True, nullable=False)  
    kode_barang = db.Column(db.String(100), nullable=False)  
    nama_barang = db.Column(db.String(200), nullable=False)  
    merk = db.Column(db.String(100))  
    tahun_perolehan = db.Column(db.String(10))  
    status = db.Column(db.String(50), nullable=False)  
    dipakai_oleh = db.Column(db.String(100))  
    ruangan_id = db.Column(db.Integer, db.ForeignKey('ruangan.id'), nullable=True)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aktivitas = db.Column(db.Text, nullable=False)
    user = db.Column(db.String(100), default="admin")
    waktu = db.Column(db.DateTime, default=datetime.utcnow)

# DASHBOARD UTAMA
@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/dashboard")
def home():
    semua_barang = Barang.query.all()
    semua_history = History.query.order_by(History.waktu.desc()).all()
    semua_ruangan = Ruangan.query.all()

    return render_template(
        "home.html",
        barang=semua_barang,
        history=semua_history,
        ruangan=semua_ruangan,
        total_barang=Barang.query.count(),
        total_tersedia=Barang.query.filter_by(status="tersedia").count(),
        total_dipakai=Barang.query.filter_by(status="dipakai").count(),
        total_rusak=Barang.query.filter_by(status="rusak").count()
    ) 

# MENU DAFTAR RUANGAN + GENERATE QR CODE RUANGAN (LEBAR MENYESUAIKAN TEKS)
@app.route("/ruangan", methods=["GET"])
def menu_ruangan():
    semua_ruangan = Ruangan.query.all()
    
    qr_folder = os.path.join(app.root_path, "static", "qr_ruangan")  
    os.makedirs(qr_folder, exist_ok=True)
    
    for r in semua_ruangan:
        qr_path = os.path.join(qr_folder, f"ruangan_{r.id}.png")
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(str(r.nama_ruangan))
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        
        qw, qh = img_qr.size
        
        # Load Font
        target_font_size = 20
        try:
            font = ImageFont.truetype("arial.ttf", target_font_size)
        except IOError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", target_font_size)
            except IOError:
                font = ImageFont.load_default()
                
        teks_baris_1 = f"{r.nama_ruangan.upper()}"
        teks_baris_2 = "LOKASI RUANGAN"
        
        # Buat dummy image untuk menghitung panjang teks asli
        dummy_img = Image.new("RGB", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        w_teks1 = dummy_draw.textlength(teks_baris_1, font=font) if hasattr(dummy_draw, 'textlength') else len(teks_baris_1)*12
        w_teks2 = dummy_draw.textlength(teks_baris_2, font=font) if hasattr(dummy_draw, 'textlength') else len(teks_baris_2)*12
        
        # Cari teks paling panjang dan tentukan lebar kanvas baru (+ padding 40 pixel biar ga mepet)
        teks_terpanjang = max(w_teks1, w_teks2)
        lebar_baru = int(max(qw, teks_terpanjang + 40))
        tinggi_baru = qh + 100
        
        canvas_baru = Image.new("RGB", (lebar_baru, tinggi_baru), "white")
        
        # Tempel QR code tepat di tengah-tengah secara horizontal
        x_qr = int((lebar_baru - qw) / 2)
        canvas_baru.paste(img_qr, (x_qr, 0))
        
        draw = ImageDraw.Draw(canvas_baru)
        x_teks1 = (lebar_baru - w_teks1) / 2
        x_teks2 = (lebar_baru - w_teks2) / 2
        
        draw.text((x_teks1, qh + 10), teks_baris_1, fill="black", font=font)
        draw.text((x_teks2, qh + 45), teks_baris_2, fill="red", font=font)
        
        canvas_baru.save(qr_path)

    return render_template("ruangan.html", ruangan=semua_ruangan)

# HALAMAN DETAIL BARANG PER RUANGAN
@app.route("/ruangan/<int:id>")
def detail_isi_ruangan(id):
    ruangan = Ruangan.query.get_or_404(id)
    barang_di_ruangan = Barang.query.filter_by(ruangan_id=id).all()
    return render_template("isi_ruangan.html", ruangan=ruangan, barang=barang_di_ruangan)

# EXPORT EXCEL SATUAN
@app.route("/export_barang/<int:id>")
def export_barang_single(id):
    b = Barang.query.get_or_404(id)
    nama_ruangan = b.lokasi_ruangan.nama_ruangan if b.ruangan_id else "Belum Ditempatkan"
    
    data = [{
        "Kode Barang": b.nup,             
        "Kode UPB": b.kode_barang,        
        "Nama Barang": b.nama_barang,
        "Merk": b.merk or "-",
        "Tahun Perolehan": b.tahun_perolehan or "-",
        "Status": b.status.capitalize(),
        "Lokasi Ruangan": nama_ruangan,
        "Dipakai Oleh": b.dipakai_oleh or "-"
    }]
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data Barang')
    output.seek(0)
    
    nama_file = f"Barang_{b.nup}.xlsx"
    return send_file(output, as_attachment=True, download_name=nama_file, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# EXPORT EXCEL FULL SATU RUANGAN
@app.route("/export_ruangan/<int:id>")
def export_ruangan_all(id):
    ruangan = Ruangan.query.get_or_404(id)
    barang_di_ruangan = Barang.query.filter_by(ruangan_id=id).all()
    
    data_list = []
    for b in barang_di_ruangan:
        data_list.append({
            "Kode Barang": b.nup,         
            "Kode UPB": b.kode_barang,    
            "Nama Barang": b.nama_barang,
            "Merk": b.merk or "-",
            "Tahun Perolehan": b.tahun_perolehan or "-",
            "Status": b.status.capitalize(),
            "Dipakai Oleh": b.dipakai_oleh or "-"
        })
        
    df = pd.DataFrame(data_list)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'Aset {ruangan.nama_ruangan[:20]}')
    output.seek(0)
    
    nama_file = f"Laporan_Ruangan_{ruangan.nama_ruangan.replace(' ', '_')}.xlsx"
    return send_file(output, as_attachment=True, download_name=nama_file, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# EXPORT EXCEL BERDASARKAN NAMA USER
@app.route("/export_user/<string:nama_user>")
def export_barang_user(nama_user):
    barang_user = Barang.query.filter_by(status="dipakai", dipakai_oleh=nama_user).all()
    
    if not barang_user:
        return "Tidak ada data barang yang sedang dipakai oleh user ini.", 404
        
    data_list = []
    for b in barang_user:
        nama_ruangan = b.lokasi_ruangan.nama_ruangan if b.ruangan_id else "Belum Ditempatkan"
        data_list.append({
            "Kode Barang": b.nup,             
            "Kode UPB": b.kode_barang,        
            "Nama Barang": b.nama_barang,
            "Merk": b.merk or "-",
            "Tahun Perolehan": b.tahun_perolehan or "-",
            "Status": b.status.capitalize(),
            "Lokasi Ruangan": nama_ruangan,
            "Dipakai Oleh": b.dipakai_oleh
        })
        
    df = pd.DataFrame(data_list)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'Aset_{nama_user[:20]}')
    output.seek(0)
    
    nama_file = f"Laporan_Aset_{nama_user.replace(' ', '_')}.xlsx"
    return send_file(output, as_attachment=True, download_name=nama_file, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# TAMBAH RUANGAN
@app.route("/tambah_ruangan", methods=["POST"])
def tambah_ruangan():
    nama_ruangan = request.form["nama_ruangan"]
    existing = Ruangan.query.filter_by(nama_ruangan=nama_ruangan).first()
    if not existing:
        ruangan_baru = Ruangan(nama_ruangan=nama_ruangan)
        db.session.add(ruangan_baru)
        db.session.commit()
    return redirect("/ruangan")

# HAPUS RUANGAN
@app.route("/hapus_ruangan/<int:id>")
def hapus_ruangan(id):
    ruangan = Ruangan.query.get_or_404(id)
    for b in ruangan.barang_barang:
        b.ruangan_id = None
    db.session.delete(ruangan)
    db.session.commit()
    return redirect("/ruangan")

# TAMBAH BARANG + GENERATE QR CODE BARANG (LEBAR OTOMATIS MENGIKUTI TEKS KODE UPB)
@app.route("/tambah", methods=["POST"])
def tambah_barang():
    ruangan_id = request.form.get("ruangan_id")
    if ruangan_id == "": ruangan_id = None

    nup = request.form["nup"]                  
    kode_barang = request.form["kode_barang"]  
    tahun_perolehan = request.form["tahun_perolehan"] or "-"

    barang_baru = Barang(  
        nup=nup,  
        kode_barang=kode_barang,  
        nama_barang=request.form["nama_barang"],  
        merk=request.form["merk"],  
        tahun_perolehan=tahun_perolehan,  
        status=request.form["status"],
        ruangan_id=ruangan_id,
        dipakai_oleh=request.form.get("dipakai_oleh") if request.form["status"] == "dipakai" else None
    )  
    db.session.add(barang_baru)  
    db.session.commit()

    db.session.add(History(aktivitas=f"Menambahkan barang: {barang_baru.nama_barang} ({barang_baru.kode_barang})"))
    db.session.commit()

    qr_folder = os.path.join(app.root_path, "static", "qr_barcodes")  
    os.makedirs(qr_folder, exist_ok=True)  
    qr_path = os.path.join(qr_folder, f"{barang_baru.nup}.png")  
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(str(barang_baru.nup))
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    qw, qh = img_qr.size
    
    # Load Font
    target_font_size = 20 
    try:
        font = ImageFont.truetype("arial.ttf", target_font_size)
    except IOError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", target_font_size)
        except IOError:
            font = ImageFont.load_default()
        
    teks_baris_1 = f"{nup}.{tahun_perolehan}"  
    teks_baris_2 = f"{kode_barang}"           
    
    # Hitung panjang teks asli menggunakan canvas dummy
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    w_teks1 = dummy_draw.textlength(teks_baris_1, font=font) if hasattr(dummy_draw, 'textlength') else len(teks_baris_1)*12
    w_teks2 = dummy_draw.textlength(teks_baris_2, font=font) if hasattr(dummy_draw, 'textlength') else len(teks_baris_2)*12
    
    # Logika Baru: Ambil panjang teks yang paling melar ke samping + kasih padding 40px
    teks_terpanjang = max(w_teks1, w_teks2)
    lebar_baru = int(max(qw, teks_terpanjang + 40))
    tinggi_baru = qh + 100  # Tinggi proporsional tidak kepanjangan kebawah lagi
    
    canvas_baru = Image.new("RGB", (lebar_baru, tinggi_baru), "white")
    
    # Tempel QR code tepat di tengah secara horizontal
    x_qr = int((lebar_baru - qw) / 2)
    canvas_baru.paste(img_qr, (x_qr, 0))
    
    draw = ImageDraw.Draw(canvas_baru)
    x_teks1 = (lebar_baru - w_teks1) / 2
    x_teks2 = (lebar_baru - w_teks2) / 2
    
    # Cetak teks pas di tengah ruangan putih bawah
    draw.text((x_teks1, qh + 10), teks_baris_1, fill="black", font=font)
    draw.text((x_teks2, qh + 45), teks_baris_2, fill="black", font=font)
    
    canvas_baru.save(qr_path)
        
    return redirect("/")  

# EDIT BARANG
@app.route("/edit/<int:id>", methods=["POST"])
def edit_barang(id):
    barang = Barang.query.get_or_404(id)

    status_lama = barang.status

    barang.nup = request.form["nup"]
    barang.kode_barang = request.form["kode_barang"]
    barang.nama_barang = request.form["nama_barang"]
    barang.merk = request.form["merk"]
    barang.tahun_perolehan = request.form["tahun_perolehan"]
    barang.status = request.form["status"]

    ruangan_id = request.form.get("ruangan_id")
    barang.ruangan_id = int(ruangan_id) if ruangan_id else None

    if barang.status == "dipakai":
        barang.dipakai_oleh = request.form.get("dipakai_oleh")
    else:
        barang.dipakai_oleh = None

    if status_lama != barang.status:
        history = History(
            aktivitas=f"Mengubah status barang '{barang.nama_barang}' dari '{status_lama}' menjadi '{barang.status}'"
        )
        db.session.add(history)

    db.session.commit()

    return redirect("/")

# HAPUS BARANG
@app.route("/hapus/<int:id>")
def hapus_barang(id):
    barang = Barang.query.get_or_404(id)
    qr_file = os.path.join(app.root_path, "static", "qr_barcodes", f"{barang.nup}.png")
    if os.path.exists(qr_file):
        os.remove(qr_file)
    db.session.add(History(aktivitas=f"Menghapus barang: {barang.nama_barang} ({barang.kode_barang})"))
    db.session.delete(barang)
    db.session.commit()
    return redirect("/")

# SCAN QR CODE & BARCODE
@app.route("/scan", methods=["GET", "POST"])
def scan():
    barang = None  
    status_scan = None
    
    if request.method == "POST":  
        scanned_value = request.form["nup"].strip()  
        
        cek_ruangan = Ruangan.query.filter(Ruangan.nama_ruangan.like(f"%{scanned_value}%")).first()
        if cek_ruangan:
            return redirect(url_for('detail_isi_ruangan', id=cek_ruangan.id))
            
        barang = Barang.query.filter_by(nup=scanned_value).first()  
        if barang:
            status_scan = "sukses"
        else:
            status_scan = "gagal"
            
    return render_template("scan.html", barang=barang, status_scan=status_scan)  

if __name__ == "__main__":
    with app.app_context():  
        db.create_all()  
    app.run(debug=True)

