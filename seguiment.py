#!/usr/bin/env python3
"""
Seguiment de cotxes (i peces) de segona mà — versió d'un sol fitxer
=====================================================================
Tot el projecte en un únic script perquè sigui fàcil de pujar a GitHub
(només calen 4-5 fitxers, cap carpeta que arrossegar).

Ús local:
    python seguiment.py

Cada vegada que s'executa, revisa les cerques actives de config.json,
detecta anuncis nous respecte a l'execució anterior (recordats a
state.json) i genera un informe HTML (ultim_informe.html, i si
s'executa des de GitHub Actions, també docs/index.html per a Pages).
"""
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
INFORME_ULTIM = BASE_DIR / "ultim_informe.html"

CAPÇALERES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ca-ES,ca;q=0.9,es-ES;q=0.8,en;q=0.6",
}


# ─────────────────────────────────────────────────────────────────────────
# SCRAPER: Wallapop (via la seva API de cerca)
# ─────────────────────────────────────────────────────────────────────────
# Com obtenir la URL: fes la cerca a wallapop.com -> F12 -> pestanya Network
# -> filtra per "wallapop" -> recarrega -> busca la petició cap a
# api.wallapop.com/api/v3/.../search... -> botó dret -> Copy link address.
def cerca_wallapop(url, selectors=None):
    resp = requests.get(url, headers={**CAPÇALERES, "Accept": "application/json", "X-DeviceOS": "0"}, timeout=20)
    resp.raise_for_status()
    dades = resp.json()

    items = dades.get("search_objects")
    if items is None:
        try:
            items = dades["data"]["section"]["payload"]["items"]
        except (KeyError, TypeError):
            items = dades.get("data") if isinstance(dades.get("data"), list) else []

    anuncis = []
    for it in items:
        try:
            contingut = it.get("content", it)
            identificador = it.get("id") or contingut.get("id")
            if identificador is None:
                continue
            titol = contingut.get("title") or it.get("title") or "(sense títol)"

            preu_val = contingut.get("price")
            if isinstance(preu_val, dict):
                preu_val = preu_val.get("amount") or preu_val.get("cash", {}).get("amount")
            moneda = contingut.get("currency", "EUR")
            preu = f"{preu_val} {moneda}" if preu_val is not None else "?"

            ubicacio = ""
            loc = contingut.get("location")
            if isinstance(loc, dict):
                ubicacio = loc.get("city", "") or loc.get("postal_code", "")

            slug = contingut.get("web_slug") or it.get("web_slug") or identificador
            anuncis.append({
                "id": str(identificador),
                "titol": titol,
                "preu": preu,
                "detalls": ubicacio,
                "link": f"https://es.wallapop.com/item/{slug}",
            })
        except Exception:
            continue

    if not anuncis and dades:
        print(f"    (avís: cap anunci reconegut a la resposta de Wallapop; claus rebudes: {list(dades.keys())})")

    return anuncis


# ─────────────────────────────────────────────────────────────────────────
# SCRAPER: genèric per a la resta de webs (Coches.net, AutoScout24,
# Autohero, Milanuncios...). Prova selectors CSS (si n'has definit a
# config.json) i, si no, intenta extreure un bloc JSON incrustat a la
# pàgina. Vegeu el README per saber com trobar bons selectors.
# ─────────────────────────────────────────────────────────────────────────
def cerca_generica(url, selectors=None):
    resp = requests.get(url, headers=CAPÇALERES, timeout=25)
    resp.raise_for_status()
    html = resp.text

    if selectors:
        anuncis = _amb_selectors(html, url, selectors)
        if anuncis:
            return anuncis
        print("    (avís: els selectors CSS no han trobat res; es prova l'extracció automàtica)")

    anuncis = _amb_json_incrustat(html, url)
    if anuncis:
        return anuncis

    raise RuntimeError(
        "No s'ha pogut extreure cap anunci d'aquesta pàgina. Pot ser que la web "
        "bloquegi peticions automàtiques, o que calgui definir \"selectors\" a "
        "config.json per a aquesta cerca (vegeu el README)."
    )


