import streamlit as st
import datetime
from dataclasses import dataclass
import mercadopago
import qrcode
import io

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS       = st.secrets.get("CBU_ALIAS")
BASE_URL        = st.secrets.get("BASE_URL")  # ej: "https://tu-app.streamlit.app" o local

# --- MODELO DE DATOS ---
@dataclass
class Workshop:
    title: str
    base_fee: float
    due_day: int
    late_pct_per_day: float

# Datos de ejemplo (luego conectás a tu BD real)
students = {
    "12345678": "María Pérez",
    "87654321": "Juan Gómez",
}
workshops = {
    "taller1": Workshop(title="Inglés", base_fee=5000.0, due_day=10, late_pct_per_day=1.0),
}
invoice_status = {}  # dni -> "PENDING" | "PAID"

# --- LÓGICA DE CÁLCULO ---
def calculate_fee(base: float, due_day: int, pct: float, today: datetime.date):
    last_day = (today.replace(day=1) + datetime.timedelta(days=40)).replace(day=1) - datetime.timedelta(days=1)
    due = today.replace(day=min(due_day, last_day.day))
    days_late = max(0, (today - due).days)
    surcharge = base * (pct/100)*days_late
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

# --- STREAMLIT UI ---
st.set_page_config(page_title="Pago de Talleres", layout="centered")
st.title("Pago de Talleres")

# Detectar pago retornado
params = st.query_params
if params.get("paid") and params.get("dni"):
    dni_paid = params["dni"][0]
    invoice_status[dni_paid] = "PAID"
    st.success(f"¡Pago recibido! Gracias, {students.get(dni_paid,dni_paid)}")

# Formulario DNI
dni = st.text_input("Ingresá tu DNI o legajo:")
if dni:
    if invoice_status.get(dni) == "PAID":
        st.info("No tienes pagos pendientes. Tu saldo es $0.")
        st.stop()

    if st.button("Calcular y Generar Pago"):
        if dni not in students:
            st.error("Alumno no encontrado.")
        else:
            st.write(f"Hola, **{students[dni]}**")
            ws = workshops["taller1"]
            today = datetime.date.today()
            total, surcharge = calculate_fee(ws.base_fee, ws.due_day, ws.late_pct_per_day, today)
            st.write(f"**Monto base:** $ {ws.base_fee:.2f}")
            st.write(f"**Recargo:** $ {surcharge:.2f}")
            st.write(f"**Total a pagar:** $ {total:.2f}")

            # — Botón Mercado Pago —
            if mp_sdk and BASE_URL:
                link_mp = create_mp_preference(dni, total)
                st.markdown(
                    f'<a href="{link_mp}" target="_blank"><button style="margin-right:10px">Pagar con Mercado Pago</button></a>',
                    unsafe_allow_html=True
                )
            else:
                st.warning("⚠️ Mercado Pago no configurado. Revisa MP_ACCESS_TOKEN y BASE_URL en secrets.toml.")

            # — Botón Homebanking (Intent Android) —
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
                st.warning("⚠️ CBU_ALIAS no configurado en secrets.toml.")
