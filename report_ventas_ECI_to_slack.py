import requests
import os
import calendar
import matplotlib.pyplot as plt
import io
from datetime import datetime, date, timedelta, timezone

# ---- CONFIGURACIÓN ----
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SLACK_TOKEN  = os.environ.get("SLACK_TOKEN")
SLACK_CANAL_VENTASECI  = os.environ.get("SLACK_CANAL_VENTASECI")

# ---- FIN CONFIGURACIÓN ----

hoy          = date.today()
ayer_reporte = hoy - timedelta(days=1)
dia_actual   = ayer_reporte.day
mes_actual   = ayer_reporte.month
anyo_actual  = ayer_reporte.year


sb_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "count=none"
}

def generar_grafico_mensual():
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    datos_2025 = []
    datos_2026 = []
    
    for m in range(1, mes_actual + 1):
        ultimo = calendar.monthrange(2025, m)[1]
        datos_2025.append(suma_total(f"2025-{m:02d}-01", f"2025-{m:02d}-{ultimo:02d}"))
        if m < mes_actual:
            ultimo_26 = calendar.monthrange(2026, m)[1]
            datos_2026.append(suma_total(f"2026-{m:02d}-01", f"2026-{m:02d}-{ultimo_26:02d}"))
        else:
            datos_2026.append(suma_total(f"2026-{m:02d}-01", str(ayer_reporte)))

    x = range(len(datos_2025))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([i - 0.2 for i in x], datos_2025, width=0.4, label="2025", color="#95a5a6")
    ax.bar([i + 0.2 for i in x], datos_2026, width=0.4, label="2026", color="#2ecc71")
    ax.set_xticks(list(x))
    ax.set_xticklabels(meses[:mes_actual])
    ax.set_title("Ventas ECI 2026 vs 2025")
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return buf

def suma_total(desde, hasta):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/suma_ventas",
        headers=sb_headers,
        json={"desde": desde, "hasta": hasta}
    )
    return r.json() or 0


# ── YTD ────────────────────────────────────────────────────
ytd_2026 = suma_total("2026-01-01", f"2026-{mes_actual:02d}-{dia_actual:02d}")
ytd_2025 = suma_total("2025-01-01", f"2025-{mes_actual:02d}-{dia_actual:02d}")
ytd_diff = ytd_2026 - ytd_2025
ytd_pct  = ((ytd_2026 / ytd_2025) - 1) * 100 if ytd_2025 > 0 else 0
ytd_faltan = max(0, ytd_2025 - ytd_2026)

# ── MESES ANTERIORES AL ACTUAL ─────────────────────────────
meses_anteriores_texto = ""
for m in range(1, mes_actual):
    ultimo_26 = calendar.monthrange(2026, m)[1]
    ultimo_25 = calendar.monthrange(2025, m)[1]
    m_2026 = suma_total(f"2026-{m:02d}-01", f"2026-{m:02d}-{ultimo_26:02d}")
    m_2025 = suma_total(f"2025-{m:02d}-01", f"2025-{m:02d}-{ultimo_25:02d}")
    m_pct  = ((m_2026 / m_2025) - 1) * 100 if m_2025 > 0 else 0
    m_emoji = "✅" if m_2026 >= m_2025 else "🔴"
    nombre = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
              "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m-1]
    meses_anteriores_texto += f"\n{m_emoji} *{nombre} 2026 vs {nombre} 2025*\n   2026: {m_2026:,} uds | 2025: {m_2025:,} uds | {m_pct:+.1f}%\n"

# ── MES ACTUAL ─────────────────────────────────────────────
mes_2026       = suma_total(f"2026-{mes_actual:02d}-01", f"2026-{mes_actual:02d}-{dia_actual:02d}")
mes_2025_mismo = suma_total(f"2025-{mes_actual:02d}-01", f"2025-{mes_actual:02d}-{dia_actual:02d}")
ultimo_dia_mes = calendar.monthrange(2025, mes_actual)[1]
mes_2025_total = suma_total(f"2025-{mes_actual:02d}-01", f"2025-{mes_actual:02d}-{ultimo_dia_mes:02d}")
mes_pct    = ((mes_2026 / mes_2025_mismo) - 1) * 100 if mes_2025_mismo > 0 else 0
mes_faltan = max(0, mes_2025_total - mes_2026)

