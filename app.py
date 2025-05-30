import os
import streamlit as st
import datetime
import mercadopago
import sqlite3

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS")
BASE_URL        = st.secrets.get("BASE_URL")

# --- LOGO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres")

# --- CONEXIÓN A BD ---
conn = sqlite3.connect("alma_paid.db", check_same_thread=False)
conn.row_factory = sqlite3.Row

# --- BÚSQUEDA DE ESTUDIANTE ---
def find_student(term: str):
    cur = conn.cursor()
    cur.execute("SELECT * FROM students")
    all_students = cur.fetchall()
    matches = []
    term_lower = term.lower()
    for student in all_students:
        # concatenar todos los campos en minúsculas
        vals = []
        for col in student.keys():
            v = student[col]
            if v is not None:
                vals.append(str(v).lower())
        if term_lower in " ".join(vals):
            matches.append(student)
    return matches

# --- OBTENER INSCRIPCIÓN ---
def get_enrollments(dni: str):
    cur = conn.cursor()
    cur.execute("SELECT * FROM enrollments WHERE student_dni = ?", (dni,))
    return cur.fetchall()  # puede haber más de uno

# --- CÁLCULO DE CUOTA ---
def calculate_fee(base: float, due_day: int, pct: float, today: datetime.date):
    last_day = (today.replace(day=1) + datetime.timedelta(days=40)).replace(day=1) - datetime.timedelta(days=1)
    due = today.replace(day=min(due_day, last_day.day))
    days_late = max(0, (today - due).days)
    surcharge = base * (pct/100) * days_late
    return base + surcharge, surcharge

# --- MERCADO PAGO SDK ---
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

def create_mp_preference(ref: str, total: float):
    payload = {
        "items": [{"title": f"Pago {ref}", "quantity":1, "unit_price": total}],
        "external_reference": ref,
        "back_urls": {"success": f"{BASE_URL}?ref={ref}&paid=true"},
        "auto_return": "approved",
    }
    pref = mp_sdk.preference().create(payload)
    return pref["response"]["init_point"]

# --- PAGO RETORNADO ---
params = st.query_params
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! Gracias.")

# --- UI DE BÚSQUEDA ---
term = st.text_input("Buscá por nombre, DNI, email o teléfono:")
if term:
    matches = find_student(term)
    if not matches:
        st.warning("No se encontraron coincidencias.")
    elif len(matches) > 1:
        st.info("Varias coincidencias:")
        for s in matches:
            line = s["name"]
            if s["dni"]:   line += f" – DNI: {s['dni']}"
            if s["email"]: line += f" – Email: {s['email']}"
            if s["phone"]: line += f" – Tel: {s['phone']}"
            st.write(line)
    else:
        student = matches[0]
        dni = student["dni"]  # siempre pandas-like
        st.write(f"Hola, **{student['name']}**" + (f" (DNI: {dni})" if dni else ""))

        enrols = get_enrollments(dni or "")
        if not enrols:
            st.warning("No tiene inscripciones registradas.")
        else:
            today = datetime.date.today()
            for e in enrols:
                title   = e["workshop"]
                base    = e["fee"]
                due_day = e["due_day"]
                pct     = e["late_pct"]
                total, surcharge = calculate_fee(base, due_day, pct, today)

                st.subheader(f"Taller: {title}")
                st.write(f"Monto base: $ {base:.2f}")
                st.write(f"Recargo (si corresponde): $ {surcharge:.2f}")
                st.write(f"Total a pagar: $ {total:.2f}")

                # Mercado Pago
                if mp_sdk and BASE_URL:
                    link = create_mp_preference(f"{dni}-{title}", total)
                    st.markdown(
                        f'<a href="{link}" target="_blank"><button>Pagar con Mercado Pago</button></a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("⚠️ MP no configurado.")

                # Homebanking
                if CBU_ALIAS:
                    intent = f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}#Intent;scheme=bankapp;package=com.bank.app;end"
                    st.markdown(f'<a href="{intent}"><button>Pagar con Homebanking</button></a>',
                                unsafe_allow_html=True)
                else:
                    st.warning("⚠️ CBU_ALIAS no configurado.")


