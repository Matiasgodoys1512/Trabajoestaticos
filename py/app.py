"""Aplicación PyScript: estado, eventos del navegador, persistencia e importación/exportación.

Seguridad: todo dato externo (archivo importado, localStorage, archivos subidos) se valida con
`proyecto.validar_proyecto` antes de usarse; los textos se escapan en `ui.esc`; los adjuntos solo
se aceptan como PNG/JPG/PDF verificando tamaño, tipo MIME y firma binaria.
"""
import asyncio
import base64
import copy
import json
import traceback
from datetime import date, datetime

import pandas as pd
from pyodide.ffi import create_proxy, to_js
from pyodide.http import pyfetch
from pyscript import document, window

import proyecto
import ui

CLAVE = "giee_proyecto_v1"
LIMITES = {"importar": 25_000_000, "subir_img": 1_500_000, "subir_pdf": 3_000_000}
FIRMAS = {"image/png": b"\x89PNG", "image/jpeg": b"\xff\xd8\xff", "application/pdf": b"%PDF"}
FORM_ACCION = {"form_med": "add_med", "form_cml": "add_cml", "form_xy": "mover_cml", "form_eq": "guardar_eq"}
E = {"data": None, "eq": None, "cml": None, "tab": "panel", "filtros": {}, "editando": None}
_proxies = []  # referencias vivas a los proxies de eventos


# ------------------------------------------------------------------ utilidades
def attr(el, nombre):
    """Lee data-<nombre> sin lanzar error si no existe (en Pyodide un atributo ausente lanza AttributeError)."""
    if el is None or not hasattr(el, "getAttribute"):
        return None
    return el.getAttribute(f"data-{nombre}")


def toast(msg, ms=3200, error=False):
    t = document.getElementById("toast")
    t.innerText = msg
    t.classList.toggle("toast-error", error)
    t.hidden = False
    p = create_proxy(lambda: setattr(t, "hidden", True))
    _proxies.append(p)
    window.setTimeout(p, ms)


def eq_actual():
    return next((e for e in E["data"]["equipos"] if e["id"] == E["eq"]), None)


def cml_actual(eq):
    return next((c for c in eq["cmls"] if c["id"] == E["cml"]), None) if eq else None


def leer_form(fid):
    form = document.getElementById(fid)
    out = {}
    if form is None:
        return out
    for i in range(form.elements.length):
        el = form.elements.item(i)
        if el.name:
            out[el.name] = el.value
    return out


def descargar(texto, nombre, mime):
    blob = window.Blob.new(to_js([texto]), to_js({"type": mime}, dict_converter=window.Object.fromEntries))
    url = window.URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href, a.download = url, nombre
    a.click()
    window.URL.revokeObjectURL(url)


def guardar_local(aviso=False):
    try:
        window.localStorage.setItem(CLAVE, json.dumps(E["data"], ensure_ascii=False))
        document.getElementById("estado-guardado").innerText = f"Guardado {datetime.now():%H:%M}"
        if aviso:
            toast("Proyecto guardado en este navegador.")
        return True
    except Exception:  # noqa: BLE001 — QuotaExceededError u otro error del navegador
        document.getElementById("estado-guardado").innerText = "Sin guardar"
        toast("No se pudo guardar en el navegador (espacio insuficiente). Usa «Exportar».", 6000, True)
        return False


async def cargar_demo():
    r = await pyfetch("data/demo.json", cache="no-store")
    E["data"] = proyecto.validar_proyecto(json.loads(await r.string()))
    E["eq"] = E["data"]["equipos"][0]["id"]
    E["cml"] = None


# ------------------------------------------------------------------ render
def render():
    try:
        data = E["data"]
        res = ui.evaluar_todo(data)
        if not eq_actual():
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
            E["cml"] = None
        document.getElementById("sidebar").innerHTML = ui.sidebar(data, res, E["eq"], E["filtros"])
        for b in document.querySelectorAll("#tabs button"):
            activo = attr(b, "tab") == E["tab"] and E["editando"] is None
            b.classList.toggle("activo", activo)
            b.setAttribute("aria-selected", "true" if activo else "false")
        eq = eq_actual()
        t = E["tab"]
        sin = '<div class="info">No hay equipos. Crea uno con «+ Nuevo equipo».</div>'
        if E["editando"] is not None:
            html = ui.form_equipo(None if E["editando"] == "nuevo" else eq)
        elif t == "panel":
            html = ui.panel(data, res, E["filtros"])
        elif t == "equipo":
            html = ui.vista_equipo(data, res, eq, E["cml"]) if eq else sin
        elif t == "diseno":
            html = ui.vista_diseno(eq, res[eq["id"]]) if eq else sin
        elif t == "rbi":
            html = ui.vista_rbi(data, res)
        elif t == "validacion":
            html = ui.vista_validacion()
        else:
            html = ui.vista_acerca()
        document.getElementById("contenido").innerHTML = html
    except Exception as e:  # noqa: BLE001 — límite de error: nunca dejar la pantalla en blanco
        window.console.error(traceback.format_exc())
        document.getElementById("contenido").innerHTML = (
            f'<div class="error">✕ Error al mostrar la vista: {ui.esc(e)}. '
            'Puedes restablecer el caso demostrativo desde la barra superior.</div>')


