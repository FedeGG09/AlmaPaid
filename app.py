import os
import streamlit as st
import datetime
import sqlite3

# --- CONFIGURACIÓN MANUAL PARA DEMO ---
# (Ya no usamos SDK real; devolvemos un link de ejemplo)
CBU_ALIAS = "CASINO.RED.GRITO"
BASE_URL  = "https://tu-app-demo.streamlit.app"

# --- LOGO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres (Demo)")

# --- CONEXIÓN A BD ---
DB_PATH = "alma_paid.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

# --- FUNCIONES BD ---
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

# --- GENERADOR DE LINK DE PAGO DEMO ---
def create_demo_link(ref: str, total: float):
    # Para demo simplemente devolvemos un enlace ficticio que incluye ref y total
    return f"{BASE_URL}/pay?ref={ref}&amount={int(total)}"

# --- DETECTAR PAGO RETORNADO ---
params = st.query_params
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! (Demo)")

# --- INTERFAZ DE BÚSQUEDA Y PAGO ---
term = st.text_input("Buscá por nombre, DNI, email o estado:")
if term:
    term_l = term.lower()
    students = load_all_students()
    matches = []
    for s in students:
        vals = [str(s[col]).lower() for col in ("name","dni","email","status") if s[col]]
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

            # — Botón Pago Demo —
            demo_link = create_demo_link(f"{s['id']}", total)
            st.markdown(
                f'<a href="{demo_link}" target="_blank">'
                '<button style="margin-right:10px">Simular Pago Demo</button>'
                '</a>',
                unsafe_allow_html=True
            )

            # — Botón Homebanking Demo —
            intent = (
                f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                "#Intent;scheme=bankapp;package=com.bank.app;end"
            )
            st.markdown(
                f'<a href="{intent}"><button>Pagar con Homebanking (Demo)</button></a>',
                unsafe_allow_html=True
            )



