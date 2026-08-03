import streamlit as st
import sqlite3
from datetime import datetime, timedelta

# --- STILIZACIJA ---
st.markdown("""
<style>
.stApp { background-color: #1e1e1e; color: white; }
div[data-testid="stMetric"] { background-color: #2b2b2b; border: 2px solid #d4af37; padding: 15px; border-radius: 15px; }
.stMarkdown p { color: white !important; font-weight: 600; }
.stMarkdown { color: white; }
.stButton > button { background-color: #2b2b2b; color: #d4af37; border: 2px solid #d4af37; border-radius: 10px; }
.stButton > button:hover { background-color: #d4af37; color: black; }
h2, h3 { color: white !important; }
div[data-baseweb="input"] { background-color: #2b2b2b; border: 1px solid #d4af37; border-radius: 10px; }
div[data-baseweb="select"] { background-color: #2b2b2b; }
input { color: white !important; background-color: #2b2b2b !important; }
[data-testid="stDateInput"] * { color: white !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: white !important; }
div[data-testid="stMetric"] [data-testid="stMetricLabel"] { color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('termini.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rezervacije (
        id INTEGER PRIMARY KEY,
        usluga TEXT,
        datum TEXT,
        vreme TEXT,
        ime TEXT,
        telefon TEXT,
        cena INTEGER,
        status TEXT DEFAULT 'zakazan',
        payment_method TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cenovnik (
        usluga TEXT PRIMARY KEY,
        cena INTEGER,
        trajanje INTEGER
    )''')
    usluge = [
        ('💇 Šišanje', 1500, 45),
        ('💇 Šišanje + pranje kose', 1900, 60),
        ('💇 Šišanje + brada', 2000, 60),
        ('💇 Šišanje + brada + pranje kose', 2400, 75),
        ('💇 Šišanje + brada + pranje kose + obrve', 2800, 90),
        ('🧔 Brada (samo)', 1000, 30),
        ('✨ Obrve (samo)', 400, 15)
    ]
    c.executemany("INSERT OR IGNORE INTO cenovnik (usluga, cena, trajanje) VALUES (?, ?, ?)", usluge)
    try: c.execute("ALTER TABLE rezervacije ADD COLUMN status TEXT DEFAULT 'zakazan'")
    except: pass
    try: c.execute("ALTER TABLE rezervacije ADD COLUMN payment_method TEXT")
    except: pass
    conn.commit()
    conn.close()

# --- SLOTOVI ---
def generisi_slotove_za_dan(datum):
    conn = sqlite3.connect('termini.db')
    c = conn.cursor()
    pocetak = datetime.strptime(f"{datum} 09:00", "%Y-%m-%d %H:%M")
    kraj = datetime.strptime(f"{datum} 20:00", "%Y-%m-%d %H:%M")
    trenutno = pocetak
    while trenutno < kraj:
        if trenutno >= datetime.strptime(f"{datum} 12:00", "%Y-%m-%d %H:%M") and \
           trenutno < datetime.strptime(f"{datum} 13:00", "%Y-%m-%d %H:%M"):
            trenutno += timedelta(minutes=30)
            continue
        vreme = trenutno.strftime("%H:%M")
        c.execute("SELECT * FROM rezervacije WHERE datum=? AND vreme=?", (datum, vreme))
        if not c.fetchone():
            c.execute("""INSERT INTO rezervacije (usluga, datum, vreme, ime, telefon, cena, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (None, datum, vreme, None, None, None, 'zakazan'))
        trenutno += timedelta(minutes=30)
    conn.commit()
    conn.close()

# --- POMOĆNE ---
def formatiraj_datum(datum):
    return datum.strftime("%d.%m.%Y.")

def generisi_datume():
    danas = datetime.now().date()
    return [danas + timedelta(days=i) for i in range(7)]

def osvezi_termine():
    for datum in generisi_datume():
        generisi_slotove_za_dan(datum)

# --- REZERVACIJE ---
def proveri_slotove_za_uslugu(datum, vreme, trajanje):
    conn = sqlite3.connect('termini.db')
    c = conn.cursor()
    c.execute("SELECT vreme, ime FROM rezervacije WHERE datum=? ORDER BY vreme ASC", (datum,))
    svi = c.fetchall()
    conn.close()
    start = None
    for i, (slot_vreme, ime) in enumerate(svi):
        if slot_vreme == vreme:
            start = i
            break
    if start is None: return None
    broj = trajanje // 30
    if start + broj > len(svi): return None
    potrebni = []
    prethodno = None
    for i in range(broj):
        slot_vreme, ime = svi[start + i]
        if ime is not None: return None
        if prethodno:
            t1 = datetime.strptime(prethodno, "%H:%M")
            t2 = datetime.strptime(slot_vreme, "%H:%M")
            if (t2 - t1).seconds // 60 != 30: return None
        potrebni.append(slot_vreme)
        prethodno = slot_vreme
    return potrebni

def rezervisi_slotove(datum, slotovi, ime, telefon, usluga_ime, usluga_cena, usluga_trajanje):
    try:
        conn = sqlite3.connect('termini.db')
        c = conn.cursor()
        prvi = True
        for slot_vreme in slotovi:
            if prvi: cena = usluga_cena; prvi = False
            else: cena = 0
            c.execute("""UPDATE rezervacije SET ime=?, telefon=?, usluga=?, cena=?, status='zakazan'
                WHERE datum=? AND vreme=?""", (ime, telefon, usluga_ime, cena, datum, slot_vreme))
        conn.commit(); conn.close()
        return True
    except Exception as e: st.error(e); return False

# --- METRIKE ---
def get_unique_clients_count_for_date(datum):
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""SELECT COUNT(DISTINCT ime || '|' || telefon || '|' || usluga) FROM rezervacije
        WHERE datum=? AND ime IS NOT NULL AND status='zakazan'""", (datum,))
    count = c.fetchone()[0]; conn.close(); return count

def get_unique_clients_count_next_7_days():
    today = datetime.now().date(); end_date = today + timedelta(days=6)
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""SELECT COUNT(DISTINCT ime || '|' || telefon || '|' || usluga) FROM rezervacije
        WHERE datum BETWEEN ? AND ? AND ime IS NOT NULL AND status='zakazan'""", (today, end_date))
    count = c.fetchone()[0]; conn.close(); return count

