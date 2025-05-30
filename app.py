import os
import streamlit as st
import datetime
import mercadopago

from data.repository import SQLiteRepository

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS")
BASE_URL        = st.secrets.get("BASE_URL")

# --- LOGO ---
st.image("logo.png", width=200)
st.title("AlmaPaid – Pago de Talleres")

# --- REPOSITORIO ---
repo = SQLiteRepository()

# --- MERCADO PAGO SDK ---
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

def create_mp_preference(ref: str, total: float):
    payload = {
        "items": [{"title": f"Pago {ref}", "quantity":1, "unit_price": total}],
        "external_reference": ref,
        "back_urls": {"success": f"{BASE_URL}?ref={ref}&paid=true"},
        "auto_return": "approved",
    }
    return mp_sdk.preference().create(payload)["response"]["init_point"]

# --- Pago retornado ---
params = st.query_params
if params.get("paid") and params.get("ref"):
    st.success("¡Pago recibido! Gracias.")

# --- Búsqueda de alumno ---
term = st.text_input("Buscá por nombre, DNI, email o estado:")
if term:
    # cargamos todos los estudiantes y filtramos por coincidencia parcial en cualquier campo
    students = repo.list_students()
    term_l = term.lower()
    matches = [
        s for s in students
        if term_l in s.name.lower()
        or term_l in (s.email or "").lower()
        or term_l in (s.dni or "").lower()
        or term_l in (s.status or "").lower()
    ]

    if not matches:
        st.warning("No se encontraron coincidencias.")
    elif len(matches) > 1:
        st.info("Se encontraron varias coincidencias:")
        for s in matches:
            line = f"{s.name}"
            if s.dni:   line += f" – DNI: {s.dni}"
            if s.email: line += f" – Email: {s.email}"
            if s.status:line += f" – Estado: {s.status}"
            st.write(line)
    else:
        # único match
        s = matches[0]
        st.write(f"Hola, **{s.name}**" + (f" (DNI: {s.dni})" if s.dni else ""))

        # calculamos deuda mes actual
        subtotal, surcharge, total = repo.calculate_due_for_student(s.dni)
        if subtotal == 0 and surcharge == 0 and total == 0:
            st.warning("No tiene cursos o DNI no registrado en la base.")
        else:
            st.write(f"**Subtotal mensual:** $ {subtotal:.2f}")
            st.write(f"**Recargo fijo (si aplica):** $ {surcharge:.2f}")
            st.write(f"**Total a pagar:** $ {total:.2f}")

            # botón Mercado Pago
            if mp_sdk and BASE_URL:
                pref_link = create_mp_preference(s.dni, total)
                st.markdown(
                    f'<a href="{pref_link}" target="_blank"><button>Pagar con Mercado Pago</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ Mercado Pago no configurado en secrets.toml.")

            # botón Homebanking
            if CBU_ALIAS:
                intent_uri = (
                    f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                    "#Intent;scheme=bankapp;package=com.bank.app;end"
                )
                st.markdown(
                    f'<a href="{intent_uri}"><button>Pagar con Homebanking</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ CBU_ALIAS no configurado en secrets.toml.")


