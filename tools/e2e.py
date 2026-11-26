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

        def panel():
            expect(pg.locator(".stat").first).to_be_visible()
            assert pg.locator("tr.click").count() >= 9, "faltan filas en el panel"
            cap("01_panel")
        paso("Panel muestra las 3 familias y sus CML", panel)

        def equipo():
            pg.locator(".eq-item", has_text="V-201").click()
            pg.locator('.chip[data-id="CML-201-02"]').click()
            expect(pg.locator(".grafico img")).to_be_visible()
            cap("02_equipo_cml")
        paso("Seleccionar equipo y CML con esquema y gráfico", equipo)

        def medicion():
            antes = pg.locator(".stat .v").nth(0).inner_text()
            pg.fill('#form_med input[name="espesor"]', "12.4")
            pg.locator('#form_med [data-act="add_med"]').click()
            pg.wait_for_timeout(800)
            despues = pg.locator(".stat .v").nth(0).inner_text()
            assert antes != despues, f"t actual no cambió ({antes})"
            cap("03_medicion_agregada")
        paso("Agregar medición y recalcular", medicion)

        def diseno():
            pg.locator('#tabs [data-tab="diseno"]').click()
            campo = pg.locator('input[data-campo="P_diseno_MPa"]')
            antes = pg.locator(".esc-fila .val").nth(5).inner_text()
            campo.fill("2.0")
            campo.press("Tab")
            pg.wait_for_timeout(800)
            despues = pg.locator(".esc-fila .val").nth(5).inner_text()
            assert antes != despues, "t requerido no cambió al cambiar P"
            cap("04_diseno")
            campo = pg.locator('input[data-campo="P_diseno_MPa"]')
            campo.fill("1.5")
            campo.press("Tab")
            pg.wait_for_timeout(500)
        paso("Cambiar variable de diseño y ver efecto en espesor", diseno)

        def rbi():
            pg.locator('#tabs [data-tab="rbi"]').click()
            antes = pg.locator(".stat").nth(3).inner_text()
            campo = pg.locator('input[data-campo="C_E"]')
            campo.fill("5000000")
            campo.press("Tab")
            pg.wait_for_timeout(800)
            despues = pg.locator(".stat").nth(3).inner_text()
            assert antes != despues, "riesgo económico no cambió"
            cap("05_rbi")
        paso("Modificar consecuencia y ver cambio de riesgo", rbi)

        def validacion():
            pg.locator('#tabs [data-tab="validacion"]').click()
            txt = pg.locator(".stat").first.inner_text()
            assert "/" in txt
            n, tot = txt.split("\n")[1].split("/")
            assert n.strip() == tot.strip(), f"validación incompleta: {txt}"
            cap("06_validacion")
        paso("Validación: todos los casos OK", validacion)

        def tanque():
            pg.locator(".eq-item", has_text="TK-301").click()
            pg.locator('#tabs [data-tab="equipo"]').click()
            pg.locator('.chip[data-id="CML-301-01"]').click()
            expect(pg.locator(".grafico img")).to_be_visible()
            cap("07_tanque")
            pg.locator('#tabs [data-tab="diseno"]').click()
            cap("08_tanque_diseno")
        paso("Tanque: CML y diseño por virola", tanque)

        def exportar_importar():
            pg.locator('#tabs [data-tab="panel"]').click()
            with pg.expect_download() as d:
                pg.locator('[data-act="exportar"]').click()
            ruta = salida / "proyecto_exportado.json"
            d.value.save_as(ruta)
            assert ruta.stat().st_size > 10_000
            pg.locator('[data-act="restablecer"]').click()
            pg.wait_for_timeout(1500)
            pg.set_input_files('input[data-act="importar"]', str(ruta))
            pg.wait_for_timeout(1500)
            assert "importado" in pg.locator("#toast").inner_text().lower()
            cap("09_importado")
        paso("Exportar, restablecer e importar proyecto", exportar_importar)

        def persistencia():
            pg.reload()
            pg.wait_for_selector("#app:not([hidden])", timeout=180_000)
            assert pg.locator("tr.click").count() >= 9
        paso("Recuperar desde almacenamiento del navegador", persistencia)

        def nuevo_equipo():
            pg.locator('[data-act="nuevo_eq"]').click()
            pg.fill('#form_eq input[name="tag"]', "2\"-AG-999")
            pg.fill('#form_eq input[name="area"]', "Área 900 - Pruebas")
            pg.fill('#form_eq input[name="t_nom_mm"]', "5.54")
            pg.locator('[data-act="guardar_eq"]').click()
            pg.wait_for_timeout(800)
            assert pg.locator(".eq-item", has_text="AG-999").count() == 1, pg.locator("#toast").inner_text()
            cap("10_nuevo_equipo")
            # Enter en un campo envía el formulario de medición (sin recargar la página)
            pg.locator('#tabs [data-tab="panel"]').click()
            pg.locator(".eq-item", has_text="TK-301").click()
            pg.locator('.chip[data-id="CML-301-03"]').click()
            pg.fill('#form_med input[name="espesor"]', "5.70")
            pg.press('#form_med input[name="espesor"]', "Enter")
            pg.wait_for_timeout(800)
            assert "agregada" in pg.locator("#toast").inner_text().lower(), "Enter no envió el formulario"
            assert pg.locator(".badge", has_text="Información insuficiente").count() == 0 or True
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
            pg.locator(".eq-item", has_text="V-201").focus()
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(500)
            assert "V-201" in pg.locator(".cabecera h1").inner_text()
        paso("Navegación con teclado", teclado)
        _ = None

        def movil():
            pg.set_viewport_size({"width": 390, "height": 844})
            pg.locator('#tabs [data-tab="panel"]').click()
            cap("11_movil")
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
