import os
import streamlit as st
import datetime
import mercadopago
import sqlite3

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS")
BASE_URL        = st.secrets.get("BASE_URL")

# --- OPCIONAL: verificar directorio de trabajo ---
# st.write("Directorio actual:", os.getcwd())

# --- LOGO ---
# Coloca logo.png en la raíz del repo
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
        # concatenar todos los campos en minúsculas (si no son None)
        joined = " ".join(str(student[col]).lower() for col in student.keys() if student[col])
        if term_lower in joined:
            matches.append(student)
    return matches

# --- OBTENER INSCRIPCIÓN ---
def get_enrollment(dni: str):
    if not dni:
        return None
    cur = conn.cursor()
    cur.execute("SELECT * FROM enrollments WHERE student_dni = ?", (dni,))
    return cur.fetchone()

# --- CÁLCULO DE CUOTA ---
def calculate_fee(base: float, due_day: int, pct: float, today: datetime.date):
    last_day = (today.replace(day=1) + datetime.timedelta(days=40)).replace(day=1) - datetime.timedelta(days=1)
    due = today.replace(day=min(due_day, last_day.day))
    days_late = max(0, (today - due).days)
    surcharge = base * (pct/100) * days_late
    total = base + surcharge
    return total, surcharge

# --- MERCADO PAGO SDK ---
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

def create_mp_preference(dni: str, total: float):
    payload = {
        "items": [{"title": f"Cuota {dni}", "quantity":1, "unit_price": total}],
        "external_reference": dni,
        "back_urls": {"success": f"{BASE_URL}?dni={dni}&paid=true"},
        "auto_return": "approved",
        "payer": {"identification": {"type":"DNI","number":dni}}
    }
    pref = mp_sdk.preference().create(payload)
    return pref["response"]["init_point"]

# --- DETECTAR PAGO RETORNADO ---
params = st.query_params
if params.get("paid") and params.get("dni"):
    dni_paid = params["dni"][0]
    st.success(f"¡Pago recibido! Gracias, DNI: {dni_paid}")

# --- INTERFAZ DE BÚSQUEDA ---
search_term = st.text_input("Buscá por nombre, DNI, email o teléfono:")
if search_term:
    matches = find_student(search_term)
    if not matches:
        st.warning("No se encontraron coincidencias.")
    elif len(matches) > 1:
        st.info("Se encontraron varias coincidencias:")
        for m in matches:
            line = m["name"] or ""
            if m["dni"]:
                line += f" – DNI: {m['dni']}"
            if m["email"]:
                line += f" – Email: {m['email']}"
            if m["phone"]:
                line += f" – Tel: {m['phone']}"
            st.write(line)
    else:
        student = matches[0]
        dni = student["dni"] or ""
        display = f"Hola, **{student['name']}**"
        if dni:
            display += f" (DNI: {dni})"
        st.write(display)

        enrollment = get_enrollment(dni)
        if not enrollment:
            st.warning("No se encontró inscripción para este estudiante.")
        else:
            today = datetime.date.today()
            total, surcharge = calculate_fee(
                enrollment["fee"],
                enrollment["due_day"],
                enrollment["late_pct"],
                today
            )
            st.write(f"**Monto base:** $ {enrollment['fee']:.2f}")
            st.write(f"**Recargo:** $ {surcharge:.2f}")
            st.write(f"**Total a pagar:** $ {total:.2f}")

            # Botón Mercado Pago
            if mp_sdk and BASE_URL:
                link_mp = create_mp_preference(dni, total)
                st.markdown(
                    f'<a href="{link_mp}" target="_blank"><button style="margin-right:10px">Pagar con Mercado Pago</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ Mercado Pago no configurado.")

            # Botón Homebanking
            if CBU_ALIAS:
                intent_link = (
                    f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                    "#Intent;scheme=bankapp;package=com.bank.app;end"
                )
                st.markdown(
                    f'<a href="{intent_link}"><button>Pagar con Homebanking</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ CBU_ALIAS no configurado.")

