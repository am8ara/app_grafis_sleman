import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="Laporan Grafis ATR/BPN Sleman", page_icon="📝")

# Nama file penyimpanan data
FILE_DATA = 'data_laporan.csv'

# --- FUNGSI BANTUAN ---

def load_data():
    """Memuat data dari file CSV jika ada, jika tidak buat baru."""
    if os.path.exists(FILE_DATA):
        return pd.read_csv(FILE_DATA)
    else:
        # Membuat struktur data kosong jika file belum ada
        return pd.DataFrame(columns=[
            'Tanggal Input', 
            'Nomor Berkas', 
            'Tahun Berkas', 
            'Jam Layanan', 
            'Status', 
            'Keterangan'
        ])

def save_data(df):
    """Menyimpan data ke file CSV."""
    df.to_csv(FILE_DATA, index=False)

# --- APLIKASI UTAMA ---

def main():
    st.title("📝 Laporan Harian Petugas Grafis")
    st.markdown("**Seksi Survey dan Pemetaan - ATR/BPN Sleman**")

    # Menu Navigasi di Sidebar
    menu = st.sidebar.radio("Menu", ["Input Laporan", "Rekap Harian"])

    # Memuat data yang sudah ada
    df = load_data()

    # --- MENU 1: INPUT LAPORAN ---
    if menu == "Input Laporan":
        st.subheader("Form Input Data Baru")
        
        with st.form("form_laporan", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nomor_berkas = st.text_input("Nomor Berkas")
                tahun_berkas = st.number_input("Tahun Berkas", min_value=2000, max_value=2100, step=1, value=datetime.now().year)
            
            with col2:
                jam_layanan = st.time_input("Jam Layanan", value=datetime.now())
                status = st.selectbox("Status Layanan", ["Terlayani", "Tidak Terlayani"])
            
            keterangan = st.text_area("Keterangan (Opsional)")
            
            # Tombol Submit
            submitted = st.form_submit_button("Simpan Laporan")
            
            if submitted:
                if nomor_berkas:
                    # Menyiapkan data baru
                    new_data = {
                        'Tanggal Input': datetime.now().strftime("%Y-%m-%d"),
                        'Nomor Berkas': nomor_berkas,
                        'Tahun Berkas': tahun_berkas,
                        'Jam Layanan': str(jam_layanan),
                        'Status': status,
                        'Keterangan': keterangan
                    }
                    
                    # Menggabungkan data baru dengan data lama
                    # Menggunakan pd.concat untuk menghindari warning append
                    new_df = pd.DataFrame([new_data])
                    df = pd.concat([df, new_df], ignore_index=True)
                    
                    save_data(df)
                    st.success("✅ Data berhasil disimpan!")
                else:
                    st.error("❌ Nomor berkas wajib diisi.")

    # --- MENU 2: REKAP HARIAN ---
    elif menu == "Rekap Harian":
        st.subheader("Rekapitulasi Laporan")

        # Filter Tanggal
        tanggal_pilih = st.date_input("Pilih Tanggal", value=datetime.now())
        tanggal_str = tanggal_pilih.strftime("%Y-%m-%d")

        # Filter Dataframe berdasarkan tanggal
        if not df.empty:
            df_harian = df[df['Tanggal Input'] == tanggal_str]
            
            # Menampilkan Statistik Ringkas
            total = len(df_harian)
            terlayani = len(df_harian[df_harian['Status'] == 'Terlayani'])
            belum = len(df_harian[df_harian['Status'] == 'Tidak Terlayani'])

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Berkas", total)
            col_b.metric("Terlayani", terlayani)
            col_c.metric("Tidak Terlayani", belum)

            st.markdown("---")
            
            # Menampilkan Tabel
            if total > 0:
                st.dataframe(df_harian, use_container_width=True)
                
                # Tombol Download
                csv = df_harian.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Rekap Hari Ini (CSV)",
                    csv,
                    f"rekap_{tanggal_str}.csv",
                    "text/csv"
                )
            else:
                st.info(f"Belum ada data laporan untuk tanggal {tanggal_str}")
        else:
            st.info("Belum ada data sama sekali di sistem.")

if __name__ == '__main__':
    main()