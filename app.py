import os
import streamlit as st
import datetime
import sqlite3
import mercadopago

# --- CARGAR SECRETOS ---
# Debes tener en .streamlit/secrets.toml o en Variables de Entorno:
# MP_ACCESS_TOKEN, CBU_ALIAS, BASE_URL
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS", "")
BASE_URL        = st.secrets.get("BASE_URL", "")

# --- CONFIG DE PÁGINA ---
st.set_page_config(page_title="AlmaPaid – Pago de Talleres", layout="centered")

# --- LOGO Y TÍTULO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres")

# --- CONEXIÓN A SQLITE ---
DB_PATH = "alma_paid.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

# --- FUNCIONES DE BD ---
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
    cutoff = datetime.date(2025, 6, 10)
    surcharge = 2000.0 if today >= cutoff else 0.0
    return surcharge, subtotal + surcharge

# --- INICIALIZAR SDK MP ---
if not MP_ACCESS_TOKEN:
    st.error("⚠️ MP_ACCESS_TOKEN no configurado en secrets.toml o env vars.")
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- CREAR PREFERENCIA Y MOSTRARLA ---
def create_mp_preference(ref: str, total: float):
    payload = {
        "items": [{"title": f"Pago {ref}", "quantity":1, "unit_price": total}],
        "external_reference": ref,
        "back_urls": {"success": f"{BASE_URL}?ref={ref}&paid=true"},
        "auto_return": "approved",
    }
    pref = mp_sdk.preference().create(payload)
    resp = pref.get("response", {}) or {}
    # Sacamos el link correcto
    link = resp.get("init_point") or resp.get("sandbox_init_point")
    # Para demo, mostramos toda la respuesta de la preferencia:
    st.subheader("Detalles de la preferencia MP:")
    st.json(resp)
    return link

# --- DETECTAR PAGO RETORNADO ---
params = st.query_params
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! Gracias.")

# --- INTERFAZ DE BÚSQUEDA Y PAGO ---
term = st.text_input("Buscá por nombre, DNI, email o estado:")
if term:
    term_l = term.lower()
    students = load_all_students()
    matches = [
        s for s in students
        if term_l in " ".join(
            str(s[col]).lower() for col in ("name","dni","email","status") if s[col]
        )
    ]

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
        st.markdown(f"**Hola, {s['name']}**" + (f" (DNI: {s['dni']})" if s["dni"] else ""))

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

            # — Botón Mercado Pago —
            st.markdown("### Pagar con Mercado Pago")
            link_mp = create_mp_preference(f"{s['id']}-{today.isoformat()}", total)
            if link_mp:
                st.markdown(
                    f'<a href="{link_mp}" target="_blank"><button>Pagar con Mercado Pago</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.error("Error generando el link de MP.")

            # — Botón Homebanking —
            st.markdown("### Pagar con Homebanking")
            if not CBU_ALIAS:
                st.warning("⚠️ CBU_ALIAS no configurado en secrets.toml o env vars.")
            else:
                intent = (
                    f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                    "#Intent;scheme=bankapp;package=com.bank.app;end"
                )
                st.markdown(
                    f'<a href="{intent}"><button>Pagar con Homebanking</button></a>',
                    unsafe_allow_html=True
                )



