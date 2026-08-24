#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Control de reservas del viaje a Japon (septiembre 2026), 100% en la nube.
VUELOS: ida EY102/EY800 Madrid 7 sep 10:45 -> Narita 8 sep 12:45.
        vuelta EY801 Narita 28 sep 18:00 -> Madrid 29 sep 08:10.
  A) VIGILANCIA (cada 30 min): SUMO (buysumotickets). Nintendo ya conseguido (17 sep, 10:30).
  B) RECORDATORIOS por fecha, con antelacion (solo en la pasada diaria ~09:05 Espana).
  C) RESUMEN semanal (lunes).
Todo se avisa por push a ntfy. NTFY_TOPIC viene por variable de entorno (secreto del repo).
"""
import os
from datetime import datetime, date
import requests
from playwright.sync_api import sync_playwright

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

SUMO_URL = "https://buysumotickets.com/shop/tokyo-september"
DAYS = ["Day 14"]  # solo el sabado 26 (el domingo 27 por la tarde es el Museo Ghibli)
PEOPLE = ["2", "4"]
NEG = "no tournament ticket types open for orders"

# Recordatorios: (fecha_ISO, alto_riesgo, titulo_ASCII, cuerpo_UTF8)
# alto_riesgo -> avisa D-2, D-1 y D ; normal -> avisa D-1 y D.
REMINDERS = [
    ("2026-08-26", True,  "Shibuya Sky",
     "Venta de Shibuya Sky para el 9 sep: abre 14 dias antes, a las 00:00 JST del 26 ago = 17:00 de Espana del martes 25. Franja del atardecer ~17:30-18:00. Se agota en minutos; entra a las 17:00 en punto."),
    ("2026-09-01", False, "Repaso final",
     "Repaso: mareas de Miyajima (22), prevision de tifones y subida al Umeda Sky (24). Sin reservas pendientes salvo Shibuya Sky."),
    ("2026-09-05", True,  "Antes de volar",
     "Visit Japan Web ya esta hecho (los dos). Repaso de vispera: capturas de TODAS las reservas en el movil, PASMO con saldo, eSIM probada, adaptador y medicinas. El 8 aterrizais a las 12:45 y teneis KABUKI a las 16:00."),
    ("2026-09-13", False, "Tren de manana",
     "Manana Thunderbird Kaga-Kioto (14 sep): compra el billete en JR West (e5489) o en la estacion (NO SmartEX)."),
    ("2026-09-20", False, "Tren de la manana siguiente",
     "Esta noche, al volver de Naoshima: mira en la app el horario del tren Uno-Okayama de manana (pasa 1-2 veces por hora). De el depende el Nozomi a Hiroshima de las 10:45."),
    ("2026-09-22", False, "Tren de manana",
     "Manana Hiroshima-Osaka (23 sep): compra el billete en SmartEX o en estacion."),
    ("2026-09-24", False, "Tren de manana",
     "Manana Osaka-Tokio (25 sep): compra el billete en SmartEX o en estacion."),
    ("2026-09-27", False, "Ultimo dia",
     "Manana vuelo EY801 desde Narita T1 a las 18:00: check-out 11:00, maletas en recepcion, y salid de Shinjuku hacia las 13:15-13:30 (N'EX ~80 min) para estar en Narita a las 15:00."),
]


def notify(title, body, priority="high", tags="jp"):
    if not NTFY_TOPIC:
        print("ERROR: falta NTFY_TOPIC")
        return
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": tags},
            timeout=20,
        )
        print(f"ntfy -> {r.status_code} ({title})")
    except Exception as e:
        print(f"ERROR enviando ntfy: {e}")


def check_sumo():
    available = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="en-US")
        page.set_default_timeout(30000)
        try:
            page.goto(SUMO_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"AVISO SUMO: no se pudo cargar ({e}); se omite.")
            browser.close()
            return available

        body0 = page.inner_text("body").lower()
        if "ticket types" not in body0 and "date" not in body0:
            print("AVISO SUMO: estructura inesperada; se omite.")
            browser.close()
            return available

        selects = page.locator("select")
        date_select = None
        for i in range(selects.count()):
            opts = selects.nth(i).locator("option").all_inner_texts()
            if any("September" in o or "Day" in o for o in opts):
                date_select = selects.nth(i)
                break
        if date_select is None:
            print("AVISO SUMO: no se encontro el selector de fecha; se omite.")
            browser.close()
            return available

        num_input = page.locator("input[type=number]")
        for day in DAYS:
            label = None
            for o in date_select.locator("option").all_inner_texts():
                if day in o:
                    label = o
                    break
            if not label:
                continue
            for ppl in PEOPLE:
                try:
                    date_select.select_option(label=label)
                    if num_input.count():
                        num_input.first.fill(ppl)
                        num_input.first.press("Tab")
                    page.wait_for_timeout(3000)
                    txt = page.inner_text("body").lower()
                    if NEG not in txt:
                        available.append((day, ppl))
                        print(f"SUMO POSIBLE DISPONIBILIDAD: {day}, {ppl} pers.")
                    else:
                        print(f"sumo agotado: {day}, {ppl} pers.")
                except Exception as e:
                    print(f"ERROR SUMO {day}/{ppl}: {e}")
        browser.close()
    return available


def run_reminders():
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Madrid")).date()
    except Exception:
        today = datetime.utcnow().date()
    print(f"recordatorios: hoy es {today} (weekday {today.weekday()})")

    for iso, high, title, body in REMINDERS:
        d = date.fromisoformat(iso)
        delta = (d - today).days
        days_set = (2, 1, 0) if high else (1, 0)
        if delta in days_set:
            pre = {2: "[En 2 dias] ", 1: "[Manana] ", 0: "[Hoy] "}[delta]
            notify(title=title, body=pre + body,
                   priority=("urgent" if high else "high"), tags="jp")
            print(f"recordatorio enviado: {title} (D-{delta})")

    if today.weekday() == 0:  # lunes: resumen semanal
        prox = []
        for iso, high, title, body in REMINDERS:
            d = date.fromisoformat(iso)
            if d >= today:
                prox.append(f"{d.strftime('%d/%m')} {title}")
        resumen = ("HECHO: alojamientos, KABUKI (8 sep 16:00), tren Kagayaki (11 sep 9:56), "
                   "bus Shirakawa-go (13 sep, 8:40 y 15:10), los DOS NOZOMI de Silver Week (18 y 21 sep, SmartEX), "
                   "teamLab Biovortex, 21st Century, MUSEO NINTENDO (17, 10:30), "
                   "Chichu/Benesse/Lee Ufan, Minamidera + e-bikes, Ghibli (27, 14:00). "
                   "EN VIGILANCIA: solo el sumo (26). "
                   "PENDIENTE: solo Shibuya Sky (25 ago 17:00). Transporte cerrado y Visit Japan Web hecho. La cena de despedida va sin reserva. "
                   "TECNICO: PASMO creadas y vinculadas al e-ticket; Visit Japan Web hecho por los dos. ")
        if prox:
            resumen += "Proximas fechas: " + " | ".join(prox) + "."
        notify(title="Resumen semanal Japon", body=resumen, priority="low", tags="jp")
        print("resumen semanal enviado")


def main():
    run_rem = (
        os.environ.get("TRIGGER", "") == "5 7 * * *"
        or os.environ.get("FORCE_REMINDERS", "").lower() == "true"
    )

    # --- A) VIGILANCIA (hasta el dia del torneo; luego se apaga sola) ---
    try:
        from zoneinfo import ZoneInfo
        hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    except Exception:
        hoy = datetime.utcnow().date()

    hits = check_sumo() if hoy <= date(2026, 9, 26) else []
    if hoy > date(2026, 9, 26):
        print("Torneo pasado: vigilancia de sumo desactivada.")
    dias = sorted({d for (d, _) in hits})
    if dias:
        notify(
            title="SUMO disponible!",
            body=("Han aparecido entradas de torneo del sumo para el sabado 26. "
                  "Compra YA en buysumotickets.com/shop/tokyo-september o en Ticket Oosumo. "
                  "Ojo: no se pueden cancelar tras comprar."),
            priority="urgent", tags="sports_medal,jp",
        )
        print("ALERTA SUMO ENVIADA")
    else:
        print("Sin disponibilidad de torneo (sabado 26).")

    # --- B) y C) RECORDATORIOS + RESUMEN (solo pasada diaria o forzado) ---
    if run_rem:
        run_reminders()
    else:
        print("(pasada de solo vigilancia; sin recordatorios)")


if __name__ == "__main__":
    main()