def _amb_selectors(html, url_base, sel):
    soup = BeautifulSoup(html, "html.parser")
    anuncis = []
    for c in soup.select(sel["contenidor"]):
        try:
            titol_el = c.select_one(sel["titol"]) if sel.get("titol") else None
            preu_el = c.select_one(sel["preu"]) if sel.get("preu") else None
            link_el = c.select_one(sel.get("link", "a"))
            if not link_el:
                continue
            href = link_el.get(sel.get("link_attr", "href"), "")
            if not href:
                continue
            link = urljoin(sel.get("link_base", url_base), href)
            anuncis.append({
                "id": link,
                "titol": titol_el.get_text(strip=True) if titol_el else "(sense títol)",
                "preu": preu_el.get_text(strip=True) if preu_el else "?",
                "detalls": "",
                "link": link,
            })
        except Exception:
            continue
    return anuncis


def _amb_json_incrustat(html, url_base):
    candidats = (
        re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        + re.findall(r'__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.S)
        + re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    )
    for bloc in candidats:
        try:
            dades = json.loads(bloc)
        except json.JSONDecodeError:
            continue
        trobats = list(_cerca_recursiva(dades))
        if not trobats:
            continue
        anuncis, vist = [], set()
        for item in trobats:
            link = urljoin(url_base, item["url"])
            if link in vist:
                continue
            vist.add(link)
            anuncis.append({"id": link, "titol": item["titol"], "preu": item["preu"], "detalls": "", "link": link})
        if anuncis:
            return anuncis
    return []


def _cerca_recursiva(node, profunditat=0):
    if profunditat > 12:
        return
    if isinstance(node, dict):
        claus = {k.lower(): k for k in node.keys()}
        clau_titol = next((claus[k] for k in claus if k in ("title", "name", "titol")), None)
        clau_preu = next((claus[k] for k in claus if "price" in k or k == "preu"), None)
        clau_link = next((claus[k] for k in claus if k in ("url", "link", "slug", "permalink")), None)
        if clau_titol and clau_preu and clau_link:
            titol, url_val = node.get(clau_titol), node.get(clau_link)
            if isinstance(titol, str) and isinstance(url_val, str) and len(titol) > 2:
                yield {"titol": titol, "preu": _com_a_text(node.get(clau_preu)), "url": url_val}
        for v in node.values():
            yield from _cerca_recursiva(v, profunditat + 1)
    elif isinstance(node, list):
        for v in node:
            yield from _cerca_recursiva(v, profunditat + 1)


def _com_a_text(valor):
    if isinstance(valor, dict):
        import_ = valor.get("amount") or valor.get("value")
        moneda = valor.get("currency", "")
        return f"{import_} {moneda}".strip() if import_ is not None else "?"
    return str(valor) if valor is not None else "?"


SCRAPERS = {"wallapop": cerca_wallapop, "generic": cerca_generica}


# ─────────────────────────────────────────────────────────────────────────
# INFORME HTML
# ─────────────────────────────────────────────────────────────────────────
CSS = """
:root { --blau:#003057; --taronja:#ff6a13; --bg:#f4f6f8; --card:#fff; --text:#1c2733; --muted:#64748b; --nou:#16a34a; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 2rem 1.5rem 4rem; }
h1 { color: var(--blau); margin-bottom: 0.2rem; }
.data { color: var(--muted); margin-top: 0; margin-bottom: 2rem; }
.cerca { background: var(--card); border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.cerca h2 { margin: 0 0 0.3rem; font-size: 1.15rem; color: var(--blau); display: flex; align-items: center; gap: 0.6rem; }
.badge { background: var(--nou); color: white; font-size: 0.75rem; padding: 0.15rem 0.55rem; border-radius: 999px; font-weight: 600; }
.badge.zero { background: #cbd5e1; color: #475569; }
.error { color: #b91c1c; font-size: 0.9rem; }
table { width: 100%; border-collapse: collapse; margin-top: 0.7rem; font-size: 0.92rem; }
th, td { text-align: left; padding: 0.45rem 0.5rem; border-bottom: 1px solid #eef1f4; }
th { color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }
tr.nou td:first-child { border-left: 3px solid var(--nou); padding-left: 0.4rem; }
a.link { color: var(--taronja); text-decoration: none; font-weight: 600; white-space: nowrap; }
a.link:hover { text-decoration: underline; }
details summary { cursor: pointer; color: var(--muted); font-size: 0.85rem; margin-top: 0.6rem; }
"""


def genera_html(resultats, moment):
    total_nous = sum(len(r["nous"]) for r in resultats)
    seccions = "\n".join(_secció(r) for r in resultats)
    return f"""<!DOCTYPE html>
<html lang="ca">
<head><meta charset="UTF-8"><title>Seguiment de cotxes — {moment.strftime('%d/%m/%Y %H:%M')}</title><style>{CSS}</style></head>
<body>
  <h1>🚗 Seguiment d'anuncis</h1>
  <p class="data">Generat el {moment.strftime('%d/%m/%Y a les %H:%M')} — {total_nous} anuncis nous en total</p>
  {seccions}
</body>
</html>"""


def _secció(r):
    n_nous = len(r["nous"])
    badge = f'<span class="badge{"" if n_nous else " zero"}">{n_nous} nou{"s" if n_nous != 1 else ""}</span>'
    cos = f'<p class="error">⚠️ {r["error"]}</p>' if r["error"] else _taula(r["anuncis"], {a["id"] for a in r["nous"]})
    return f'<section class="cerca"><h2>{r["nom"]} {badge}</h2>{cos}</section>'


def _taula(anuncis, ids_nous):
    if not anuncis:
        return '<p style="color:#94a3b8;">Cap anunci trobat en aquesta cerca.</p>'
    noves = [a for a in anuncis if a["id"] in ids_nous]
    resta = [a for a in anuncis if a["id"] not in ids_nous]

    def fila(a):
        classe = "nou" if a["id"] in ids_nous else ""
        return (f'<tr class="{classe}"><td>{a["titol"]}</td><td>{a["preu"]}</td>'
                f'<td>{a.get("detalls", "")}</td>'
                f'<td><a class="link" href="{a["link"]}" target="_blank" rel="noopener">Veure anunci ↗</a></td></tr>')

    capçalera = '<table><thead><tr><th>Títol</th><th>Preu</th><th>Detalls</th><th></th></tr></thead><tbody>'
    cos_noves = "".join(fila(a) for a in noves)
    if resta:
        cos_resta = "".join(fila(a) for a in resta)
        cua = (f'</tbody></table><details><summary>Veure {len(resta)} anuncis ja vistos anteriorment</summary>'
               f'<table><tbody>{cos_resta}</tbody></table></details>')
    else:
        cua = "</tbody></table>"
    return capçalera + cos_noves + cua


# ─────────────────────────────────────────────────────────────────────────
# ORQUESTRACIÓ
# ─────────────────────────────────────────────────────────────────────────
def carrega_json(path, per_defecte):
    if not path.exists():
        return per_defecte
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"⚠️  Error llegint {path.name}: {e}")
        return per_defecte