def cambio():
    guardar_local()
    render()


# ------------------------------------------------------------------ acciones de clic
def accion_click(el):
    act = attr(el, "act")
    eq = eq_actual()

    if act == "tab":
        E["tab"], E["editando"] = attr(el, "tab"), None
        render()
        return
    if act == "sel_eq":
        E["eq"], E["editando"] = attr(el, "id"), None
        E["cml"] = attr(el, "cml") or None
        if E["tab"] in ("panel", "validacion", "acerca", "rbi"):
            E["tab"] = "equipo"
        render()
        return
    if act == "sel_cml":
        E["cml"] = attr(el, "id")
        render()
        return
    if act == "guardar":
        guardar_local(True)
        return
    if act == "exportar":
        asyncio.ensure_future(exportar())
        return
    if act == "exportar_csv":
        filas = ui.filas_panel(E["data"], ui.evaluar_todo(E["data"]), E["filtros"])
        if not filas:
            toast("No hay filas para exportar con los filtros actuales.")
            return
        df = pd.DataFrame(filas).drop(columns=["_eq", "_cml"])
        descargar("﻿" + df.to_csv(index=False, sep=";", decimal=","), f"resumen_cml_{date.today()}.csv", "text/csv")
        toast(f"CSV exportado ({len(df)} filas).")
        return
    if act == "restablecer":
        if window.confirm("¿Restablecer el caso demostrativo? Se perderán los cambios no exportados."):
            asyncio.ensure_future(restablecer())
        return
    if act == "nuevo_eq":
        E["editando"] = "nuevo"
        render()
        return
    if act == "editar_eq":
        E["editando"] = "editar"
        render()
        return
    if act == "cancelar_eq":
        E["editando"] = None
        render()
        return
    if act == "limpiar_filtros":
        E["filtros"] = {}
        render()
        return

    # --- acciones que modifican datos (se guardan) ---
    if act == "add_med":
        if not agregar_medicion(eq):
            return
    elif act == "del_med":
        c = cml_actual(eq)
        if not window.confirm("¿Eliminar esta medición?"):
            return
        c["mediciones"].pop(int(attr(el, "i")))
        toast("Medición eliminada.")
    elif act == "add_cml":
        if not agregar_cml(eq):
            return
    elif act == "mover_cml":
        d = leer_form("form_xy")
        c = cml_actual(eq)
        x, y = proyecto.numero(d.get("x")), proyecto.numero(d.get("y"))
        if x is None or y is None or not (0 <= x <= 100 and 0 <= y <= 100):
            toast("Las coordenadas deben estar entre 0 y 100 %.", error=True)
            return
        c["x"], c["y"] = x, y
        toast(f"Marcador de {c['id']} movido a ({x:g}; {y:g}) %.")
    elif act == "borrar_cml":
        if not window.confirm(f"¿Eliminar {E['cml']} y todo su historial?"):
            return
        eq["cmls"] = [c for c in eq["cmls"] if c["id"] != E["cml"]]
        if eq.get("rbi") and eq["rbi"]["cml"] == E["cml"]:
            eq["rbi"]["cml"] = eq["cmls"][0]["id"] if eq["cmls"] else ""
        E["cml"] = None
    elif act == "guardar_eq":
        if not guardar_equipo(attr(el, "nuevo") == "1"):
            return
    elif act == "borrar_eq":
        if not window.confirm(f"¿Eliminar el equipo {eq['tag']} con todos sus CML y mediciones?"):
            return
        E["data"]["equipos"] = [e for e in E["data"]["equipos"] if e["id"] != eq["id"]]
        E["eq"], E["cml"] = None, None
        toast("Equipo eliminado.")
    elif act == "del_adj":
        eq["adjuntos"].pop(int(attr(el, "i")))
    else:
        return
    cambio()


