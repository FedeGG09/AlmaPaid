# AlmaPaid

import os
import streamlit as st
import datetime
import sqlite3
import mercadopago

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS")
BASE_URL        = st.secrets.get("BASE_URL")

# --- LOGO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres")

# --- CONEXIÓN A BD ---
DB_PATH = "alma_paid.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

# --- FUNCIONES AUXILIARES ---
def load_all_students():
    """Devuelve lista de sqlite3.Row con campos id, name, email, dni, status."""
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, dni, status FROM students;")
    return cur.fetchall()

def load_courses_for_student(student_id: int):
    """Devuelve lista de tuplas (title, monthly_fee) para un alumno."""
    cur = conn.cursor()
    cur.execute("""
        SELECT c.title, c.monthly_fee
          FROM courses c
          JOIN enrollments e ON e.course_id = c.id
         WHERE e.student_id = ?
    """, (student_id,))
    return cur.fetchall()

def calculate_due(subtotal: float, today: datetime.date):
    """
    Aplica recargo fijo de 2000 a partir del 10 de cada mes.
    (Ajusta fecha de corte si prefieres otro día).
    """
    cutoff = datetime.date(today.year, today.month, 10)
    surcharge = 2000.0 if today >= cutoff else 0.0
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
params = st.experimental_get_query_params()
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! Gracias por tu operación.")

# --- INTERFAZ DE BÚSQUEDA ---
term = st.text_input("Buscá por nombre, DNI, email o estado:")
if term:
    term_l = term.lower()
    students = load_all_students()
    matches = []
    for s in students:
        # Concatenamos todos los campos y buscamos coincidencia parcial
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
        # Cargamos cursos y fees
        courses = load_courses_for_student(s["id"])
        if not courses:
            st.warning("Este alumno no tiene cursos inscriptos.")
        else:
            subtotal = sum(fee for _, fee in courses)
            today = datetime.date.today()
            surcharge, total = calculate_due(subtotal, today)

            # Mostrar detalle de cada curso
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
