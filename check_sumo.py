#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Control de reservas del viaje a Japon (septiembre 2026), 100% en la nube.
  A) VIGILANCIA (cada 30 min): SUMO (buysumotickets) y NINTENDO MUSEUM (calendario oficial).
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

NINTENDO_URL = "https://museum-tickets.nintendo.com/en/calendar"
NINTENDO_DATE = "2026-09-17"

# Recordatorios: (fecha_apertura_ISO, alto_riesgo, titulo_ASCII, cuerpo_UTF8)
# alto_riesgo -> avisa D-2, D-1 y D ; normal -> avisa D-1 y D.
REMINDERS = [
    ("2026-08-11", False, "Tren Kagayaki",
     "Reserva del shinkansen Kagayaki Tokio-Kanazawa (11 sep): se abre el 11 de agosto (1 mes antes). App SmartEX."),
    ("2026-08-12", True,  "Shibuya Sky",
     "Venta de Shibuya Sky para el 9 sep (~4 semanas antes), franja del atardecer ~18:00. Se agota rapido; reserva en cuanto abra."),
    ("2026-08-13", False, "Shirakawa-go y teamLab",
     "Hoy toca: bus Hokutetsu a Shirakawa-go (13 sep) y entradas de teamLab Borderless (10 sep)."),
    ("2026-08-14", True,  "Kabukiza",
     "Venta general del Kabukiza: 14 de agosto a las 10:00 JST (03:00 Espana). Funcion de la NOCHE del 10 sep. kabukiweb.net. Pon una alarma."),
    ("2026-08-18", False, "Tren Kioto-Kurashiki",
     "Reserva del Nozomi Kioto-Kurashiki (18 sep): se abre el 18 de agosto (Silver Week, recomendado). SmartEX."),
    ("2026-08-21", True,  "TREN CRITICO Hiroshima",
     "Reserva YA el Nozomi Okayama-Hiroshima (21 sep): abre el 21 de agosto a las 10:00 JST (03:00 Espana). Es el tren imprescindible de Silver Week. Pon una alarma."),
    ("2026-08-24", False, "Trenes al vuelo",
     "Opcional: si quieres asiento asegurado, reserva ya los trenes al vuelo del regreso (Thunderbird 14, Hiroshima-Osaka 23, Osaka-Tokio 25). SmartEX."),
    ("2026-09-01", False, "Repaso final",
     "Repaso: tabla de mareas de Miyajima (22 sep), prevision de tifones, cartelera de conciertos y reservar la subida al Umeda Sky (24 sep)."),
    ("2026-09-13", False, "Tren de manana",
     "Manana Thunderbird Kaga-Kioto (14 sep): compra el billete hoy o manana en SmartEX o en estacion."),
    ("2026-09-22", False, "Tren de manana",
     "Manana Hiroshima-Osaka (23 sep): compra el billete en SmartEX o en estacion."),
    ("2026-09-24", False, "Tren de manana",
     "Manana Osaka-Tokio (25 sep): compra el billete en SmartEX o en estacion."),
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


def check_nintendo():
    cls = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(locale="en-US")
            page.set_default_timeout(30000)
            page.goto(NINTENDO_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(f'td[data-date="{NINTENDO_DATE}"]', timeout=30000)
            page.wait_for_timeout(1500)
            cls = page.locator(f'td[data-date="{NINTENDO_DATE}"]').first.get_attribute("class")
            browser.close()
    except Exception as e:
        print(f"AVISO NINTENDO: no se pudo comprobar ({e}); se omite.")
        return False
    cls = (cls or "").lower()
    closed = any(k in cls for k in ["closed", "holiday", "disabled", "no-date", "past", "other-month"])
    soldout = "soldout" in cls or "sold-out" in cls
    if cls and (not soldout) and (not closed):
        print(f"NINTENDO POSIBLE DISPONIBILIDAD ({NINTENDO_DATE}) class={cls}")
        return True
    print(f"nintendo agotado/cerrado ({NINTENDO_DATE}) class={cls}")
    return False


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
        resumen = ("HECHO: alojamientos, teamLab Biovortex, 21st Century, Chichu/Benesse/Lee Ufan, Ghibli. "
                   "EN VIGILANCIA: sumo (26) y Nintendo (17). "
                   "SIN FECHA FIJA: taller Mokuhankan (8 sep), te Camellia (15), cena de despedida (27). ")
        if prox:
            resumen += "Proximas aperturas: " + " | ".join(prox) + "."
        notify(title="Resumen semanal Japon", body=resumen, priority="low", tags="jp")
        print("resumen semanal enviado")


def main():
    run_rem = (
        os.environ.get("TRIGGER", "") == "5 7 * * *"
        or os.environ.get("FORCE_REMINDERS", "").lower() == "true"
    )

    # --- A) VIGILANCIA (siempre) ---
    hits = check_sumo()
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

    if check_nintendo():
        notify(
            title="Nintendo Museum disponible!",
            body=("Ha aparecido disponibilidad para el Museo Nintendo el jueves 17 de septiembre "
                  "(posible cancelacion). Compra YA por orden de llegada en "
                  "museum-tickets.nintendo.com/en/calendar."),
            priority="urgent", tags="video_game,jp",
        )
        print("ALERTA NINTENDO ENVIADA")

    # --- B) y C) RECORDATORIOS + RESUMEN (solo pasada diaria o forzado) ---
    if run_rem:
        run_reminders()
    else:
        print("(pasada de solo vigilancia; sin recordatorios)")


if __name__ == "__main__":
    main()