def agregar_medicion(eq):
    c = cml_actual(eq)
    d = leer_form("form_med")
    t = proyecto.numero(d.get("espesor"))
    f = proyecto.fecha_valida(d.get("fecha"))
    if f is None:
        toast("Ingresa una fecha válida.", error=True)
        return False
    if t is None or t <= 0:
        toast("Ingresa un espesor mayor que 0.", error=True)
        return False
    if date.fromisoformat(f) > date.today():
        toast("La fecha de la medición no puede ser futura.", error=True)
        return False
    t_mm = t * ui.IN if d.get("unidad") == "in" else t
    if t_mm > 300:
        toast("Espesor fuera de rango (> 300 mm). Revisa la unidad.", error=True)
        return False
    if any(m["fecha"] == f for m in c["mediciones"]) and not window.confirm(
            "Ya existe una medición en esa fecha para este CML. ¿Agregarla igualmente?"):
        return False
    nominal = c.get("t_nom_mm") or eq["t_nom_mm"]
    if nominal and t_mm > nominal * 1.15 and not window.confirm(
            f"El espesor ({t_mm:.2f} mm) supera en más de 15 % el nominal ({nominal:.2f} mm). ¿Es correcto?"):
        return False
    m = {"fecha": f, "espesor_mm": round(t_mm, 4), "unidad": d.get("unidad", "mm"),
         "tecnica": proyecto.texto(d.get("tecnica"), 40), "observaciones": proyecto.texto(d.get("observaciones"), 300)}
    if d.get("evento") in proyecto.EVENTOS:
        m["evento"] = d["evento"]
    c["mediciones"].append(m)
    toast(f"Medición agregada a {c['id']}: {t_mm:.2f} mm. Cálculos actualizados.")
    return True


def agregar_cml(eq):
    d = leer_form("form_cml")
    cid = proyecto.texto(d.get("id"), 40)
    if not cid:
        toast("El ID del CML es obligatorio.", error=True)
        return False
    if any(c["id"] == cid for c in eq["cmls"]):
        toast(f"Ya existe el CML {cid} en este equipo.", error=True)
        return False
    x, y = proyecto.numero(d.get("x")), proyecto.numero(d.get("y"))
    if x is None or y is None or not (0 <= x <= 100 and 0 <= y <= 100):
        toast("Las coordenadas deben estar entre 0 y 100 %.", error=True)
        return False
    tn = proyecto.numero(d.get("t_nom_mm"))
    c = {"id": cid, "componente": proyecto.texto(d.get("componente")), "ubicacion": proyecto.texto(d.get("ubicacion")),
         "x": x, "y": y, "t_nom_mm": tn if tn and 0 < tn <= 300 else eq["t_nom_mm"], "mediciones": []}
    if eq["familia"] == "tanque":
        vir, msg1 = proyecto.validar_campo_diseno("virola", d.get("virola") or 1)
        h, msg2 = proyecto.validar_campo_diseno("H_m", d.get("H_m") or eq["diseno"]["H_m"])
        if msg1 or msg2:
            toast(msg1 or msg2, error=True)
            return False
        c["diseno_local"] = {"virola": int(vir), "H_m": h}
    eq["cmls"].append(c)
    E["cml"] = cid
    toast(f"CML {cid} agregado. Registra su primera medición.")
    return True


