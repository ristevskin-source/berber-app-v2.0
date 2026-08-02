import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- СТИЛИЗАЦИЈА ---
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

# --- БАЗА ---
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

# --- СЛОТОВИ ---
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

# --- ПОМОЋНЕ ---
def formatiraj_datum(datum):
    return datum.strftime("%d.%m.%Y.")

def generisi_datume():
    danas = datetime.now().date()
    return [danas + timedelta(days=i) for i in range(7)]

def osvezi_termine():
    for datum in generisi_datume():
        generisi_slotove_za_dan(datum)

# --- РЕЗЕРВАЦИЈЕ ---
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

# --- МЕТРИКЕ ---
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

# --- КЛИЈЕНТСКИ ДЕО ---
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

def admin_rucno_zakazi():
    st.write("### ➕ Ručno zakazivanje")
    with st.form(key="admin_zakazi_form"):
        ime = st.text_input("Ime i prezime *"); telefon = st.text_input("Telefon *")
        datum = st.date_input("Odaberi datum", value=datetime.now().date(), min_value=datetime.now().date())
        conn = sqlite3.connect('termini.db'); c = conn.cursor()
        c.execute("SELECT usluga, cena, trajanje FROM cenovnik ORDER BY trajanje ASC")
        usluge = c.fetchall(); conn.close()
        usluga_opcije = [f"{u[0]} ({u[2]} min, {u[1]} din)" for u in usluge]
        izabrana = st.selectbox("Usluga", usluga_opcije)
        idx = usluga_opcije.index(izabrana) if izabrana in usluga_opcije else 0
        usluga_ime = usluge[idx][0]; usluga_cena = usluge[idx][1]; usluga_trajanje = usluge[idx][2]
        conn = sqlite3.connect('termini.db'); c = conn.cursor()
        c.execute("SELECT vreme, ime FROM rezervacije WHERE datum=? AND ime IS NULL ORDER BY vreme ASC", (datum,))
        slobodni_slotovi = c.fetchall(); conn.close()
        if not slobodni_slotovi: st.warning("Nema slobodnih termina."); return
        vreme_opcije = [v[0] for v in slobodni_slotovi]
        izabrano_vreme = st.selectbox("Termin", vreme_opcije)
        potvrdi = st.form_submit_button("✅ Zakaži")
        if potvrdi:
            if ime and telefon and ime.strip() and telefon.strip():
                slotovi = proveri_slotove_za_uslugu(datum, izabrano_vreme, usluga_trajanje)
                if slotovi is None: st.error("❌ Nema dovoljno slobodnih termina.")
                else:
                    if rezervisi_slotove(datum, slotovi, ime, telefon, usluga_ime, usluga_cena, usluga_trajanje):
                        st.success(f"✅ Uspešno zakazano!"); st.rerun()
                    else: st.error("❌ Greška pri rezervaciji.")
            else: st.warning("⚠️ Popunite ime i telefon.")

