"""Prueba de punta a punta en navegador real (Playwright + Chromium local en .venv).

Uso:  .venv/Scripts/python tools/e2e.py [URL] [carpeta_capturas]
Por defecto levanta un servidor local en el puerto 8765 y recorre el flujo de la demo
(sección 8 del enunciado). Termina con código 1 si hay errores de consola o fallas.
"""
import contextlib
import functools
import http.server
import os
import pathlib
import socketserver
import sys
import threading

RAIZ = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(RAIZ / ".venv" / "ms-playwright"))
from playwright.sync_api import sync_playwright, expect  # noqa: E402


@contextlib.contextmanager
def servidor(puerto=8765):
    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Silencioso, directory=str(RAIZ))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", puerto), handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            yield f"http://127.0.0.1:{puerto}/"
        finally:
            httpd.shutdown()


def recorrer(url, salida):
    salida.mkdir(parents=True, exist_ok=True)
    errores, fallas = [], []

    def paso(nombre, fn):
        try:
            fn()
            print(f"  OK   {nombre}")
        except Exception as e:  # noqa: BLE001
            fallas.append(f"{nombre}: {e}")
            print(f"  FALLA {nombre}: {(str(e) or repr(e)).splitlines()[0][:200]}")

    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        pg = ctx.new_page()
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(url)
        pg.wait_for_selector("#app:not([hidden])", timeout=180_000)
        print("App cargada")
        cap = lambda n: pg.screenshot(path=str(salida / f"{n}.png"), full_page=True)  # noqa: E731

        def ir(tab):
            pg.locator(f'#tabs [data-tab="{tab}"]').click()
            pg.wait_for_timeout(300)

        def menu(act):
            pg.locator("details.menu > summary").click()
            pg.locator(f'.menu-panel [data-act="{act}"]').click()

        def abrir_equipo(tag):
            ir("equipos")
            pg.locator(".eq-item").filter(has=pg.locator(".eq-tag", has_text=tag)).click()
            pg.wait_for_timeout(300)

        def inicio():
            assert "#/inicio" in pg.url, f"no abrió en Inicio: {pg.url}"
            expect(pg.locator(".hero h1")).to_be_visible()
            assert pg.locator(".familia").count() == 3, "faltan las 3 familias en la portada"
            assert pg.locator(".fila-accion").count() >= 3, "faltan los puntos que requieren atención"
            assert not pg.locator("#sidebar").is_visible(), "la barra lateral no debe verse en Inicio"
            cap("00_inicio")
        paso("Abre en una portada (Inicio) con familias y puntos críticos", inicio)

        def familias():
            pg.locator('.familia-pie [data-act="ir_familia"][data-familia="tuberia"]').click()
            pg.wait_for_timeout(500)
            assert "#/planta" in pg.url, pg.url
            assert pg.locator('.filtros select[data-campo="familia"]').input_value() == "tuberia"
            assert pg.locator("#tabla-cml tr.click").count() == 4, "la familia no filtró la tabla"
            pg.locator('[data-act="limpiar_filtros"]').first.click()
            ir("inicio")
            pg.locator('.fam-menu:has([data-familia="tanque"]) > summary').click()
            menu_tk = pg.locator('.fam-menu:has([data-familia="tanque"]) .fam-menu-panel')
            expect(menu_tk).to_be_visible()
            assert menu_tk.locator('[data-act="sel_eq"]').count() == 1, "el menú debe listar todos los tanques"
            cap("00b_menu_familia")
            pg.locator('.fam-menu:has([data-familia="recipiente"]) > summary').click()
            assert not menu_tk.is_visible(), "abrir otro menú debe cerrar el anterior"
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(200)
            assert pg.locator("details.fam-menu[open]").count() == 0, "Escape no cerró el menú"
            pg.locator('.fam-menu:has([data-familia="tanque"]) > summary').click()
            menu_tk.locator('[data-act="sel_eq"][data-id="TK-301"]').click()
            pg.wait_for_timeout(500)
            assert "#/equipos/TK-301" in pg.url, pg.url
            ir("inicio")
            pg.locator('.ilu-eq[data-familia="recipiente"]').click()
            pg.wait_for_timeout(500)
            assert pg.locator('.filtros select[data-campo="familia"]').input_value() == "recipiente"
            pg.locator('[data-act="limpiar_filtros"]').first.click()
            ir("inicio")
        paso("Familias de la portada: filtran Planta y abren cada equipo", familias)

        def critico():
            pg.locator('[data-act="ir_critico"]').click()
            pg.wait_for_timeout(500)
            assert "CML-201-03" in pg.url, f"no llevó al CML crítico: {pg.url}"
            expect(pg.locator(".migas")).to_be_visible()
            pg.go_back()
            pg.wait_for_timeout(600)
            assert "#/inicio" in pg.url and pg.locator(".hero").count() == 1, "el botón Atrás no volvió a Inicio"
        paso("«Ir al punto más crítico» y botón Atrás del navegador", critico)

        def panel():
            ir("planta")
            expect(pg.locator(".stat").first).to_be_visible()
            assert pg.locator("#tabla-cml tr.click").count() >= 9, "faltan filas en Planta"
            pg.select_option('.filtros select[data-campo="familia"]', "tanque")
            pg.wait_for_timeout(500)
            assert pg.locator("#tabla-cml tr.click").count() == 3, "el filtro por familia no funcionó"
            assert pg.locator("#calidad tr.click").count() == 1, "calidad de datos debe respetar el filtro"
            pg.locator('[data-act="limpiar_filtros"]').first.click()
            pg.wait_for_timeout(400)
            cap("01_panel")
        paso("Planta: tabla de CML con filtros junto a la tabla", panel)

        def plano():
            ir("planta")
            assert pg.locator(".pl-area").count() >= 2, "faltan áreas en el plano"
            assert pg.locator(".pl-eq").count() == 3, "faltan equipos en el plano"
            assert pg.locator('.pl-eq[data-eq="V-201"] .pl-aviso').count() == 1, "V-201 debe tener aviso"
            assert pg.locator('.pl-eq[data-eq="L-101"] .pl-aviso').count() == 1, "la línea debe tener aviso"
            pop = pg.locator('.pl-eq[data-eq="V-201"] .pl-pop')
            assert not pop.is_visible(), "el pop-up no debe verse antes del clic"
            pg.locator('.pl-eq[data-eq="V-201"]').click()
            expect(pop).to_be_visible()
            cap("01b_plano_popup")
            pop.locator('.pl-cml[data-cml="CML-201-02"]').click()
            pg.wait_for_timeout(600)
            assert "CML-201-02" in pg.url, f"el pop-up no abrió el CML: {pg.url}"
            pg.go_back()
            pg.wait_for_timeout(500)
            pg.locator(".pl-area-cab").first.click()
            pg.wait_for_timeout(400)
            assert pg.locator(".pl-area.sel").count() == 1 and pg.locator(".pl-eq.atenuado").count() >= 1, "el área no filtró"
            assert pg.locator(".filtros-activos .filtro-chip").count() == 1, "falta el filtro activo visible"
            pg.locator(".pl-area.sel .pl-area-cab").click()          # segundo clic: deselecciona
            pg.wait_for_timeout(400)
            assert pg.locator(".pl-area.sel").count() == 0 and pg.locator(".filtros-activos").count() == 0, "el área no se deseleccionó"
            pg.locator(".pl-area-cab").first.click()
            pg.wait_for_timeout(300)
            pg.locator('.filtro-chip[data-campo="area"]').click()     # quitar con la «✕» del filtro
            pg.wait_for_timeout(300)
            assert pg.locator(".pl-area.sel").count() == 0, "la ✕ del filtro no lo quitó"
        paso("Plano de planta: avisos, pop-up con CML y filtro por área", plano)

        def equipo():
            abrir_equipo("V-201")
            assert pg.locator(".chip.sel").get_attribute("data-id") == "CML-201-03", "no abrió el CML más crítico por defecto"
            pg.locator('.chip[data-id="CML-201-02"]').click()
            expect(pg.locator(".grafico img")).to_be_visible()
            ficha = pg.locator(".ficha-cml").inner_text()
            assert "Pérdida acumulada" in ficha and "Llega a t mín" in ficha, "falta la ficha del CML"
            cap("02_equipo_cml")
        paso("Equipo: abre el CML crítico; se puede elegir otro", equipo)

        def enlace_directo():
            url = pg.url
            pg.goto("about:blank")
            pg.goto(url)
            pg.wait_for_selector("#app:not([hidden])", timeout=180_000)
            assert pg.locator(".chip.sel").get_attribute("data-id") == "CML-201-02", "el enlace no restauró el CML"
        paso("La URL lleva directo al equipo y CML (enlace compartible)", enlace_directo)

        def medicion():
            antes = pg.locator(".stat .v").nth(0).inner_text()
            pg.fill('#form_med input[name="espesor"]', "12.4")
            pg.locator('#form_med [data-act="add_med"]').click()
            pg.wait_for_timeout(800)
            despues = pg.locator(".stat .v").nth(0).inner_text()
            assert antes != despues, f"t actual no cambió ({antes})"
            assert pg.locator("#btn-guardar.sucio").count() == 1, "el botón Guardar debía marcar cambios pendientes"
            cap("03_medicion_agregada")
            pg.keyboard.press("Control+s")
            pg.wait_for_timeout(500)
            assert pg.locator("#btn-guardar.sucio").count() == 0, "Ctrl+S no guardó"
            pg.reload()
            pg.wait_for_selector("#app:not([hidden])", timeout=180_000)
            pg.wait_for_timeout(800)
            assert pg.locator(".stat .v").nth(0).inner_text() == despues, "la medición guardada no persistió"
        paso("Agregar medición y recalcular", medicion)

        def diseno():
            pg.locator('[data-act="subvista"][data-vista="diseno"]').click()
            pg.wait_for_timeout(300)
            campo = pg.locator('input[data-campo="P_diseno_MPa"]')
            assert pg.locator(".esc-fila .val").first.inner_text().strip().endswith("mm"), "falta la unidad en la escalera"
            antes = pg.locator(".esc-fila .val").nth(5).inner_text()
            campo.fill("2.0")
            campo.press("Tab")
            pg.wait_for_timeout(800)
            despues = pg.locator(".esc-fila .val").nth(5).inner_text()
            assert antes != despues, "t requerido no cambió al cambiar P"
            assert "→" in pg.locator(".cambio").inner_text(), "falta el aviso antes → después"
            assert pg.locator("label.editado").count() == 1, "el campo editado no quedó marcado"
            cap("04_diseno")
            pg.locator('.revertir[data-campo="P_diseno_MPa"]').click()
            pg.wait_for_timeout(600)
            assert float(pg.locator('input[data-campo="P_diseno_MPa"]').input_value()) == 1.5, "↺ no volvió al valor del demo"
            assert pg.locator("label.editado").count() == 0
        paso("Cambiar variable de diseño y ver efecto en espesor", diseno)

        def rbi():
            ir("rbi")
            antes = pg.locator(".stat").nth(3).inner_text()
            campo = pg.locator('input[data-campo="C_E"]')
            campo.fill("5000000")
            campo.press("Tab")
            pg.wait_for_timeout(800)
            despues = pg.locator(".stat").nth(3).inner_text()
            assert antes != despues, "riesgo económico no cambió"
            campo = pg.locator('input[data-campo="C_E"]')
            campo.fill("20000000")
            campo.press("Tab")
            pg.wait_for_timeout(800)
            assert "125.823" in pg.locator(".stat").nth(3).inner_text(), "R_E debe mostrarse con separador de miles"
            assert "Prioridad" in pg.locator(".cambio").inner_text() or "prioridad" in pg.locator(".cambio").inner_text()
            cap("05_rbi")
        paso("Modificar consecuencia y ver cambio de riesgo", rbi)

        def validacion():
            ir("validacion")
            txt = pg.locator(".kpi-v").first.inner_text()
            n, tot = txt.split("/")
            assert n.strip() == tot.strip(), f"validación incompleta: {txt}"
            pg.locator('[data-act="val_fam"][data-fam="tanque"]').click()
            pg.wait_for_timeout(400)
            assert pg.locator(".val-grupo").count() == 1, "el filtro de familia no funcionó"
            pg.locator("details.val-caso > summary").first.click()
            expect(pg.locator("details.val-caso[open] .val-det")).to_be_visible()
            pg.locator('[data-act="val_fam"][data-fam=""]').click()
            pg.wait_for_timeout(300)
            cap("06_validacion")
        paso("Validación: todos los casos OK", validacion)

        def plan_y_fecha():
            ir("plan")
            grupos = pg.locator(".plan-grupo").all_inner_texts()
            assert grupos and grupos[0].startswith("Acción inmediata") and grupos[1].startswith("Vencidas"), grupos
            cap("06b_plan")
            ir("planta")
            assert pg.locator("#calidad tr.click").count() >= 2, "faltan avisos de calidad de datos"
            vencidas = lambda: int(pg.locator(".stat.estado").nth(3).locator(".v").inner_text().strip()[-1])  # noqa: E731
            antes = vencidas()
            pg.fill("#fecha-eval", "2027-06-01")
            pg.wait_for_timeout(1000)
            assert vencidas() > antes, "adelantar la fecha de evaluación no venció ningún CML"
            assert pg.locator("#caja-fecha.fija").count() == 1
            pg.fill("#fecha-eval", "2026-11-26")
            pg.wait_for_timeout(800)
            assert vencidas() == antes
        paso("Plan de inspección, calidad de datos y fecha de evaluación", plan_y_fecha)

        def tanque():
            abrir_equipo("TK-301")
            pg.locator('.chip[data-id="CML-301-01"]').click()
            expect(pg.locator(".grafico img")).to_be_visible()
            cap("07_tanque")
            pg.locator('[data-act="subvista"][data-vista="diseno"]').click()
            pg.wait_for_timeout(300)
            cap("08_tanque_diseno")
        paso("Tanque: CML y diseño por virola", tanque)

        def exportar_importar():
            with pg.expect_download() as d:
                menu("exportar")
            ruta = salida / "proyecto_exportado.json"
            d.value.save_as(ruta)
            assert ruta.stat().st_size > 10_000
            assert pg.locator("details.menu[open]").count() == 0, "el menú no se cerró tras elegir una opción"
            menu("restablecer")
            pg.wait_for_timeout(1500)
            assert "#/inicio" in pg.url
            pg.set_input_files('input[data-act="importar"]', str(ruta))
            pg.wait_for_timeout(1500)
            assert "importado" in pg.locator("#toast").inner_text().lower()
            cap("09_importado")
        paso("Menú Proyecto: exportar, restablecer e importar", exportar_importar)

        def adjuntos_usuario():
            pdf = salida / "informe_prueba.pdf"
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
            abrir_equipo("V-201")
            pg.set_input_files('input[data-act="subir_img"]', str(RAIZ / "data" / "img" / "tanque_TK301.png"))
            pg.wait_for_timeout(1200)
            pg.set_input_files('input[data-act="subir_pdf"]', str(pdf))
            pg.wait_for_timeout(1200)
            with pg.expect_download() as d:
                menu("exportar")
            ruta = salida / "proyecto_con_adjuntos.json"
            d.value.save_as(ruta)
            menu("restablecer")
            pg.wait_for_timeout(1500)
            abrir_equipo("V-201")
            assert pg.locator("text=informe_prueba.pdf").count() == 0, "el PDF no debía estar tras restablecer"
            pg.set_input_files('input[data-act="importar"]', str(ruta))
            pg.wait_for_timeout(1500)
            abrir_equipo("V-201")
            assert pg.locator("text=informe_prueba.pdf").count() == 1, "el PDF no se recuperó al importar"
            src = pg.locator(".esquema img").get_attribute("src")
            assert src.startswith("data:image/png;base64,"), "el esquema subido no se recuperó"
            cap("09b_adjuntos_recuperados")
        paso("Adjuntos del usuario (PNG y PDF) se conservan al exportar/importar", adjuntos_usuario)

        def persistencia():
            pg.reload()
            pg.wait_for_selector("#app:not([hidden])", timeout=180_000)
            ir("planta")
            assert pg.locator("tr.click").count() >= 9
        paso("Recuperar desde almacenamiento del navegador", persistencia)

        def nuevo_equipo():
            ir("equipos")
            pg.locator('[data-act="nuevo_eq"]').click()
            pg.fill('#form_eq input[name="tag"]', "2\"-AG-999")
            pg.fill('#form_eq input[name="area"]', "Área 900 - Pruebas")
            pg.fill('#form_eq input[name="t_nom_mm"]', "5.54")
            pg.locator('[data-act="guardar_eq"]').click()
            pg.wait_for_timeout(800)
            assert pg.locator(".eq-item", has_text="AG-999").count() == 1, pg.locator("#toast").inner_text()
            cap("10_nuevo_equipo")
            abrir_equipo("TK-301")
            pg.locator('.chip[data-id="CML-301-03"]').click()
            pg.fill('#form_med input[name="espesor"]', "5.70")
            pg.press('#form_med input[name="espesor"]', "Enter")
            pg.wait_for_timeout(800)
            assert "agregada" in pg.locator("#toast").inner_text().lower(), "Enter no envió el formulario"
        paso("Crear equipo nuevo y enviar formulario con Enter", nuevo_equipo)

        def import_malicioso():
            ruta = salida / "malicioso.json"
            ruta.write_text('{"equipos":[{"id":"X","tag":"<img src=x onerror=alert(1)>","familia":"tuberia","material":"A106-B",'
                            '"t_nom_mm":5,"fecha_servicio":"2020-01-01","imagen":"javascript:alert(1)",'
                            '"diseno":{"P_diseno_MPa":1,"T_diseno_C":50,"D_ext_mm":100,"E":1}}]}', encoding="utf8")
            pg.set_input_files('input[data-act="importar"]', str(ruta))
            pg.wait_for_timeout(1000)
            assert "rechazado" in pg.locator("#toast").inner_text().lower(), pg.locator("#toast").inner_text()
        paso("Rechazar proyecto importado con contenido inseguro", import_malicioso)

        def teclado():
            ir("equipos")
            pg.locator('.eq-item[data-id="V-201"]').focus()
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(500)
            assert "V-201" in pg.locator(".cabecera h1").inner_text()
        paso("Navegación con teclado", teclado)

        def visibilidad():
            ir("equipos")
            pg.locator('.nodo-area:has-text("Área 300") input.vis').click()
            pg.wait_for_timeout(600)
            assert pg.locator(".eq-fila.oculto").count() == 1, "TK-301 debía quedar oculto"
            ir("planta")
            assert pg.locator("#tabla-cml tr.click").count() == 7, "Planta debía excluir el equipo oculto"
            assert pg.locator(".oculto-chip").count() == 1
            ir("inicio")
            assert "TK-301" not in pg.locator(".familias").inner_text()
            ir("equipos")
            pg.locator('.nodo-area:has-text("Alquilación") [data-act="plegar"]').click()
            pg.wait_for_timeout(300)
            assert not pg.locator('.eq-item[data-id="V-201"]').is_visible(), "el área no se plegó"
            pg.locator('.nodo-area:has-text("Alquilación") [data-act="plegar"]').click()
            pg.wait_for_timeout(300)
            pg.locator('[data-act="mostrar_todos"]').first.click()
            pg.wait_for_timeout(500)
            assert pg.locator(".eq-fila.oculto").count() == 0
        paso("Lista de Equipos plegable con casillas para ocultar equipos en toda la app", visibilidad)

        def arrastrar_cml():
            menu("restablecer")
            pg.wait_for_timeout(1500)
            abrir_equipo("V-201")
            antes = pg.locator(".chip").count()
            tok = pg.locator(".cml-token").bounding_box()
            img = pg.locator(".esquema img").bounding_box()
            pg.mouse.move(tok["x"] + tok["width"] / 2, tok["y"] + tok["height"] / 2)
            pg.mouse.down()
            destino = (img["x"] + img["width"] * .5, img["y"] + img["height"] * .45)   # virola 2
            pg.mouse.move(destino[0] - 40, destino[1] - 40, steps=8)
            pg.mouse.move(*destino, steps=8)
            expect(pg.locator(".zona-luz")).to_be_visible()
            assert "Virola 2" in pg.locator(".zona-luz").inner_text(), pg.locator(".zona-luz").inner_text()
            cap("02b_arrastre_cml")
            pg.mouse.up()
            pg.wait_for_timeout(700)
            expect(pg.locator(".modal")).to_be_visible()
            assert pg.locator('#form_cml input[name="id"]').input_value() == "CML-201-04"
            assert pg.locator('#form_cml input[name="componente"]').input_value() == "Envolvente - virola 2"
            cap("02c_modal_cml")
            pg.locator('.modal [data-act="add_cml"]').click()
            pg.wait_for_timeout(800)
            assert pg.locator(".modal").count() == 0 and pg.locator(".chip").count() == antes + 1, "el CML no se agregó"
            pg.locator('.cml-token').focus()
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(500)
            expect(pg.locator(".modal")).to_be_visible()
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(400)
            assert pg.locator(".modal").count() == 0, "Escape no cerró la ventana"
        paso("Agregar CML arrastrando el ícono al esquema (zona iluminada y sugerencias)", arrastrar_cml)

        def buscador():
            ir("equipos")
            pg.fill('input[data-act="buscar_eq"]', "tanque")
            pg.wait_for_timeout(400)
            assert pg.locator("#sidebar .eq-item:not([hidden])").count() == 1, "el buscador no filtró"
            pg.fill('input[data-act="buscar_eq"]', "zzz")
            pg.wait_for_timeout(300)
            assert pg.locator("#sidebar .sin-res").is_visible(), "falta el aviso sin resultados"
            pg.fill('input[data-act="buscar_eq"]', "")
            pg.wait_for_timeout(300)
            assert pg.locator("#sidebar .eq-item:not([hidden])").count() >= 3
        paso("Buscador de equipos en la barra lateral", buscador)

        def nuevo_recipiente():
            ir("equipos")
            pg.locator('[data-act="nuevo_eq"]').click()
            pg.wait_for_timeout(400)
            pg.locator('[data-act="nuevo_fam"][data-familia="recipiente"]').click()
            pg.wait_for_timeout(400)
            assert pg.locator('#form_eq input[name="tag"]').input_value() == "V-202", "falta el TAG sugerido"
            assert "VIII-1" in pg.locator('#form_eq input[name="codigo_diseno"]').input_value()
            pg.fill('#form_eq input[name="t_nom_mm"]', "12")
            pg.fill('#form_eq input[name="area"]', "Área 100 - Alquilación")
            pg.locator('[data-act="guardar_eq"]').click()
            pg.wait_for_timeout(800)
            assert pg.locator('.eq-item[data-id="V-202"]').count() == 1, pg.locator("#toast").inner_text()
            ir("equipos")
            pg.locator('[data-act="nuevo_eq"]').click()
            pg.wait_for_timeout(300)
            pg.locator('[data-act="nuevo_fam"][data-familia="tuberia"]').click()
            pg.wait_for_timeout(300)
            pg.select_option('select[data-act="preset_nps"]', "219.1|8.18")
            assert pg.locator('#form_eq input[name="t_nom_mm"]').input_value() == "8.18"
            assert pg.locator('#form_eq input[name="d_D_ext_mm"]').input_value() == "219.1"
            pg.locator('[data-act="cancelar_eq"]').click()
            pg.wait_for_timeout(300)
        paso("Nuevo equipo con familia y campos predefinidos (TAG, códigos, NPS/cédula)", nuevo_recipiente)

        def rbi_tuberia():
            ir("rbi")
            pg.select_option('select[data-act="sel_rbi"]', "L-101")
            pg.wait_for_timeout(500)
            pg.locator('[data-act="crear_rbi"]').click()
            pg.wait_for_timeout(800)
            assert "Tubería" in pg.locator(".cabecera .desc").inner_text()
            assert pg.locator(".stat").count() >= 5, "faltan los resultados del RBI de la tubería"
            menu("restablecer")
            pg.wait_for_timeout(1500)
        paso("Riesgo (RBI) también para tuberías y tanques, con selector de equipo", rbi_tuberia)

        def rbi_planta():
            import copy as _c
            import json as _j
            demo = _j.loads((RAIZ / "data" / "demo.json").read_text(encoding="utf8"))
            v2 = _c.deepcopy(demo["equipos"][1])
            v2["id"] = v2["tag"] = "V-202"
            v2.pop("rbi")
            demo["equipos"].append(v2)
            ruta = salida / "dos_recipientes.json"
            ruta.write_text(_j.dumps(demo), encoding="utf8")
            pg.set_input_files('input[data-act="importar"]', str(ruta))
            pg.wait_for_timeout(1500)
            ir("rbi")
            pg.select_option('select[data-act="sel_rbi"]', "V-202")
            pg.wait_for_timeout(500)
            pg.locator('[data-act="crear_rbi"]').click()
            pg.wait_for_timeout(800)
            assert pg.locator(".m-chip").count() == 2, "la matriz de planta no muestra los 2 equipos"
            assert "#/rbi/V-202" in pg.url, pg.url
            cap("05b_rbi_planta")
            menu("restablecer")
            pg.wait_for_timeout(1500)
        paso("RBI de otro recipiente y matriz de riesgo de la planta", rbi_planta)

        def movil():
            pg.set_viewport_size({"width": 390, "height": 844})
            ir("inicio")
            cap("11_movil_inicio")
            ir("planta")
            cap("12_movil_planta")
        paso("Vista móvil", movil)
        nav.close()

    errores = [e for e in errores if "favicon" not in e.lower()]
    print(f"\nErrores de consola: {len(errores)}")
    for e in errores[:20]:
        print("  -", e[:300])
    print(f"Fallas: {len(fallas)}")
    return 1 if (errores or fallas) else 0


if __name__ == "__main__":
    salida = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / ".venv" / "e2e"
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        sys.exit(recorrer(sys.argv[1], salida))
    with servidor() as url:
        sys.exit(recorrer(url, salida))
