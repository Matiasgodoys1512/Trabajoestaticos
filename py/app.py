"""Aplicación PyScript: estado, eventos del navegador, persistencia e importación/exportación."""
import asyncio
import base64
import copy
import json
import traceback
from datetime import date

import pandas as pd
from pyodide.ffi import create_proxy, to_js
from pyodide.http import pyfetch
from pyscript import document, window

import ui

CLAVE = "giee_proyecto_v1"
E = {"data": None, "eq": None, "cml": None, "tab": "panel", "filtros": {}, "editando": None}


# ------------------------------------------------------------------ utilidades
def toast(msg, ms=3000):
    t = document.getElementById("toast")
    t.innerText = msg
    t.hidden = False
    window.setTimeout(create_proxy(lambda: setattr(t, "hidden", True)), ms)


def eq_actual():
    return next((e for e in E["data"]["equipos"] if e["id"] == E["eq"]), None)


def leer_form(fid):
    form = document.getElementById(fid)
    out = {}
    for i in range(form.elements.length):
        el = form.elements.item(i)
        if el.name:
            out[el.name] = el.value
    return out


def num(x, defecto=None):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return defecto


def descargar(texto, nombre, mime):
    blob = window.Blob.new(to_js([texto]), to_js({"type": mime}, dict_converter=window.Object.fromEntries))
    url = window.URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href = url
    a.download = nombre
    a.click()
    window.URL.revokeObjectURL(url)


async def leer_archivo(input_el, como_dataurl=False):
    archivo = input_el.files.item(0)
    if not archivo:
        return None, None
    buf = await archivo.arrayBuffer()
    datos = buf.to_py().tobytes()
    if como_dataurl:
        return archivo.name, f"data:{archivo.type};base64,{base64.b64encode(datos).decode()}"
    return archivo.name, datos.decode("utf-8")


def guardar_local(aviso=False):
    try:
        window.localStorage.setItem(CLAVE, json.dumps(E["data"], ensure_ascii=False))
        if aviso:
            toast("Proyecto guardado en el navegador (localStorage).")
    except Exception:
        toast("No se pudo guardar en el navegador (¿imágenes muy pesadas?). Usa Exportar proyecto.", 5000)


async def cargar_demo():
    r = await pyfetch("data/demo.json")
    E["data"] = json.loads(await r.string())
    E["eq"] = E["data"]["equipos"][0]["id"]
    E["cml"] = None


# ------------------------------------------------------------------ render
def render():
    try:
        data = E["data"]
        res = ui.evaluar_todo(data)
        if E["eq"] and not eq_actual():
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
        document.getElementById("sidebar").innerHTML = ui.sidebar(data, res, E["eq"], E["filtros"])
        for b in document.querySelectorAll("#tabs button"):
            b.classList.toggle("activo", b.dataset.tab == E["tab"])
        eq = eq_actual()
        t = E["tab"]
        if E["editando"] is not None:
            html = ui.form_equipo(None if E["editando"] == "nuevo" else eq)
        elif t == "panel":
            html = ui.panel(data, res, E["filtros"])
        elif t == "equipo":
            html = ui.vista_equipo(data, res, eq, E["cml"]) if eq else "<p>No hay equipos.</p>"
        elif t == "diseno":
            html = ui.vista_diseno(eq, res[eq["id"]]) if eq else "<p>No hay equipos.</p>"
        elif t == "rbi":
            html = ui.vista_rbi(data, res)
        elif t == "validacion":
            html = ui.vista_validacion()
        else:
            html = ui.vista_acerca()
        document.getElementById("contenido").innerHTML = html
    except Exception as e:
        document.getElementById("contenido").innerHTML = (
            f'<div class="error"><b>Error al mostrar la vista:</b> {ui.esc(e)}<pre>{ui.esc(traceback.format_exc())}</pre></div>')


def cambio():
    guardar_local()
    render()