def get_earnings_breakdown_for_date(datum):
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""SELECT payment_method, SUM(cena) FROM (SELECT ime, telefon, usluga, payment_method, MAX(cena) AS cena
        FROM rezervacije WHERE datum=? AND status='naplacen' GROUP BY ime, telefon, usluga, payment_method)
        GROUP BY payment_method""", (datum,))
    results = c.fetchall(); conn.close()
    kes = kartica = 0
    for method, total in results:
        if method == 'Keš': kes = total if total else 0
        elif method == 'Kartica': kartica = total if total else 0
    return kes + kartica, kes, kartica

def get_monthly_earnings_breakdown():
    today = datetime.now().date(); first_day = today.replace(day=1)
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""SELECT payment_method, SUM(cena) FROM (SELECT ime, telefon, usluga, payment_method, MAX(cena) AS cena
        FROM rezervacije WHERE datum BETWEEN ? AND ? AND status='naplacen' GROUP BY ime, telefon, usluga, payment_method)
        GROUP BY payment_method""", (first_day, today))
    results = c.fetchall(); conn.close()
    kes = kartica = 0
    for method, total in results:
        if method == 'Keš': kes = total if total else 0
        elif method == 'Kartica': kartica = total if total else 0
    return kes + kartica, kes, kartica

def get_yearly_earnings_breakdown():
    today = datetime.now().date(); first_day = today.replace(month=1, day=1)
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""SELECT payment_method, SUM(cena) FROM (SELECT ime, telefon, usluga, payment_method, MAX(cena) AS cena
        FROM rezervacije WHERE datum BETWEEN ? AND ? AND status='naplacen' GROUP BY ime, telefon, usluga, payment_method)
        GROUP BY payment_method""", (first_day, today))
    results = c.fetchall(); conn.close()
    kes = kartica = 0
    for method, total in results:
        if method == 'Keš': kes = total if total else 0
        elif method == 'Kartica': kartica = total if total else 0
    return kes + kartica, kes, kartica

def moze_naplata(datum, vremena):
    sada = datetime.now()
    if isinstance(datum, str): termin_datum = datetime.strptime(datum, "%Y-%m-%d").date()
    else: termin_datum = datum
    if termin_datum > sada.date(): return False
    if termin_datum == sada.date():
        poslednje_vreme = max(vremena)
        termin_vreme = datetime.strptime(poslednje_vreme, "%H:%M").time()
        if termin_vreme > sada.time(): return False
    return True

def otkazi_termin(rezervacija_id):
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("""UPDATE rezervacije SET ime=NULL, telefon=NULL, usluga=NULL, cena=NULL,
        status='zakazan', payment_method=NULL WHERE id=?""", (rezervacija_id,))
    conn.commit(); conn.close()

def naplati_termin(rezervacija_id, payment_method):
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("UPDATE rezervacije SET status='naplacen', payment_method=? WHERE id=?", (payment_method, rezervacija_id))
    conn.commit(); conn.close()

# --- KLIJENTSKI DEO ---
def prikazi_usluge():
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("SELECT usluga, cena, trajanje FROM cenovnik ORDER BY trajanje ASC")
    usluge = c.fetchall(); conn.close()
    st.write("### 💈 Korak 1: Odaberite uslugu"); st.write("---")
    cols = st.columns(2)
    for i, u in enumerate(usluge):
        with cols[i % 2]:
            ime_usluge, cena, trajanje = u
            st.markdown(f"**{ime_usluge}**")
            st.caption(f"{trajanje} min • {cena} din")
            if st.button(f"Izaberi", key=f"usl_{i}"):
                st.session_state['izabrana_usluga'] = {'ime': ime_usluge, 'cena': cena, 'trajanje': trajanje}
                st.session_state['izabrani_termin'] = None; st.rerun()
            st.write("---")

def prikazi_slotove(datum):
    conn = sqlite3.connect('termini.db'); c = conn.cursor()
    c.execute("SELECT vreme, ime FROM rezervacije WHERE datum=? ORDER BY vreme ASC", (datum,))
    svi_slotovi = c.fetchall(); conn.close()
    if not svi_slotovi: st.caption("Nema dostupnih termina."); return
    st.write("### ⏰ Korak 2: Odaberite vreme")
    red = []
    for vreme, ime in svi_slotovi:
        if "12:00" <= vreme < "13:00": red.append("PAUZA")
        elif ime is not None: red.append(f"🔴 {vreme}")
        else: red.append(vreme)
    for i in range(0, len(red), 3):
        kolone = st.columns(3)
        for j in range(3):
            index = i + j
            if index < len(red):
                termin = red[index]
                with kolone[j]:
                    if termin == "PAUZA":
                        st.button("🚫 PAUZA", disabled=True, use_container_width=True, key=f"pauza_{i}_{j}")
                    elif termin.startswith("🔴"):
                        st.button(termin, disabled=True, use_container_width=True, key=f"zauzet_{termin}")
                    else:
                        if st.button(f"🟢 {termin}", key=f"slot_{termin}_{datum}", use_container_width=True):
                            st.session_state['izabrani_termin'] = termin; st.rerun()

# ============================================================
# KALENDAR - STREAMLIT KOLONE SA DUGMADIMA + EXPANDER
# ============================================================
def prikaz_nedeljnog_kalendara():
    st.subheader("📅 Nedeljni pregled (30 min slotovi)")

    # --- 1. Datumi ---
    danas = datetime.now().date()
    pocetak_nedelje = danas - timedelta(days=danas.weekday())
    datumi = [pocetak_nedelje + timedelta(days=i) for i in range(7)]

    # --- 2. Zauzeti termini ---
    conn = sqlite3.connect('termini.db')
    c = conn.cursor()
    placeholders = ','.join(['?'] * len(datumi))
    c.execute(f"""
        SELECT datum, vreme, ime, telefon, usluga, cena, status, id FROM rezervacije
        WHERE datum IN ({placeholders})
        AND ime IS NOT NULL
    """, [d.strftime('%Y-%m-%d') for d in datumi])
    zauzeti = c.fetchall()
    conn.close()

    # Filtriraj naplaćene
    zauzeti = [row for row in zauzeti if row[6] != 'naplacen']

    podaci_termina = {}
    for row in zauzeti:
        datum, vreme, ime, telefon, usluga, cena, status, id = row
        podaci_termina[(datum, vreme)] = (ime, telefon, usluga, cena, id)

    # --- 3. Slotovi ---
    slotovi = []
    trenutno = datetime.strptime("09:00", "%H:%M")
    kraj = datetime.strptime("20:00", "%H:%M")
    while trenutno < kraj:
        vreme_str = trenutno.strftime("%H:%M")
        if "12:00" <= vreme_str < "13:00":
            trenutno += timedelta(minutes=30)
            continue
        slotovi.append(vreme_str)
        trenutno += timedelta(minutes=30)

    # --- 4. Prikaz tabele sa Streamlit kolonama ---
    # Zaglavlje
    header_cols = st.columns([0.5] + [1]*7)
    with header_cols[0]:
        st.markdown("**Vreme**")
    for i, d in enumerate(datumi):
        with header_cols[i+1]:
            st.markdown(f"**{d.strftime('%a')}**<br><small>{d.strftime('%d.%m.')}</small>", unsafe_allow_html=True)

    # Redovi
    for slot in slotovi:
        cols = st.columns([0.5] + [1]*7)
        with cols[0]:
            st.write(slot)

        for i, d in enumerate(datumi):
            datum_str = d.strftime('%Y-%m-%d')
            key = (datum_str, slot)
            with cols[i+1]:
                if key in podaci_termina:
                    # Zauzeto - crveno dugme
                    if st.button("🔴", key=f"z_{datum_str}_{slot}", help="Zauzet termin", use_container_width=True):
                        ime, telefon, usluga, cena, id_termin = podaci_termina[key]
                        st.session_state['kalendar_klik'] = {
                            'tip': 'zauzet',
                            'datum': datum_str,
                            'vreme': slot,
                            'ime': ime,
                            'telefon': telefon,
                            'usluga': usluga,
                            'cena': cena,
                            'id': id_termin
                        }
                        st.rerun()
                else:
                    # Slobodno - zeleno dugme
                    if st.button("🟢", key=f"s_{datum_str}_{slot}", help="Slobodan termin", use_container_width=True):
                        st.session_state['kalendar_klik'] = {
                            'tip': 'slobodan',
                            'datum': datum_str,
                            'vreme': slot
                        }
                        st.rerun()

    # --- 5. Prikaz expandera ---
    if 'kalendar_klik' in st.session_state and st.session_state['kalendar_klik']:
        klik = st.session_state['kalendar_klik']
        tip = klik['tip']
        datum = klik['datum']
        vreme = klik['vreme']

        if tip == 'zauzet':
            with st.expander("👤 Detalji klijenta", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Ime:** {klik['ime']}")
                    st.write(f"**Telefon:** {klik['telefon']}")
                with col2:
                    st.write(f"**Usluga:** {klik['usluga']}")
                    st.write(f"**Cena:** {klik['cena']} din")
                st.write(f"**Datum:** {datum}  **Vreme:** {vreme}")
                
                st.write("---")
                col_akcije = st.columns(4)
                with col_akcije[0]:
                    if st.button("✖️ Zatvori", use_container_width=True):
                        del st.session_state['kalendar_klik']
                        st.rerun()
                with col_akcije[1]:
                    if st.button("🗑️ Obriši", use_container_width=True):
                        conn = sqlite3.connect('termini.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM rezervacije WHERE id=?", (klik['id'],))
                        conn.commit()
                        conn.close()
                        del st.session_state['kalendar_klik']
                        st.rerun()
                with col_akcije[2]:
                    if st.button("💰 Naplati", use_container_width=True):
                        conn = sqlite3.connect('termini.db')
                        c = conn.cursor()
                        c.execute("UPDATE rezervacije SET status='naplacen', payment_method='Keš' WHERE id=?", (klik['id'],))
                        conn.commit()
                        conn.close()
                        del st.session_state['kalendar_klik']
                        st.rerun()
                with col_akcije[3]:
                    if st.button("🔄 Prezakazi", use_container_width=True):
                        st.session_state['prezakazi_termin'] = {
                            'id': klik['id'],
                            'datum': datum,
                            'vreme': vreme
                        }
                        del st.session_state['kalendar_klik']
                        st.rerun()

        elif tip == 'slobodan':
            with st.expander("📝 Novi termin", expanded=True):
                st.write(f"**Datum:** {datum}  **Vreme:** {vreme}")
                
                with st.form(key="novi_termin_kalendar"):
                    ime = st.text_input("Ime i prezime *")
                    telefon = st.text_input("Telefon *")

                    conn = sqlite3.connect('termini.db')
                    c = conn.cursor()
                    c.execute("SELECT usluga, cena, trajanje FROM cenovnik ORDER BY trajanje ASC")
                    usluge = c.fetchall()
                    conn.close()

                    usluga_opcije = [f"{u[0]} ({u[2]} min, {u[1]} din)" for u in usluge]
                    izabrana = st.selectbox("Usluga", usluga_opcije)
                    idx = usluga_opcije.index(izabrana) if izabrana in usluga_opcije else 0
                    usluga_ime = usluge[idx][0]
                    usluga_cena = usluge[idx][1]
                    usluga_trajanje = usluge[idx][2]

                    col_potvrdi, col_odustani = st.columns(2)
                    with col_potvrdi:
                        potvrdi = st.form_submit_button("✅ Zakaži")
                    with col_odustani:
                        if st.form_submit_button("✖️ Odustani"):
                            del st.session_state['kalendar_klik']
                            st.rerun()

                    if potvrdi:
                        if ime and telefon and ime.strip() and telefon.strip():
                            slotovi_za_uslugu = proveri_slotove_za_uslugu(datum, vreme, usluga_trajanje)
                            if slotovi_za_uslugu is None:
                                st.error("❌ Nema dovoljno slobodnih termina.")
                            else:
                                if rezervisi_slotove(datum, slotovi_za_uslugu, ime, telefon, usluga_ime, usluga_cena, usluga_trajanje):
                                    st.success("✅ Termin uspešno zakazan!")
                                    del st.session_state['kalendar_klik']
                                    st.rerun()
                                else:
                                    st.error("❌ Greška pri rezervaciji.")
                        else:
                            st.warning("⚠️ Popunite ime i telefon.")

    # --- 6. Prezakazivanje ---
    if 'prezakazi_termin' in st.session_state:
        prezakazi = st.session_state['prezakazi_termin']
        with st.expander("🔄 Prezakazivanje", expanded=True):
            st.write(f"**Trenutni termin:** {prezakazi['datum']} {prezakazi['vreme']}")
            novi_datum = st.date_input("Novi datum", value=datetime.strptime(prezakazi['datum'], "%Y-%m-%d").date())
            novo_vreme = st.time_input("Novo vreme", value=datetime.strptime(prezakazi['vreme'], "%H:%M").time(), step=timedelta(minutes=30))
            
            col_potvrdi, col_odustani = st.columns(2)
            with col_potvrdi:
                if st.button("✅ Potvrdi prezakazivanje", use_container_width=True):
                    novi_datum_str = novi_datum.strftime("%Y-%m-%d")
                    novo_vreme_str = novo_vreme.strftime("%H:%M")
                    conn = sqlite3.connect('termini.db')
                    c = conn.cursor()
                    c.execute("SELECT ime FROM rezervacije WHERE datum=? AND vreme=? AND ime IS NOT NULL", (novi_datum_str, novo_vreme_str))
                    if c.fetchone():
                        st.error("❌ Izabrani termin je već zauzet!")
                    else:
                        c.execute("UPDATE rezervacije SET datum=?, vreme=? WHERE id=?", (novi_datum_str, novo_vreme_str, prezakazi['id']))
                        conn.commit()
                        conn.close()
                        st.success("✅ Termin prezakazan!")
                        del st.session_state['prezakazi_termin']
                        st.rerun()
                    conn.close()
            with col_odustani:
                if st.button("✖️ Odustani od prezakazivanja", use_container_width=True):
                    del st.session_state['prezakazi_termin']
                    st.rerun()

# ===================================================================
# GLAVNI DEO
# ===================================================================
init_db()

if 'izabrana_usluga' not in st.session_state: st.session_state['izabrana_usluga'] = None
if 'izabrani_termin' not in st.session_state: st.session_state['izabrani_termin'] = None
if 'booking_success' not in st.session_state: st.session_state['booking_success'] = False
if 'admin_authenticated' not in st.session_state: st.session_state['admin_authenticated'] = False
if 'admin_password' not in st.session_state: st.session_state['admin_password'] = 'admin123'
if 'naplata_id' not in st.session_state: st.session_state['naplata_id'] = None
if 'admin_selected_date' not in st.session_state: st.session_state['admin_selected_date'] = datetime.now().date()
if 'kalendar_klik' not in st.session_state: st.session_state['kalendar_klik'] = None
if 'prezakazi_termin' not in st.session_state: st.session_state['prezakazi_termin'] = None

tab1, tab2 = st.tabs(["📅 Zakazivanje", "🔑 Admin Panel"])

# --- TAB 1 ---
with tab1:
    if 'izabrana_usluga' in st.session_state and not isinstance(st.session_state['izabrana_usluga'], (dict, type(None))):
        st.session_state['izabrana_usluga'] = None

    if st.session_state['booking_success']:
        detalji = st.session_state['booking_details']
        st.balloons()
        st.markdown(f"""
        <div style="background-color: #3a3a3a; padding: 20px; border-radius: 15px; border-left: 6px solid #d4af37; box-shadow: 0 4px 12px rgba(0,0,0,0.5); margin: 20px 0;">
            <h2 style="color: #d4af37; margin:0;">✅ Uspešno ste zakazali!</h2>
            <p><strong>Usluga:</strong> {detalji['usluga']}</p>
            <p><strong>Datum:</strong> {formatiraj_datum(detalji['datum'])}</p>
            <p><strong>Vreme:</strong> {detalji['vreme']}</p>
            <p><strong>Trajanje:</strong> {detalji['trajanje']} min</p>
            <p><strong>Cena:</strong> {detalji['cena']} din</p>
            <p><strong>Klijent:</strong> {detalji['ime']}</p>
            <p style="margin-top:15px; font-size:1.2em; color:#d4af37;">✂️ Vidimo se!</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📅 Zakaži novi termin"):
            st.session_state['booking_success'] = False
            st.session_state['izabrana_usluga'] = None
            st.session_state['izabrani_termin'] = None
            st.rerun()
    else:
        datumi_raw = generisi_datume()
        if datumi_raw:
            osvezi_termine()
            datum = st.selectbox("Datum", datumi_raw, index=0, format_func=formatiraj_datum, key="klijent_datum_select")
            st.info(f"📅 Termini za: {formatiraj_datum(datum)}")
            prikazi_usluge()
            if st.session_state['izabrana_usluga'] is not None:
                prikazi_slotove(datum)
                if st.session_state['izabrani_termin'] is not None:
                    kliknuto_vreme = st.session_state['izabrani_termin']
                    st.write("### 📝 Korak 3: Unesite podatke")
                    with st.form(key="klijent_form"):
                        ime = st.text_input("Ime i prezime *")
                        telefon = st.text_input("Telefon *")
                        usluga = st.session_state['izabrana_usluga']
                        slotovi = proveri_slotove_za_uslugu(datum, kliknuto_vreme, usluga['trajanje'])
                        if slotovi is None:
                            st.error("❌ Nema dovoljno slobodnih termina.")
                        else:
                            st.success(f"✅ Usluga **{usluga['ime']}** traje **{usluga['trajanje']} min** i zauzima **{len(slotovi)} slotova**.")
                            st.write("Zauzeće sledeće slotove:")
                            for s in slotovi: st.markdown(f"- 🔴 {s}")
                            potvrdi = st.form_submit_button("✅ Zakaži")
                            if potvrdi:
                                if ime and telefon and ime.strip() and telefon.strip():
                                    slotovi = proveri_slotove_za_uslugu(datum, kliknuto_vreme, usluga['trajanje'])
                                    if slotovi is None:
                                        st.error("❌ Nažalost, neko je već zauzeo neki od ovih slotova.")
                                        st.session_state['izabrani_termin'] = None; st.rerun()
                                    else:
                                        if rezervisi_slotove(datum, slotovi, ime, telefon, usluga['ime'], usluga['cena'], usluga['trajanje']):
                                            st.session_state['izabrani_termin'] = None
                                            st.session_state['izabrana_usluga'] = None
                                            st.session_state['booking_success'] = True
                                            st.session_state['booking_details'] = {
                                                'usluga': usluga['ime'],
                                                'datum': datum,
                                                'vreme': kliknuto_vreme,
                                                'trajanje': usluga['trajanje'],
                                                'cena': usluga['cena'],
                                                'ime': ime
                                            }
                                            st.rerun()
                                        else: st.error("❌ Greška pri rezervaciji.")
                                else: st.warning("⚠️ Popunite ime i telefon.")
        else: st.error("❌ Nema dostupnih datuma.")

