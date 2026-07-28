import streamlit as st

from database import inicijalizuj_bazu


# pokretanje baze
inicijalizuj_bazu()


# izgled stranice
st.set_page_config(
    page_title="💈 Berberski salon",
    layout="centered"
)


st.title("💈 Berberski salon - Zakazivanje")

st.success("✅ Baza uspešno povezana")


st.write("""
Dobrodošli u sistem za zakazivanje termina.

Sledeći korak:
- izbor usluge
- izbor datuma
- izbor termina
- podaci klijenta
""")