# ============================================================
# КАЛЕНДАР - ФИЛТЕР У PYTHON-У (БЕЗБЕДНА ВЕРЗИЈА)
# ============================================================
def prikaz_nedeljnog_kalendara():
    st.subheader("📅 Nedeljni pregled (30 min slotovi)")

    # --- 1. Datumi ---
    danas = datetime.now().date()
    pocetak_nedelje = danas - timedelta(days=danas.weekday())
    datumi = [pocetak_nedelje + timedelta(days=i) for i in range(7)]

    # --- 2. Zauzeti termini (BEZ filtera u SQL, filtriramo u Python-u) ---
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

    # Filtriraj naplaćene termine (status != 'naplacen')
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

    # --- 4. Usluge za dropdown ---
    conn = sqlite3.connect('termini.db')
    c = conn.cursor()
    c.execute("SELECT usluga, cena, trajanje FROM cenovnik ORDER BY trajanje ASC")
    usluge = c.fetchall()
    conn.close()

    usluge_opcije = []
    for u in usluge:
        usluge_opcije.append(f"{u[0]}||{u[1]}||{u[2]}")

    # --- 5. HTML + JavaScript (RADNA VERZIJA) ---
    dani_oznake = [d.strftime("%a %d.") for d in datumi]
    dani_vrednosti = [d.strftime("%Y-%m-%d") for d in datumi]

    js_popup = f"""
    <script>
    function otvoriPopup(tip, datum, vreme, ime, telefon, usluga, cena, id) {{
        var overlay = document.createElement('div');
        overlay.id = 'popup-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            animation: fadeIn 0.3s;
        `;
        
        var popup = document.createElement('div');
        popup.style.cssText = `
            background: #2b2b2b;
            padding: 25px 30px;
            border-radius: 15px;
            border: 2px solid #d4af37;
            max-width: 420px;
            width: 92%;
            color: white;
            font-family: sans-serif;
            box-shadow: 0 10px 40px rgba(0,0,0,0.8);
            animation: slideUp 0.3s;
            max-height: 90vh;
            overflow-y: auto;
        `;
        
        var sadrzaj = '';
        
        if (tip === 'zauzet') {{
            sadrzaj = `
                <h3 style="color: #d4af37; margin-top: 0;">👤 Detalji klijenta</h3>
                <hr style="border-color: #444;">
                <p><strong>Ime:</strong> ${{ime}}</p>
                <p><strong>Telefon:</strong> ${{telefon}}</p>
                <p><strong>Usluga:</strong> ${{usluga}}</p>
                <p><strong>Cena:</strong> ${{cena}} din</p>
                <p><strong>Datum:</strong> ${{datum}}  <strong>Vreme:</strong> ${{vreme}}</p>
                <hr style="border-color: #444;">
                <div style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
                    <button onclick="zatvoriPopup()" style="
                        flex: 1;
                        padding: 10px;
                        background: #c62828;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 16px;
                        min-width: 80px;
                    ">✖️ Zatvori</button>
                    <button onclick="window.location.href='?akcija=obrisi&id=${{id}}'" style="
                        flex: 1;
                        padding: 10px;
                        background: #e65100;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 16px;
                        min-width: 80px;
                    ">🗑️ Obriši</button>
                    <button onclick="window.location.href='?akcija=naplati&id=${{id}}'" style="
                        flex: 1;
                        padding: 10px;
                        background: #2e7d32;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 16px;
                        min-width: 80px;
                    ">💰 Naplati</button>
                </div>
            `;
        }} else {{
            sadrzaj = `
                <h3 style="color: #d4af37; margin-top: 0;">📝 Novi termin</h3>
                <hr style="border-color: #444;">
                <p><strong>Datum:</strong> ${{datum}}  <strong>Vreme:</strong> ${{vreme}}</p>
                <form id="formaNoviTermin" onsubmit="return false;">
                    <div style="margin-bottom: 12px;">
                        <label style="display:block; margin-bottom:4px; color:#aaa;">Ime i prezime *</label>
                        <input type="text" id="imeInput" required style="
                            width: 100%;
                            padding: 10px;
                            border-radius: 8px;
                            border: 1px solid #444;
                            background: #1e1e1e;
                            color: white;
                            font-size: 16px;
                            box-sizing: border-box;
                        ">
                    </div>
                    <div style="margin-bottom: 12px;">
                        <label style="display:block; margin-bottom:4px; color:#aaa;">Telefon *</label>
                        <input type="text" id="telefonInput" required style="
                            width: 100%;
                            padding: 10px;
                            border-radius: 8px;
                            border: 1px solid #444;
                            background: #1e1e1e;
                            color: white;
                            font-size: 16px;
                            box-sizing: border-box;
                        ">
                    </div>
                    <div style="margin-bottom: 12px;">
                        <label style="display:block; margin-bottom:4px; color:#aaa;">Usluga</label>
                        <select id="uslugaSelect" style="
                            width: 100%;
                            padding: 10px;
                            border-radius: 8px;
                            border: 1px solid #444;
                            background: #1e1e1e;
                            color: white;
                            font-size: 16px;
                            box-sizing: border-box;
                        ">
    """
    for u in usluge_opcije:
        dijelovi = u.split('||')
        ime_usl = dijelovi[0]
        cena_usl = dijelovi[1]
        trajanje_usl = dijelovi[2]
        js_popup += f"<option value='{ime_usl}||{cena_usl}||{trajanje_usl}'>{ime_usl} ({trajanje_usl} min, {cena_usl} din)</option>"
    
    js_popup += f"""
                        </select>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
                        <button type="button" onclick="zatvoriPopup()" style="
                            flex: 1;
                            padding: 10px;
                            background: #666;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 16px;
                            min-width: 80px;
                        ">✖️ Odustani</button>
                        <button type="button" onclick="zakaziTermin('${{datum}}','${{vreme}}')" style="
                            flex: 1;
                            padding: 10px;
                            background: #d4af37;
                            color: black;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 16px;
                            min-width: 80px;
                            font-weight: bold;
                        ">✅ Zakaži</button>
                    </div>
                </form>
            `;
        }}
        
        popup.innerHTML = sadrzaj;
        overlay.appendChild(popup);
        document.body.appendChild(overlay);
        
        var style = document.createElement('style');
        style.textContent = `
            @keyframes fadeIn {{
                from {{ opacity: 0; }}
                to {{ opacity: 1; }}
            }}
            @keyframes slideUp {{
                from {{ transform: translateY(30px); opacity: 0; }}
                to {{ transform: translateY(0); opacity: 1; }}
            }}
        `;
        document.head.appendChild(style);
    }}
    
    function zakaziTermin(datum, vreme) {{
        var ime = document.getElementById('imeInput').value;
        var telefon = document.getElementById('telefonInput').value;
        var uslugaSelect = document.getElementById('uslugaSelect');
        var uslugaValue = uslugaSelect.value;
        
        if (!ime || !telefon) {{
            alert('Molimo popunite ime i telefon.');
            return;
        }}
        
        var dijelovi = uslugaValue.split('||');
        var uslugaIme = dijelovi[0];
        var uslugaCena = dijelovi[1];
        var uslugaTrajanje = dijelovi[2];
        
        window.location.href = `?akcija=zakazi&datum=${{datum}}&vreme=${{vreme}}&ime=${{encodeURIComponent(ime)}}&telefon=${{encodeURIComponent(telefon)}}&usluga=${{encodeURIComponent(uslugaIme)}}&cena=${{uslugaCena}}&trajanje=${{uslugaTrajanje}}`;
    }}
    
    function zatvoriPopup() {{
        var overlay = document.getElementById('popup-overlay');
        if (overlay) {{
            overlay.remove();
        }}
    }}
    </script>
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        .kalendar-wrapper {{
            overflow-x: auto;
            overflow-y: auto;
            max-height: 80vh;
            -webkit-overflow-scrolling: touch;
            margin: 10px 0;
            border: 1px solid #444;
            border-radius: 8px;
            background-color: #1e1e1e;
            padding: 4px;
        }}
        .kalendar-tabela {{
            border-collapse: collapse;
            width: 100%;
            min-width: 650px;
            font-size: 13px;
            color: white;
            table-layout: fixed;
        }}
        .kalendar-tabela th, .kalendar-tabela td {{
            padding: 6px 4px;
            text-align: center;
            border-bottom: 1px solid #333;
            border-right: 1px solid #333;
            vertical-align: middle;
        }}
        .kalendar-tabela th {{
            background-color: #2b2b2b;
            color: #d4af37;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
            font-size: 12px;
        }}
        .vreme-kolona {{
            background-color: #2b2b2b;
            font-weight: bold;
            color: #aaa;
            position: sticky;
            left: 0;
            z-index: 5;
            width: 60px;
            min-width: 60px;
            max-width: 60px;
            white-space: nowrap;
            font-size: 13px;
        }}
        .dan-kolona {{
            width: 80px;
            min-width: 80px;
            max-width: 80px;
        }}
        .slot-link {{
            display: inline-block;
            width: 44px;
            height: 44px;
            border-radius: 6px;
            text-decoration: none;
            cursor: pointer;
            font-size: 0px;
            padding: 0;
            margin: 0 auto;
            border: none;
            transition: transform 0.1s;
        }}
        .slot-link:active {{ transform: scale(0.92); }}
        .slot-slobodan {{ background-color: #2e7d32; }}
        .slot-slobodan:hover {{ background-color: #43a047; }}
        .slot-zauzet {{ background-color: #c62828; }}
        .slot-zauzet:hover {{ background-color: #e53935; }}
        .kalendar-wrapper::-webkit-scrollbar {{
            height: 6px; width: 6px;
        }}
        .kalendar-wrapper::-webkit-scrollbar-track {{ background: #2b2b2b; }}
        .kalendar-wrapper::-webkit-scrollbar-thumb {{ background: #d4af37; border-radius: 3px; }}
        @media (max-width: 600px) {{
            .vreme-kolona {{ width: 50px; min-width: 50px; max-width: 50px; font-size: 11px; }}
            .dan-kolona {{ width: 70px; min-width: 70px; max-width: 70px; }}
            .slot-link {{ width: 38px; height: 38px; }}
            .kalendar-tabela {{ min-width: 550px; font-size: 11px; }}
        }}
    </style>
    {js_popup}
    </head>
    <body>
    <div class="kalendar-wrapper">
    <table class="kalendar-tabela">
        <thead><tr><th class="vreme-kolona">Vreme</th>
    """
    for oznaka in dani_oznake:
        html += f"<th class='dan-kolona'>{oznaka}</th>"
    html += "</tr></thead><tbody>"

    for slot in slotovi:
        html += f"<tr><td class='vreme-kolona'>{slot}</td>"
        for i, datum in enumerate(dani_vrednosti):
            if (datum, slot) in podaci_termina:
                ime, telefon, usluga, cena, id_termin = podaci_termina[(datum, slot)]
                ime_esc = ime.replace("'", "\\'")
                telefon_esc = telefon.replace("'", "\\'")
                usluga_esc = usluga.replace("'", "\\'")
                html += f"""
                    <td class='dan-kolona'>
                        <button class='slot-link slot-zauzet' 
                                onclick="otvoriPopup('zauzet','{datum}','{slot}','{ime_esc}','{telefon_esc}','{usluga_esc}','{cena}','{id_termin}')">
                        </button>
                    </td>
                """
            else:
                html += f"""
                    <td class='dan-kolona'>
                        <button class='slot-link slot-slobodan' 
                                onclick="otvoriPopup('slobodan','{datum}','{slot}','','','','','')">
                        </button>
                    </td>
                """
        html += "</tr>"
    html += """
        </tbody>
    </table>
    </div>
    </body>
    </html>
    """

    components.html(html, height=600, scrolling=False)

    # --- 6. Obrada akcija ---
    query_params = st.query_params

    if query_params.get("akcija") == "zakazi":
        datum = query_params.get("datum")
        vreme = query_params.get("vreme")
        ime = query_params.get("ime")
        telefon = query_params.get("telefon")
        usluga = query_params.get("usluga")
        cena = query_params.get("cena")
        trajanje = query_params.get("trajanje")
        if datum and vreme and ime and telefon and usluga and cena and trajanje:
            trajanje_int = int(trajanje)
            cena_int = int(cena)
            slotovi_za_uslugu = proveri_slotove_za_uslugu(datum, vreme, trajanje_int)
            if slotovi_za_uslugu is None:
                st.error("❌ Nema dovoljno slobodnih termina.")
            else:
                if rezervisi_slotove(datum, slotovi_za_uslugu, ime, telefon, usluga, cena_int, trajanje_int):
                    st.success("✅ Termin uspešno zakazan!")
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("❌ Greška pri rezervaciji.")
        st.query_params.clear()

    if query_params.get("akcija") == "obrisi":
        termin_id = query_params.get("id")
        if termin_id:
            conn = sqlite3.connect('termini.db')
            c = conn.cursor()
            c.execute("DELETE FROM rezervacije WHERE id=?", (termin_id,))
            conn.commit()
            conn.close()
            st.success("🗑️ Termin obrisan!")
            st.query_params.clear()
            st.rerun()

    if query_params.get("akcija") == "naplati":
        termin_id = query_params.get("id")
        if termin_id:
            conn = sqlite3.connect('termini.db')
            c = conn.cursor()
            c.execute("UPDATE rezervacije SET status='naplacen', payment_method='Keš' WHERE id=?", (termin_id,))
            conn.commit()
            conn.close()
            st.success("💰 Termin naplaćen!")
            st.query_params.clear()
            st.rerun()

