import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from fpdf import FPDF
import base64

# --- KONFIGURASI ---
st.set_page_config(page_title="Sistem Laporan ATR/BPN", page_icon="🔐")

# --- KONEKSI GOOGLE SHEETS ---
def get_db_connection():
    # Mengambil credentials dari Secrets Streamlit
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Membaca secrets dari konfigurasi Streamlit Cloud
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Buka Spreadsheet (Ganti nama sesuai nama file Google Sheet Anda)
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
    
    # Header Tabel
    cols = dataframe.columns
    for col in cols:
        pdf.cell(30, 10, str(col)[:15], 1, 0, 'C') # Potong nama kolom jika kepanjangan
    pdf.ln()
    
    # Isi Tabel
    for index, row in dataframe.iterrows():
        for col in cols:
            data_str = str(row[col])
            pdf.cell(30, 10, data_str[:15], 1, 0)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- HALAMAN LOGIN ---
def login_page():
    st.title("🔐 Login Petugas")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            try:
                sh = get_db_connection()
                ws_users = sh.worksheet("Users")
                users_data = ws_users.get_all_records()
                
                user_found = False
                for user in users_data:
                    # Cek username dan password (sederhana)
                    # Di real app, password harusnya di-hash
                    if str(user['Username']) == username and str(user['Password']) == password:
                        st.session_state['logged_in'] = True
                        st.session_state['role'] = user['Role']
                        st.session_state['username'] = user['Username']
                        st.session_state['nama'] = user['Nama Lengkap']
                        user_found = True
                        st.success("Login Berhasil!")
                        st.rerun()
                        break
                
                if not user_found:
                    st.error("Username atau Password salah.")
            except Exception as e:
                st.error(f"Gagal koneksi ke database: {e}")

# --- DASHBOARD ADMIN ---
def admin_dashboard():
    st.title(f"👤 Admin Panel: {st.session_state['nama']}")
    
    tab1, tab2 = st.tabs(["Rekap & PDF", "Manajemen User"])
    
    sh = get_db_connection()
    
    with tab1:
        st.subheader("Download Laporan Harian")
        tanggal_pilih = st.date_input("Pilih Tanggal Laporan", value=datetime.now())
        tanggal_str = tanggal_pilih.strftime("%Y-%m-%d")
        
        if st.button("Tampilkan Data"):
            ws_laporan = sh.worksheet("Laporan")
            data = ws_laporan.get_all_records()
            df = pd.DataFrame(data)
            
            # Filter tanggal
            df_harian = df[df['Tanggal Input'] == tanggal_str]
            
            if not df_harian.empty:
                st.dataframe(df_harian)
                
                # Generate PDF
                pdf_bytes = generate_pdf(df_harian, tanggal_str)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="Laporan_{tanggal_str}.pdf">📄 Download PDF Laporan Harian</a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.warning("Tidak ada data pada tanggal tersebut.")

    with tab2:
        st.subheader("Tambah Pengguna Baru")
        with st.form("add_user"):
            new_user = st.text_input("Username Baru")
            new_pass = st.text_input("Password")
            new_role = st.selectbox("Role", ["petugas", "admin"])
            new_nama = st.text_input("Nama Lengkap")
            
            if st.form_submit_button("Tambah User"):
                ws_users = sh.worksheet("Users")
                ws_users.append_row([new_user, new_pass, new_role, new_nama])
                st.success(f"User {new_user} berhasil ditambahkan.")

# --- DASHBOARD PETUGAS ---
def petugas_dashboard():
    st.title(f"👋 Halo, {st.session_state['nama']}")
    st.info("Silakan input laporan harian Anda di bawah ini.")
    
    with st.form("input_laporan", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nomor_berkas = st.text_input("Nomor Berkas")
            tahun_berkas = st.number_input("Tahun", value=datetime.now().year)
        with col2:
            jam = st.time_input("Jam Layanan", value=datetime.now())
            status = st.selectbox("Status", ["Terlayani", "Tidak Terlayani"])
        
        ket = st.text_area("Keterangan")
        
        if st.form_submit_button("Kirim Laporan"):
            try:
                sh = get_db_connection()
                ws_laporan = sh.worksheet("Laporan")
                
                data_baru = [
                    datetime.now().strftime("%Y-%m-%d"),
                    nomor_berkas,
                    tahun_berkas,
                    str(jam),
                    status,
                    ket,
                    st.session_state['nama'] # Mencatat siapa yang input
                ]
                
                ws_laporan.append_row(data_baru)
                st.success("✅ Laporan berhasil dikirim ke server.")
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")

# --- MAIN CONTROLLER ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        # Tombol Logout di Sidebar
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()
            
        if st.session_state['role'] == 'admin':
            admin_dashboard()
        else:
            petugas_dashboard()

if __name__ == '__main__':
    main()