# --- TAB 2 ---
with tab2:
    if not st.session_state['admin_authenticated']:
        st.write("### 🔐 Admin pristup")
        password = st.text_input("Unesite lozinku", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Potvrdi"):
                if password == st.session_state['admin_password']:
                    st.session_state['admin_authenticated'] = True; st.rerun()
                else: st.error("Pogrešna lozinka!")
    else:
        with st.expander("🔑 Promeni lozinku"):
            old = st.text_input("Stara lozinka", type="password", key="old_pass")
            new = st.text_input("Nova lozinka", type="password", key="new_pass")
            confirm = st.text_input("Potvrdi novu lozinku", type="password", key="confirm_pass")
            if st.button("Promeni lozinku"):
                if old == st.session_state['admin_password']:
                    if new and new == confirm:
                        st.session_state['admin_password'] = new
                        st.success("Lozinka uspešno promenjena!")
                    else: st.error("Nove lozinke se ne poklapaju ili su prazne")
                else: st.error("Stara lozinka nije tačna")

        st.write("---")
        st.write("## 📅 Odaberite datum za pregled")
        admin_datumi = generisi_datume()
        admin_datum = st.selectbox("Izaberite datum", admin_datumi, index=0, format_func=formatiraj_datum, key="admin_datum_select")
        st.session_state['admin_selected_date'] = admin_datum
        st.write("---")
        st.write(f"## 📊 Finansijski pregled za {formatiraj_datum(admin_datum)}")
        col1, col2 = st.columns(2)
        with col1: st.metric("📅 Zakazano za izabrani dan", get_unique_clients_count_for_date(admin_datum))
        with col2: st.metric("📆 Zakazano u narednih 7 dana", get_unique_clients_count_next_7_days())
        col3, col4 = st.columns(2)
        with col3:
            st.write("**💰 Mesečni pazar**")
            uk, ke, ka = get_monthly_earnings_breakdown()
            st.write(f"Keš: {ke:,.0f} din"); st.write(f"Kartica: {ka:,.0f} din"); st.write(f"**Ukupno: {uk:,.0f} din**")
        with col4:
            st.write("**📈 Godišnji pazar**")
            uk, ke, ka = get_yearly_earnings_breakdown()
            st.write(f"Keš: {ke:,.0f} din"); st.write(f"Kartica: {ka:,.0f} din"); st.write(f"**Ukupno: {uk:,.0f} din**")
        st.markdown("---")
        uk