# ------------------------------------------------------------------ acciones
def accion_click(el):
    act = el.dataset.act
    ds = el.dataset
    eq = eq_actual()

    if act == "tab":
        E["tab"], E["editando"] = ds.tab, None
    elif act == "sel_eq":
        E["eq"], E["editando"] = ds.id, None
        E["cml"] = ds.cml if ds.cml else None
        if E["tab"] in ("panel", "validacion", "acerca"):
            E["tab"] = "equipo"
    elif act == "sel_cml":
        E["cml"] = ds.id
    elif act == "guardar":
        guardar_local(True)
        return
    elif act == "exportar":
        asyncio.ensure_future(exportar())
        return
    elif act == "exportar_csv":
        filas = ui.filas_panel(E["data"], ui.evaluar_todo(E["data"]), E["filtros"])
        df = pd.DataFrame(filas).drop(columns=["_eq", "_cml"])
        descargar(df.to_csv(index=False, sep=";", decimal=","), f"resumen_cml_{date.today()}.csv", "text/csv")
        return
    elif act == "restablecer":
        if window.confirm("¿Restablecer el caso demostrativo? Se perderán los cambios no exportados."):
            asyncio.ensure_future(restablecer())
        return
    elif act == "add_med":
        d = leer_form("form_med")
        t = num(d["espesor"])
        if not d["fecha"] or t is None or t <= 0:
            toast("Ingresa fecha y un espesor válido (> 0).")
            return
        cml = next(c for c in eq["cmls"] if c["id"] == E["cml"])
        if any(m["fecha"] == d["fecha"] for m in cml["mediciones"]):
            if not window.confirm("Ya existe una medición en esa fecha. ¿Agregar igualmente?"):
                return
        t_mm = t * ui.IN if d["unidad"] == "in" else t
        if t_mm > (cml.get("t_nom_mm") or eq["t_nom_mm"]) * 1.15:
            toast("Aviso: el espesor medido supera en más de 15 % el nominal. Revisa la unidad.", 5000)
        m = {"fecha": d["fecha"], "espesor_mm": round(t_mm, 3), "unidad": d["unidad"], "tecnica": d["tecnica"],
             "observaciones": d["observaciones"]}
        if d["evento"]:
            m["evento"] = d["evento"]
        cml["mediciones"].append(m)
        toast(f"Medición agregada a {cml['id']}: {t_mm:.2f} mm. Recalculado.")
    elif act == "del_med":
        cml = next(c for c in eq["cmls"] if c["id"] == E["cml"])
        if window.confirm("¿Eliminar esta medición?"):
            cml["mediciones"].pop(int(ds.i))
    elif act == "add_cml":
        d = leer_form("form_cml")
        cid = d["id"].strip()
        if not cid or any(c["id"] == cid for c in eq["cmls"]):
            toast("El ID del CML es obligatorio y no puede repetirse.")
            return
        c = {"id": cid, "componente": d["componente"], "ubicacion": d["ubicacion"],
             "x": num(d["x"], 50), "y": num(d["y"], 50), "t_nom_mm": num(d["t_nom_mm"], eq["t_nom_mm"]), "mediciones": []}
        if eq["familia"] == "tanque":
            c["diseno_local"] = {"virola": int(num(d.get("virola"), 1)), "H_m": num(d.get("H_m"), eq["diseno"]["H_m"])}
        eq["cmls"].append(c)
        E["cml"] = cid
    elif act == "mover_cml":
        d = leer_form("form_xy")
        c = next(c for c in eq["cmls"] if c["id"] == E["cml"])
        c["x"], c["y"] = min(max(num(d["x"], 50), 0), 100), min(max(num(d["y"], 50), 0), 100)
    elif act == "borrar_cml":
        if window.confirm(f"¿Eliminar {E['cml']} y todo su historial?"):
            eq["cmls"] = [c for c in eq["cmls"] if c["id"] != E["cml"]]
            if eq.get("rbi") and eq["rbi"]["cml"] == E["cml"] and eq["cmls"]:
                eq["rbi"]["cml"] = eq["cmls"][0]["id"]
            E["cml"] = None
    elif act == "nuevo_eq":
        E["editando"] = "nuevo"
    elif act == "editar_eq":
        E["editando"] = "editar"
    elif act == "guardar_eq":
        if not guardar_equipo(ds.nuevo == "1"):
            return
    elif act == "borrar_eq":
        if window.confirm(f"¿Eliminar el equipo {eq['tag']} con todos sus CML?"):
            E["data"]["equipos"] = [e for e in E["data"]["equipos"] if e["id"] != eq["id"]]
            E["eq"], E["cml"] = None, None
    elif act == "del_adj":
        eq["adjuntos"].pop(int(ds.i))
    else:
        return
    cambio()


def guardar_equipo(nuevo):
    d = leer_form("form_eq")
    tag = d["tag"].strip()
    if not tag:
        toast("El TAG es obligatorio.")
        return False
    if nuevo:
        fam = d["familia"]
        if any(e["id"] == tag for e in E["data"]["equipos"]):
            toast("Ya existe un equipo con ese TAG.")
            return False
        eq = {"id": tag, "familia": fam, "diseno": copy.deepcopy(ui.DISENO_BASE[fam]), "cmls": [], "imagen": "",
              "adjuntos": [], "ubicacion": {}, "operacion": {}}
        E["data"]["equipos"].append(eq)
    else:
        eq = eq_actual()
    if ui.MATERIALES[d["material"]]["familia"] != eq["familia"]:
        toast("El material seleccionado no corresponde a la familia del equipo.")
        if nuevo:
            E["data"]["equipos"].pop()
        return False
    eq.update(tag=tag, descripcion=d["descripcion"], servicio=d["servicio"], fluido=d["fluido"],
              circuito=d["circuito"], clase=int(num(d["clase"], 2)) if d["clase"] else None, material=d["material"],
              codigo_diseno=d["codigo_diseno"], codigo_servicio=d["codigo_servicio"],
              t_nom_mm=num(d["t_nom_mm"], 0), fecha_servicio=d["fecha_servicio"])
    eq["ubicacion"] = {"planta": d["planta"], "area": d["area"] or "Sin área", "sistema": d["sistema"] or "Sin sistema"}
    eq["operacion"] = {"P_MPa": num(d["P_op"], 0), "T_C": num(d["T_op"], 20)}
    E["eq"], E["editando"], E["tab"] = eq["id"], None, ("diseno" if nuevo else "equipo")
    toast("Equipo guardado." + (" Completa ahora sus datos de diseño." if nuevo else ""))
    return True