# ===================================================================
# ГЛАВНИ ДЕО
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

        admin_rucno_zakazi()
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
        ukupno, kes, kartica = get_earnings_breakdown_for_date(admin_datum)
        st.markdown(f"""
        <div style="background-color: #1e1e1e; padding: 20px; border-radius: 10px; border: 2px solid #d4af37; text-align: center;">
            <h3 style="color: #d4af37;">💵 Pazar za {formatiraj_datum(admin_datum)} (do sada)</h3>
            <div style="display: flex; justify-content: space-around; flex-wrap: wrap; margin-top: 10px;">
                <div><span style="color: #aaa;">Keš:</span> <span style="color:white; font-weight:bold;">{kes:,.0f} din</span></div>
                <div><span style="color: #aaa;">Kartica:</span> <span style="color:white; font-weight:bold;">{kartica:,.0f} din</span></div>
                <div><span style="color: #d4af37;">Ukupno:</span> <span style="color:#d4af37; font-size:1.4em; font-weight:bold;">{ukupno:,.0f} din</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.write("---")
        st.write(f"## 📋 Termini za {formatiraj_datum(admin_datum)}")
        conn = sqlite3.connect('termini.db')
        c = conn.cursor()
        c.execute("""SELECT id, vreme, ime, telefon, usluga, cena, status, payment_method
            FROM rezervacije WHERE datum=? AND ime IS NOT NULL ORDER BY vreme ASC""", (admin_datum,))
        rows = c.fetchall()
        conn.close()
        # Filtriraj naplaćene termine
        rows = [row for row in rows if row[6] != 'naplacen']
        if rows:
            grupe = {}
            for id, vreme, ime, telefon, usluga, cena, status, payment_method in rows:
                key = (ime, telefon, usluga)
                if key not in grupe:
                    grupe[key] = {'vremena': [], 'ids': [], 'status': status, 'payment_method': payment_method, 'cena': cena}
                grupe[key]['vremena'].append(vreme)
                grupe[key]['ids'].append(id)
                if grupe[key]['cena'] == 0 and cena > 0:
                    grupe[key]['cena'] = cena
                if status == 'naplacen':
                    grupe[key]['status'] = 'naplacen'
                    grupe[key]['payment_method'] = payment_method
            for (ime, telefon, usluga), data in grupe.items():
                vremena = sorted(data['vremena'])
                ids = data['ids']
                status = data['status']
                payment_method = data['payment_method']
                cena = data['cena']
                vreme_prikaz = f"{vremena[0]} – {vremena[-1]}" if len(vremena) > 1 else vremena[0]
                with st.container():
                    cols = st.columns([1.2, 1.5, 1.2, 2, 1.2, 1.5])
                    with cols[0]:
                        st.write(vreme_prikaz)
                    with cols[1]:
                        st.write(ime)
                    with cols[2]:
                        st.write(telefon)
                    with cols[3]:
                        st.write(f"{usluga} ({cena} din)")
                    with cols[4]:
                        if status == 'zakazan':
                            if st.button("❌ Otkaži", key=f"otkazi_grupa_{ids[0]}"):
                                for id in ids:
                                    otkazi_termin(id)
                                st.rerun()
                            if st.button("💰 Naplati", key=f"naplati_grupa_{ids[0]}"):
                                st.session_state['naplata_id'] = ids
                                st.rerun()
                        elif status == 'naplacen':
                            st.success(f"✅ Naplaćeno ({payment_method})")
                        elif status == 'otkazan':
                            st.warning("❌ Otkazano")
                    with cols[5]:
                        if status == 'zakazan' and st.session_state.get('naplata_id') == ids:
                            payment_choice = st.radio("Način plaćanja", ["Keš", "Kartica"], key=f"payment_grupa_{ids[0]}", label_visibility="collapsed")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("✅ Potvrdi", key=f"potvrdi_grupa_{ids[0]}"):
                                    if moze_naplata(admin_datum, vremena):
                                        for id in ids:
                                            naplati_termin(id, payment_choice)
                                        st.session_state['naplata_id'] = None
                                        st.rerun()
                                    else:
                                        st.warning("⏳ Termin još nije završen.")
                            with col_b:
                                if st.button("❌ Odustani", key=f"odustani_grupa_{ids[0]}"):
                                    st.session_state['naplata_id'] = None
                                    st.rerun()
                    st.markdown("---")
        else:
            st.info(f"Nema zakazanih klijenata za {formatiraj_datum(admin_datum)}.")

        # ---- КАЛЕНДАР ----
        st.write("---")
        prikaz_nedeljnog_kalendara()