def guardar_equipo(nuevo):
    d = leer_form("form_eq")
    tag = proyecto.texto(d.get("tag"), 60)
    if not tag:
        toast("El TAG es obligatorio.", error=True)
        return False
    fam = d.get("familia") if nuevo else eq_actual()["familia"]
    if ui.MATERIALES[d["material"]]["familia"] != fam:
        toast("El material seleccionado no corresponde a la familia del equipo.", error=True)
        return False
    t_nom = proyecto.numero(d.get("t_nom_mm"))
    if t_nom is None or not 0 < t_nom <= 300:
        toast("Ingresa un espesor nominal válido (0–300 mm).", error=True)
        return False
    if not proyecto.fecha_valida(d.get("fecha_servicio")):
        toast("Ingresa la fecha de puesta en servicio.", error=True)
        return False
    if nuevo:
        if any(e["id"] == tag for e in E["data"]["equipos"]):
            toast("Ya existe un equipo con ese TAG.", error=True)
            return False
        eq = {"id": tag, "familia": fam, "diseno": copy.deepcopy(ui.DISENO_BASE[fam]), "cmls": [], "imagen": "",
              "adjuntos": []}
        E["data"]["equipos"].append(eq)
    else:
        eq = eq_actual()
    clase = proyecto.numero(d.get("clase"))
    eq.update(tag=tag, descripcion=proyecto.texto(d.get("descripcion"), 200), servicio=proyecto.texto(d.get("servicio")),
              fluido=proyecto.texto(d.get("fluido")), circuito=proyecto.texto(d.get("circuito"), 60),
              clase=int(clase) if clase in (1, 2, 3, 4) else (2 if fam == "tuberia" else None), material=d["material"],
              codigo_diseno=proyecto.texto(d.get("codigo_diseno"), 80), codigo_servicio=proyecto.texto(d.get("codigo_servicio"), 80),
              t_nom_mm=t_nom, fecha_servicio=proyecto.fecha_valida(d.get("fecha_servicio")))
    eq["ubicacion"] = {"planta": proyecto.texto(d.get("planta"), 80) or "Planta",
                       "area": proyecto.texto(d.get("area"), 80) or "Sin área",
                       "sistema": proyecto.texto(d.get("sistema"), 80) or "Sin sistema"}
    eq["operacion"] = {"P_MPa": proyecto.numero(d.get("P_op")) or 0.0, "T_C": proyecto.numero(d.get("T_op")) or 20.0}
    E["eq"], E["cml"], E["editando"] = eq["id"], None, None
    E["tab"] = "diseno" if nuevo else "equipo"
    toast("Equipo guardado." + (" Completa ahora sus datos de diseño." if nuevo else ""))
    return True


# ------------------------------------------------------------------ acciones de cambio (inputs)
def accion_change(el):
    act = attr(el, "act")
    campo = attr(el, "campo")
    eq = eq_actual()
    if act == "filtro":
        E["filtros"][campo] = el.value or None
        render()
        return
    if act == "form_familia":
        mat = document.querySelector('#form_eq select[name="material"]')
        mat.innerHTML = ui.opciones_material(el.value)
        return
    if act == "diseno":
        v, msg = proyecto.validar_campo_diseno(campo, el.value)
        if msg:
            toast(msg, error=True)
            render()
            return
        antes = eq["diseno"].get(campo)
        eq["diseno"][campo] = v
        if eq["familia"] == "tanque" and campo == "H_m":
            for c in eq["cmls"]:
                if c.get("diseno_local", {}).get("virola") == 1:
                    c["diseno_local"]["H_m"] = v
        toast(f"{proyecto.RANGOS.get(campo, (0, 0, 0, campo))[3]}: {ui.f(antes, 3)} → {ui.f(v, 3)}. Recalculado.")
    elif act == "rbi":
        cfg = eq_rbi()["rbi"]
        if campo.startswith("insp_"):
            n = proyecto.numero(el.value)
            if n is None or n < 0 or n > 20 or n != int(n):
                toast("N° de inspecciones: entero entre 0 y 20.", error=True)
                render()
                return
            cfg["inspecciones"][campo[5:]] = int(n)
        elif campo in ("pscore", "f_om", "C_A_m2", "C_E"):
            v = proyecto.numero(el.value)
            lim = {"pscore": (0, 100), "f_om": (0.1, 10), "C_A_m2": (0, 1e7), "C_E": (0, 1e12)}[campo]
            if v is None or not lim[0] <= v <= lim[1]:
                toast(f"Valor fuera de rango ({lim[0]:g} – {lim[1]:g}).", error=True)
                render()
                return
            cfg[campo] = v
        elif campo == "fecha_eval":
            cfg[campo] = proyecto.fecha_valida(el.value) or ""
        elif campo in ("cml", "confianza", "moneda", "base_valoracion"):
            cfg[campo] = proyecto.texto(el.value, 200)
        else:
            return
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
    archivo = el.files.item(0) if el.files.length else None
    el.value = ""
    if archivo is None:
        return
    try:
        if archivo.size > LIMITES[act]:
            raise ValueError(f"archivo demasiado grande ({archivo.size / 1e6:.1f} MB; máx. {LIMITES[act] / 1e6:.1f} MB)")
        datos = (await archivo.arrayBuffer()).to_py().tobytes()
        if act == "importar":
            data = proyecto.validar_proyecto(json.loads(datos.decode("utf-8-sig")))
            E["data"], E["cml"], E["editando"], E["filtros"] = data, None, None, {}
            E["eq"] = data["equipos"][0]["id"] if data["equipos"] else None
            toast(f"Proyecto importado: {archivo.name} ({len(data['equipos'])} equipos).")
        else:
            permitidos = ("image/png", "image/jpeg") if act == "subir_img" else ("application/pdf",)
            mime = archivo.type
            if mime not in permitidos or not datos.startswith(FIRMAS[mime]):
                raise ValueError("tipo de archivo no permitido" + (" (solo PNG o JPG)" if act == "subir_img" else " (solo PDF)"))
            url = f"data:{mime};base64,{base64.b64encode(datos).decode()}"
            eq = eq_actual()
            if act == "subir_img":
                eq["imagen"] = url
                toast(f"Esquema actualizado: {archivo.name}")
            else:
                if len(eq["adjuntos"]) >= proyecto.MAX_ADJ:
                    raise ValueError(f"máximo {proyecto.MAX_ADJ} PDF por equipo")
                eq["adjuntos"].append({"nombre": proyecto.texto(archivo.name, 120), "url": url})
                toast(f"PDF adjuntado: {archivo.name}")
        cambio()
    except proyecto.ErrorProyecto as e:
        toast(f"Archivo rechazado: {e.errores[0]}" + (f" (+{len(e.errores) - 1} problemas más)" if len(e.errores) > 1 else ""), 8000, True)
    except Exception as e:  # noqa: BLE001
        toast(f"No se pudo leer el archivo: {e}", 6000, True)