def accion_change(el):
    act = el.dataset.act
    ds = el.dataset
    eq = eq_actual()
    if act == "filtro":
        E["filtros"][ds.campo] = el.value or None
        render()
        return
    if act == "diseno":
        v = num(el.value)
        if v is None:
            toast("Valor no numérico.")
            return
        antes = eq["diseno"].get(ds.campo)
        eq["diseno"][ds.campo] = v
        if eq["familia"] == "tanque" and ds.campo == "H_m":
            for c in eq["cmls"]:
                if c.get("diseno_local", {}).get("virola") == 1:
                    c["diseno_local"]["H_m"] = v
        toast(f"{ds.campo}: {antes} → {v}. Espesores recalculados.")
    elif act == "rbi":
        cfg = eq_rbi()["rbi"]
        c = ds.campo
        if c.startswith("insp_"):
            cfg["inspecciones"][c[5:]] = int(num(el.value, 0))
        elif c in ("pscore", "f_om", "C_A_m2", "C_E"):
            v = num(el.value)
            if v is None or v < 0 or (c == "f_om" and v == 0):
                toast("Valor inválido.")
                return
            cfg[c] = v
        else:
            cfg[c] = el.value
    elif act in ("importar", "subir_img", "subir_pdf"):
        asyncio.ensure_future(cargar_archivo(el, act))
        return
    else:
        return
    cambio()


def eq_rbi():
    return next(e for e in E["data"]["equipos"] if e.get("rbi"))


# ------------------------------------------------------------------ archivos
async def cargar_archivo(el, act):
    try:
        if act == "importar":
            nombre, texto = await leer_archivo(el)
            data = json.loads(texto)
            if "equipos" not in data:
                raise ValueError("el archivo no contiene la clave 'equipos'")
            E["data"] = data
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
            E["cml"] = None
            toast(f"Proyecto importado: {nombre} ({len(data['equipos'])} equipos).")
        else:
            nombre, url = await leer_archivo(el, como_dataurl=True)
            eq = eq_actual()
            if act == "subir_img":
                eq["imagen"] = url
                toast(f"Esquema actualizado: {nombre}")
            else:
                eq.setdefault("adjuntos", []).append({"nombre": nombre, "url": url})
                toast(f"PDF adjuntado: {nombre}")
        el.value = ""
        cambio()
    except Exception as e:
        toast(f"No se pudo leer el archivo: {e}", 6000)


async def exportar():
    data = copy.deepcopy(E["data"])
    for eq in data["equipos"]:
        img = eq.get("imagen") or ""
        if img and not img.startswith("data:"):
            r = await pyfetch(img)
            datos = await r.bytes()
            eq["imagen"] = f"data:image/png;base64,{base64.b64encode(datos).decode()}"
    data["exportado"] = date.today().isoformat()
    descargar(json.dumps(data, ensure_ascii=False, indent=1), f"proyecto_giee_{date.today()}.json", "application/json")
    toast("Proyecto exportado con equipos, CML, mediciones, esquemas y adjuntos.")


async def restablecer():
    await cargar_demo()
    E["tab"], E["filtros"], E["editando"] = "panel", {}, None
    cambio()
    toast("Caso demostrativo restablecido.")


# ------------------------------------------------------------------ eventos (delegación)
def on_click(evt):
    el = evt.target.closest("[data-act]")
    if el and el.tagName not in ("SELECT", "INPUT"):
        try:
            accion_click(el)
        except Exception as e:
            toast(f"Error: {e}", 6000)
            console_error()


def on_change(evt):
    el = evt.target
    if el.dataset and el.dataset.act:
        try:
            accion_change(el)
        except Exception as e:
            toast(f"Error: {e}", 6000)
            console_error()


def console_error():
    window.console.error(traceback.format_exc())


# ------------------------------------------------------------------ inicio
guardado = window.localStorage.getItem(CLAVE)
if guardado:
    E["data"] = json.loads(guardado)
    E["eq"] = E["data"]["equipos"][0]["id"] if E["data"]["equipos"] else None
else:
    await cargar_demo()

document.addEventListener("click", create_proxy(on_click))
document.addEventListener("change", create_proxy(on_change))
document.getElementById("cargando").hidden = True
document.getElementById("app").hidden = False
render()
if guardado:
    toast("Proyecto recuperado desde el almacenamiento del navegador.")
