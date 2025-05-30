import os
import streamlit as st
import datetime
import sqlite3
import mercadopago
import toml
import streamlit as st

# --- CARGAR SECRETS MANUALMENTE ---
config = toml.load("streamlit/secrets.toml")
MP_ACCESS_TOKEN = config.get("MP_ACCESS_TOKEN", "")
CBU_ALIAS       = config.get("CBU_ALIAS", "")
BASE_URL        = config.get("BASE_URL", "")


# --- LOGO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres")

# --- CONEXIÓN A BD ---
DB_PATH = "alma_paid.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

# --- AUXILIARES BD ---
def load_all_students():
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, dni, status FROM students;")
    return cur.fetchall()

def load_courses_for_student(student_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT c.title, c.monthly_fee
          FROM courses c
          JOIN enrollments e ON e.course_id = c.id
         WHERE e.student_id = ?
    """, (student_id,))
    return cur.fetchall()

# --- CÁLCULO DE RECARGO ---
def calculate_due(subtotal: float, today: datetime.date):
    """
    Aplica un recargo fijo de $2000 sólo si hoy >= 10 de junio de 2025.
    Antes de esa fecha, recargo = 0.
    """
    cutoff = datetime.date(2025, 6, 10)
    if today >= cutoff:
        surcharge = 2000.0
    else:
        surcharge = 0.0
    return surcharge, subtotal + surcharge

# --- MERCADO PAGO SDK ---
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

def create_mp_preference(ref: str, total: float):
    payload = {
        "items": [{"title": f"Pago {ref}", "quantity":1, "unit_price": total}],
        "external_reference": ref,
        "back_urls": {"success": f"{BASE_URL}?ref={ref}&paid=true"},
        "auto_return": "approved",
    }
    resp = mp_sdk.preference().create(payload)
    return resp["response"]["init_point"]

# --- DETECTAR PAGO RETORNADO ---
params = st.query_params
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! Gracias por tu operación.")

# --- INTERFAZ DE BÚSQUEDA Y PAGO ---
term = st.text_input("Buscá por nombre, DNI, email o estado:")
if term:
    term_l = term.lower()
    students = load_all_students()
    matches = []
    for s in students:
        vals = []
        for col in ("name","dni","email","status"):
            v = s[col]
            if v:
                vals.append(str(v).lower())
        if term_l in " ".join(vals):
            matches.append(s)

    if not matches:
        st.warning("No se encontraron alumnos con ese término.")
    elif len(matches) > 1:
        st.info("Se encontraron varias coincidencias:")
        for s in matches:
            line = s["name"]
            if s["dni"]:   line += f" – DNI: {s['dni']}"
            if s["email"]: line += f" – Email: {s['email']}"
            if s["status"]:line += f" – Estado: {s['status']}"
            st.write(line)
    else:
        s = matches[0]
        st.write(f"Hola, **{s['name']}**" + (f" (DNI: {s['dni']})" if s["dni"] else ""))

        courses = load_courses_for_student(s["id"])
        if not courses:
            st.warning("Este alumno no tiene cursos inscriptos.")
        else:
            subtotal = sum(fee for _, fee in courses)
            today = datetime.date.today()
            surcharge, total = calculate_due(subtotal, today)

            st.markdown("**Detalle de cursos:**")
            for title, fee in courses:
                st.write(f"- {title}: $ {fee:.2f}")

            st.write(f"**Subtotal mensual:** $ {subtotal:.2f}")
            st.write(f"**Recargo (si corresponde):** $ {surcharge:.2f}")
            st.write(f"**Total a pagar:** $ {total:.2f}")

            # Botón Mercado Pago
            if mp_sdk and BASE_URL:
                link = create_mp_preference(f"{s['id']}", total)
                st.markdown(
                    f'<a href="{link}" target="_blank"><button style="margin-right:10px">Pagar con Mercado Pago</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ Mercado Pago no configurado en secrets.toml.")

            # Botón Homebanking
            if CBU_ALIAS:
                intent = (
                    f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                    "#Intent;scheme=bankapp;package=com.bank.app;end"
                )
                st.markdown(
                    f'<a href="{intent}"><button>Pagar con Homebanking</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ CBU_ALIAS no configurado en secrets.toml.")



