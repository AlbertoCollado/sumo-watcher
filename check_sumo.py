#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vigia de entradas para el viaje a Japon (septiembre 2026):
  1) SUMO  - buysumotickets.com, Day 14 (sab 26) y Day 15 (dom 27), 2 y 4 personas.
  2) NINTENDO MUSEUM - museum-tickets.nintendo.com, dia objetivo 2026-09-17.
Si aparece disponibilidad, envia un push a ntfy.
Corre en GitHub Actions (cron ~30 min). NTFY_TOPIC viene por variable de entorno.
"""
import os
import requests
from playwright.sync_api import sync_playwright

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

SUMO_URL = "https://buysumotickets.com/shop/tokyo-september"
DAYS = ["Day 14", "Day 15"]
PEOPLE = ["2", "4"]
NEG = "no tournament ticket types open for orders"

NINTENDO_URL = "https://museum-tickets.nintendo.com/en/calendar"
NINTENDO_DATE = "2026-09-17"


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


def main():
    hits = check_sumo()
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
        print("ALERTA SUMO ENVIADA")
    else:
        print("Sin disponibilidad de torneo (26 ni 27).")

    if check_nintendo():
        notify(
            title="Nintendo Museum disponible!",
            body=("Ha aparecido disponibilidad para el Museo Nintendo el jueves 17 de septiembre "
                  "(posible cancelacion). Compra YA por orden de llegada en "
                  "museum-tickets.nintendo.com/en/calendar."),
            priority="urgent",
            tags="video_game,jp",
        )
        print("ALERTA NINTENDO ENVIADA")


if __name__ == "__main__":
    main()
