import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from fpdf import FPDF
import base64
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Laporan ATR/BPN", page_icon="🔐", layout="wide")

# --- KONEKSI GOOGLE SHEETS ---
def get_db_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sh = client.open("Database_Laporan_BPN") 
    return sh

# --- FUNGSI PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Laporan Harian Petugas Grafis - ATR/BPN Sleman', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Halaman {self.page_no()}', 0, 0, 'C')

def generate_pdf(dataframe, tanggal):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Tanggal Laporan: {tanggal}", 0, 1)
    
    # Header
    cols = ["No. Berkas", "Tahun", "Jam", "Status", "Ket", "Petugas"]
    # Mapping nama kolom df ke header
    # Kita asumsikan urutan kolom dataframe sesuai
    
    col_width = [30, 20, 30, 35, 40, 35]
    
    for i, col in enumerate(cols):
        pdf.cell(col_width[i], 10, col, 1, 0, 'C')
    pdf.ln()
    
    # Isi
    for index, row in dataframe.iterrows():
        pdf.cell(col_width[0], 10, str(row['Nomor Berkas'])[:15], 1, 0)
        pdf.cell(col_width[1], 10, str(row['Tahun Berkas']), 1, 0)
        pdf.cell(col_width[2], 10, str(row['Jam Layanan']), 1, 0)
        pdf.cell(col_width[3], 10, str(row['Status']), 1, 0)
        pdf.cell(col_width[4], 10, str(row['Keterangan'])[:20], 1, 0)
        pdf.cell(col_width[5], 10, str(row['Petugas'])[:18], 1, 0)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIKA MANAJEMEN DATA ---

def get_data_with_index(worksheet):
    """Mengambil data beserta nomor baris aslinya di Google Sheets"""
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    # Menambahkan kolom index baris (mulai dari 2 karena baris 1 adalah header)
    if not df.empty:
        df['row_index'] = range(2, len(df) + 2)
    return df

def manage_reports_ui(role, user_fullname):
    """Komponen UI untuk Edit/Hapus yang dipakai Admin dan Petugas"""
    
    st.subheader("📂 Manajemen Data Laporan")
    
    try:
        sh = get_db_connection()
        ws_laporan = sh.worksheet("Laporan")
        df = get_data_with_index(ws_laporan)
        
        if df.empty:
            st.info("Belum ada data laporan.")
            return

        # Filter Data Sesuai Role
        if role == "petugas":
            # Petugas hanya melihat datanya sendiri
            df_view = df[df['Petugas'] == user_fullname]
        else:
            # Admin melihat semua
            df_view = df

        # Tampilkan Tabel
        st.dataframe(df_view.drop(columns=['row_index']), use_container_width=True)
        st.write("---")

        # --- BAGIAN EDIT / HAPUS ---
        st.write("#### 🛠️ Edit atau Hapus Laporan")
        
        # Pilih Laporan berdasarkan list
        # Kita buat label yang mudah dibaca untuk dropdown
        df_view['label'] = df_view['Tanggal Input'] + " | " + df_view['Nomor Berkas'] + " | " + df_view['Petugas']
        
        pilihan = st.selectbox("Pilih Laporan untuk dikelola:", df_view['label'].tolist())
        
        # Ambil data baris yang dipilih
        selected_row = df_view[df_view['label'] == pilihan].iloc[0]
        row_idx = int(selected_row['row_index'])
        tanggal_laporan = selected_row['Tanggal Input']
        
        # Logika Penguncian (Locking)
        hari_ini = datetime.now().strftime("%Y-%m-%d")
        is_locked = False
        
        if role == "petugas" and tanggal_laporan != hari_ini:
            is_locked = True
            st.warning(f"🔒 Laporan ini terkunci karena dibuat pada tanggal {tanggal_laporan}. Petugas hanya bisa mengedit laporan hari ini.")

        # Form Edit
        with st.form("edit_form"):
            st.write(f"**Mengedit data baris ke-{row_idx}**")
            col1, col2 = st.columns(2)
            
            # Pre-fill data lama
            new_nomor = col1.text_input("Nomor Berkas", value=selected_row['Nomor Berkas'], disabled=is_locked)
            new_tahun = col1.number_input("Tahun", value=int(selected_row['Tahun Berkas']), disabled=is_locked)
            new_jam = col2.text_input("Jam Layanan (HH:MM:SS)", value=selected_row['Jam Layanan'], disabled=is_locked)
            
            # Cari index status lama
            status_opts = ["Terlayani", "Tidak Terlayani"]
            try:
                idx_stat = status_opts.index(selected_row['Status'])
            except:
                idx_stat = 0
            new_status = col2.selectbox("Status", status_opts, index=idx_stat, disabled=is_locked)
            
            new_ket = st.text_area("Keterangan", value=selected_row['Keterangan'], disabled=is_locked)

            c1, c2 = st.columns([1, 4])
            with c1:
                update_btn = st.form_submit_button("💾 Simpan Perubahan", disabled=is_locked)
            
            if update_btn and not is_locked:
                # Update ke Google Sheets
                # Urutan kolom di Sheet: Tanggal, Nomor, Tahun, Jam, Status, Ket, Petugas
                # Kita update cell satu per satu atau range. Update range lebih aman.
                # Kolom B (2) sampai F (6). Tanggal (A) dan Petugas (G) tidak diubah.
                
                ws_laporan.update_cell(row_idx, 2, new_nomor) # Nomor
                ws_laporan.update_cell(row_idx, 3, new_tahun) # Tahun
                ws_laporan.update_cell(row_idx, 4, str(new_jam)) # Jam
                ws_laporan.update_cell(row_idx, 5, new_status) # Status
                ws_laporan.update_cell(row_idx, 6, new_ket)   # Keterangan
                
                st.success("Data berhasil diperbarui! Mohon tunggu sebentar...")
                time.sleep(2)
                st.rerun()

        # Tombol Hapus (Di luar form agar tidak tereksekusi enter)
        if not is_locked:
            st.write("")
            if st.button("🗑️ Hapus Laporan Ini", type="primary"):
                ws_laporan.delete_rows(row_idx)
                st.success("Data berhasil dihapus.")
                time.sleep(2)
                st.rerun()

    except Exception as e:
        st.error(f"Terjadi kesalahan koneksi: {e}")