def desa_json(path, dades):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False, indent=2)


def main():
    config = carrega_json(CONFIG_PATH, {"cerques": []})
    estat = carrega_json(STATE_PATH, {})

    cerques = [c for c in config.get("cerques", []) if c.get("activa", True)]
    if not cerques:
        print("No hi ha cap cerca activa a config.json. Posa \"activa\": true en alguna i torna-ho a provar.")
        sys.exit(1)

    resultats = []
    for cerca in cerques:
        cid, nom, site, url = cerca["id"], cerca.get("nom", cerca["id"]), cerca.get("site"), cerca.get("url")
        print(f"🔍 Cercant: {nom} ({site})...")

        funcio = SCRAPERS.get(site)
        if not funcio:
            msg = f"Tipus de web desconegut: {site!r} (opcions vàlides: {list(SCRAPERS)})"
            print(f"  ⚠️  {msg}")
            resultats.append({"nom": nom, "error": msg, "anuncis": [], "nous": []})
            continue
        try:
            anuncis = funcio(url, cerca.get("selectors"))
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            resultats.append({"nom": nom, "error": str(e), "anuncis": [], "nous": []})
            continue

        ids_previs = set(estat.get(cid, []))
        nous = [a for a in anuncis if a["id"] not in ids_previs]
        estat[cid] = list({a["id"] for a in anuncis} | ids_previs)

        print(f"  ✅ {len(anuncis)} anuncis trobats, {len(nous)} nous")
        resultats.append({"nom": nom, "error": None, "anuncis": anuncis, "nous": nous})

    desa_json(STATE_PATH, estat)

    ara = datetime.now()
    html = genera_html(resultats, ara)
    INFORME_ULTIM.write_text(html, encoding="utf-8")

    if os.environ.get("CI"):
        docs_dir = BASE_DIR / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "index.html").write_text(html, encoding="utf-8")
        print("📄 Informe publicat a docs/index.html")
    else:
        print(f"📄 Informe generat: {INFORME_ULTIM}")
        try:
            webbrowser.open(f"file://{INFORME_ULTIM.resolve()}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
