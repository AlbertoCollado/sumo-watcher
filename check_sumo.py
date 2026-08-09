#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vigia de entradas del Gran Torneo de Sumo de Tokio (septiembre 2026).
Comprueba buysumotickets.com para el sabado 26 (Day 14) y el domingo 27 (Day 15),
con 2 y 4 personas. Si aparece CUALQUIER "tournament ticket type", envia push a ntfy.
Corre en GitHub Actions (cron ~30 min). NTFY_TOPIC viene por variable de entorno.
"""
import os
import requests
from playwright.sync_api import sync_playwright

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
URL = "https://buysumotickets.com/shop/tokyo-september"
DAYS = ["Day 14", "Day 15"]
PEOPLE = ["2", "4"]
NEG = "no tournament ticket types open for orders"


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
        print(f"ntfy -> {r.status_code}")
    except Exception as e:
        print(f"ERROR enviando ntfy: {e}")


def check():
    available = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="en-US")
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"AVISO: no se pudo cargar la pagina ({e}); se omite esta pasada.")
            browser.close()
            return available

        body0 = page.inner_text("body").lower()
        if "ticket types" not in body0 and "date" not in body0:
            print("AVISO: estructura de pagina inesperada; se omite esta pasada.")
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
            print("AVISO: no se encontro el selector de fecha; se omite.")
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
                print(f"AVISO: no hay opcion para {day}")
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
                        print(f"POSIBLE DISPONIBILIDAD: {day}, {ppl} pers.")
                    else:
                        print(f"agotado: {day}, {ppl} pers.")
                except Exception as e:
                    print(f"ERROR comprobando {day}/{ppl}: {e}")
        browser.close()
    return available


def main():
    hits = check()
    dias = sorted({d for (d, _) in hits})
    if dias:
        cuales = " y ".join(
            {"Day 14": "sabado 26", "Day 15": "domingo 27"}.get(d, d) for d in dias
        )
        notify(
            title="SUMO disponible!",
            body=(f"Han aparecido entradas de torneo del sumo para {cuales}. "
                  f"Compra YA en buysumotickets.com/shop/tokyo-september o en Ticket Oosumo. "
                  f"Ojo: no se pueden cancelar tras comprar."),
            priority="urgent",
            tags="sports_medal,jp",
        )
        print("ALERTA ENVIADA")
    else:
        print("Sin disponibilidad de torneo (26 ni 27).")


if __name__ == "__main__":
    main()