# --- HALAMAN UTAMA ---

def login_page():
    st.title("🔐 Login Petugas")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk"):
            sh = get_db_connection()
            ws = sh.worksheet("Users")
            users = ws.get_all_records()
            
            found = False
            for u in users:
                if str(u['Username']) == username and str(u['Password']) == password:
                    st.session_state.update({
                        'logged_in': True,
                        'role': u['Role'],
                        'nama': u['Nama Lengkap'],
                        'username': u['Username']
                    })
                    found = True
                    st.success("Login sukses!")
                    st.rerun()
                    break
            if not found:
                st.error("Username/Password salah.")

def admin_dashboard():
    st.title(f"Admin Panel: {st.session_state['nama']}")
    tab1, tab2, tab3 = st.tabs(["📥 Download PDF", "🛠️ Manajemen Laporan", "👥 Manajemen User"])
    
    with tab1:
        sh = get_db_connection()
        ws = sh.worksheet("Laporan")
        df = pd.DataFrame(ws.get_all_records())
        
        tgl = st.date_input("Pilih Tanggal", value=datetime.now())
        tgl_str = tgl.strftime("%Y-%m-%d")
        
        if st.button("Preview & Download"):
            df_filter = df[df['Tanggal Input'] == tgl_str]
            if not df_filter.empty:
                st.dataframe(df_filter)
                pdf_bytes = generate_pdf(df_filter, tgl_str)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="Laporan_{tgl_str}.pdf">👉 Download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.warning("Data kosong.")

    with tab2:
        # Admin bisa edit semua data tanpa batasan waktu
        manage_reports_ui("admin", st.session_state['nama'])

    with tab3:
        st.write("Tambah User Baru")
        with st.form("new_user"):
            u = st.text_input("Username")
            p = st.text_input("Password")
            r = st.selectbox("Role", ["petugas", "admin"])
            n = st.text_input("Nama Lengkap")
            if st.form_submit_button("Simpan User"):
                sh = get_db_connection()
                sh.worksheet("Users").append_row([u, p, r, n])
                st.success("User ditambahkan.")

def petugas_dashboard():
    st.title(f"Halo, {st.session_state['nama']}")
    
    tab1, tab2 = st.tabs(["📝 Input Laporan", "🗂️ Riwayat & Kelola"])
    
    with tab1:
        with st.form("input"):
            c1, c2 = st.columns(2)
            nb = c1.text_input("Nomor Berkas")
            th = c1.number_input("Tahun", value=datetime.now().year)
            jm = c2.time_input("Jam", value=datetime.now())
            stt = c2.selectbox("Status", ["Terlayani", "Tidak Terlayani"])
            ket = st.text_area("Keterangan")
            
            if st.form_submit_button("Kirim"):
                sh = get_db_connection()
                sh.worksheet("Laporan").append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    nb, th, str(jm), stt, ket, st.session_state['nama']
                ])
                st.success("Terkirim!")

    with tab2:
        # Petugas hanya bisa edit datanya sendiri & dibatasi waktu
        manage_reports_ui("petugas", st.session_state['nama'])

def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        
    if not st.session_state['logged_in']:
        login_page()
    else:
        with st.sidebar:
            st.write(f"User: **{st.session_state['username']}**")
            if st.button("Logout"):
                st.session_state['logged_in'] = False
                st.rerun()
                
        if st.session_state['role'] == 'admin':
            admin_dashboard()
        else:
            petugas_dashboard()

if __name__ == '__main__':
    main()