async def exportar():
    try:
        data = copy.deepcopy(E["data"])
        for eq in data["equipos"]:
            img = eq.get("imagen") or ""
            if img and not img.startswith("data:"):
                r = await pyfetch(img)
                mime = "image/jpeg" if img.lower().endswith((".jpg", ".jpeg")) else "image/png"
                eq["imagen"] = f"data:{mime};base64,{base64.b64encode(await r.bytes()).decode()}"
        data["exportado"] = datetime.now().isoformat(timespec="seconds")
        descargar(json.dumps(data, ensure_ascii=False, indent=1), f"proyecto_giee_{date.today()}.json", "application/json")
        toast("Proyecto exportado: equipos, CML, mediciones, esquemas y adjuntos.")
    except Exception as e:  # noqa: BLE001
        toast(f"No se pudo exportar: {e}", 6000, True)


async def restablecer():
    await cargar_demo()
    E["tab"], E["filtros"], E["editando"] = "panel", {}, None
    cambio()
    toast("Caso demostrativo restablecido.")


# ------------------------------------------------------------------ eventos (delegación)
def _seguro(fn, el):
    try:
        fn(el)
    except Exception as e:  # noqa: BLE001
        window.console.error(traceback.format_exc())
        toast(f"Error inesperado: {e}", 6000, True)


def on_click(evt):
    el = evt.target.closest("[data-act]")
    if el is not None and el.tagName not in ("SELECT", "INPUT", "TEXTAREA"):
        evt.preventDefault()
        _seguro(accion_click, el)


def on_change(evt):
    if attr(evt.target, "act"):
        _seguro(accion_change, evt.target)


def on_submit(evt):
    evt.preventDefault()  # el botón del formulario ya recibe un clic (también con Enter)


def on_keydown(evt):
    if evt.key in ("Enter", " ") and evt.target.getAttribute("role") == "button":
        evt.preventDefault()
        _seguro(accion_click, evt.target)


def registrar(tipo, fn):
    p = create_proxy(fn)
    _proxies.append(p)
    document.addEventListener(tipo, p)


# ------------------------------------------------------------------ inicio
async def iniciar():
    guardado = window.localStorage.getItem(CLAVE)
    recuperado = False
    if guardado:
        try:
            E["data"] = proyecto.validar_proyecto(json.loads(guardado))
            E["eq"] = E["data"]["equipos"][0]["id"] if E["data"]["equipos"] else None
            recuperado = True
        except Exception:  # noqa: BLE001 — datos corruptos o de otra versión
            window.localStorage.removeItem(CLAVE)
    if not recuperado:
        await cargar_demo()
    for tipo, fn in (("click", on_click), ("change", on_change), ("submit", on_submit), ("keydown", on_keydown)):
        registrar(tipo, fn)
    document.getElementById("cargando").hidden = True
    document.getElementById("app").hidden = False
    render()
    document.getElementById("estado-guardado").innerText = "Recuperado del navegador" if recuperado else "Caso demo"
    if guardado and not recuperado:
        toast("Los datos guardados estaban dañados: se cargó el caso demostrativo.", 6000, True)


await iniciar()
