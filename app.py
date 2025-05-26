import streamlit as st
import datetime
from dataclasses import dataclass
import mercadopago
import qrcode
import io

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN")
CBU_ALIAS = st.secrets.get("CBU_ALIAS")
# URL pública de tu Streamlit app, necesaria para back_urls
BASE_URL = st.secrets.get("BASE_URL")  # ej: "http://localhost:8501"

# --- MODELO DE DATOS ---
@dataclass
class Workshop:
    title: str
    base_fee: float
    due_day: int
    late_pct_per_day: float

# Datos de ejemplo (reemplazar con DB real)
students = {
    "12345678": "María Pérez",
    "87654321": "Juan Gómez",
}
workshops = {
    "taller1": Workshop(title="Inglés", base_fee=5000.0, due_day=10, late_pct_per_day=1.0),
}
# Estado de facturas en memoria: dni -> "PENDING" | "PAID"
invoice_status = {}

# --- LÓGICA DE CÁLCULO ---
def calculate_fee(base: float, due_day: int, pct_per_day: float, on_date: datetime.date):
    last_day = (on_date.replace(day=1) + datetime.timedelta(days=40)).replace(day=1) - datetime.timedelta(days=1)
    due = on_date.replace(day=min(due_day, last_day.day))
    days_late = max(0, (on_date - due).days)
    surcharge = base * (pct_per_day / 100) * days_late
    total = base + surcharge
    return total, surcharge

# --- MERCADO PAGO ---
mp_sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

def create_mp_preference(dni: str, total: float):
    if not mp_sdk or not BASE_URL:
        return None
    preference_data = {
        "items": [{"title": f"Cuota {dni}", "quantity": 1, "unit_price": total}],
        "external_reference": dni,
        "back_urls": {"success": f"{BASE_URL}?dni={dni}&paid=true"},
        "auto_return": "approved",
        "payer": {"identification": {"type": "DNI", "number": dni}}
    }
    pref = mp_sdk.preference().create(preference_data)
    resp = pref.get("response")
    return resp.get("init_point") if resp else None

# --- STREAMLIT UI ---
st.set_page_config(page_title="Pago de Talleres", layout="centered")
st.title("Pago de Talleres")

# Manejo de retorno después de pago
params = st.query_params
if params.get("paid") and params.get("dni"):
    dni_paid = params.get("dni")[0]
    invoice_status[dni_paid] = "PAID"
    st.success(f"Pago recibido. Gracias, {students.get(dni_paid, dni_paid)}!")

# Entrada de DNI
dni = st.text_input("Ingresá tu DNI o legajo:")
if dni:
    status = invoice_status.get(dni)
    # Si ya pagó
    if status == "PAID":
        st.info("No tienes pagos pendientes. Tu saldo es $0.")
        st.stop()
    # Botón para calcular y cobrar
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
            # Pago MP
            if mp_sdk and BASE_URL:
                link = create_mp_preference(dni, total)
                if link:
                    st.markdown(
                        f'<a href="{link}" target="_blank"><button>Pagar con Mercado Pago</button></a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.error("No se pudo generar el link de pago MP.")
            else:
                st.info("Mercado Pago no configurado o falta BASE_URL en secretos.")
            # Botón pago Homebanking (Intent deep link)
            if CBU_ALIAS:
                # Reemplazá 'bankapp' y 'com.bank.app' por el esquema y paquete de tu banco
                intent_link = (
                    f"intent://pay?cbu={CBU_ALIAS}&amount={total:.2f}"
                    "#Intent;scheme=bankapp;package=com.bank.app;end"
                )
                st.markdown(
                    f'<a href="{intent_link}"><button>Pagar con Homebanking</button></a>',
                    unsafe_allow_html=True
                )