# ── SEMANAS DEL MES ACTUAL ─────────────────────────────────
def get_semanas_mes(anyo, mes):
    primer_dia = date(anyo, mes, 1)
    ultimo_dia = date(anyo, mes, calendar.monthrange(anyo, mes)[1])
    semanas = []
    seen = set()
    d = primer_dia
    while d <= min(ultimo_dia, ayer_reporte):
        sem_num = d.isocalendar()[1]
        if sem_num not in seen:
            seen.add(sem_num)
            # Calcular lunes y domingo de esa semana ISO en el año correcto
            lunes   = date.fromisocalendar(anyo, sem_num, 1)
            domingo = date.fromisocalendar(anyo, sem_num, 7)
            fin     = min(domingo, ayer_reporte)
            semanas.append((sem_num, lunes, fin))
        d += timedelta(days=1)
    return semanas

semanas = get_semanas_mes(anyo_actual, mes_actual)
semanas_texto = ""
for sem_num, inicio, fin in semanas:
    s2026 = suma_total(str(inicio), str(fin))
    lunes_2025   = date.fromisocalendar(2025, sem_num, 1)
    domingo_2025 = date.fromisocalendar(2025, sem_num, 7)
    s2025 = suma_total(str(lunes_2025), str(domingo_2025))
    s_pct = ((s2026 / s2025) - 1) * 100 if s2025 > 0 else 0
    emoji = "✅" if s2026 >= s2025 else "🔴"
    semanas_texto += f"   {emoji} Sem {sem_num}: {s2026:,} uds vs {s2025:,} uds ({s_pct:+.1f}%)\n"

# ── MENSAJE ────────────────────────────────────────────────
nombre_mes = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
              "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][mes_actual-1]
ytd_emoji = "✅" if ytd_2026 >= ytd_2025 else "🔴"

mes_emoji = "✅" if mes_2026 >= mes_2025_mismo else "🔴"

mensaje = f"""📊 *VENTAS ECI | {ayer_reporte.strftime('%d/%m/%Y')}*
━━━━━━━━━━━━━━━━━━━━━━━

{ytd_emoji} *YTD 2026 vs 2025*
   2026: {ytd_2026:,} uds | 2025: {ytd_2025:,} uds | {ytd_pct:+.1f}%
   {"🎯 Faltan " + f"{ytd_faltan:,} uds para igualar 2025" if ytd_faltan > 0 else "🏆 Superado 2025 en " + f"{abs(ytd_diff):,} uds"}

{meses_anteriores_texto}   


{mes_emoji} *{nombre_mes} 2026 (1-{dia_actual}) vs {nombre_mes} 2025 (1-{dia_actual})*
   2026: {mes_2026:,} uds | 2025: {mes_2025_mismo:,} uds | {mes_pct:+.1f}%
   {"🎯 Faltan " + f"{mes_faltan:,} uds para igualar {nombre_mes} 2025 ({mes_2025_total:,} uds)" if mes_faltan > 0 else f"🏆 Mes superado vs 2025"}


📅 *Semanas {nombre_mes} {anyo_actual}*
{semanas_texto}━━━━━━━━━━━━━━━━━━━━━━━"""

print(mensaje)

# ── ENVIAR A SLACK ─────────────────────────────────────────
# Mensaje de texto
r_slack = requests.post(
    "https://slack.com/api/chat.postMessage",
    headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
    json={"channel": SLACK_CANAL, "text": mensaje, "mrkdwn": True}
)
print("✅ Texto enviado" if r_slack.json().get("ok") else f"❌ {r_slack.json().get('error')}")

# Gráfico
# Paso 1: obtener URL de subida
imagen = generar_grafico_mensual()
r_upload = requests.post(
    "https://slack.com/api/files.getUploadURLExternal",
    headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
    data={"filename": "ventas_eci.png", "length": len(imagen.getvalue())}
)
upload_data = r_upload.json()
upload_url  = upload_data["upload_url"]
file_id     = upload_data["file_id"]

# Paso 2: subir el fichero
requests.post(upload_url, files={"file": imagen.getvalue()})

# Paso 3: publicar en el canal
requests.post(
    "https://slack.com/api/files.completeUploadExternal",
    headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
    json={"files": [{"id": file_id}], "channel_id": SLACK_CANAL}
)
print("✅ Gráfico enviado")


