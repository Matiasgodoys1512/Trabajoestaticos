# Mejoras propuestas: app de gestión de integridad (Trabajoestaticos)

**App:** https://matiasgodoys1512.github.io/Trabajoestaticos/
**Fecha:** 26-11-2026
**Origen:** revisión de la app publicada (versión con navegación Inicio / Planta / Equipos / Riesgo (RBI) / Validación / Acerca).

> **Forma de trabajo:** esta es una lista de propuestas. Antes de aplicar cualquier cambio, revisarla y decidir en grupo qué entra. Marcar `[x]` al terminar cada una.

**Prioridad sugerida**

- **Antes de la presentación:** U1, U2, U4 y F1 (baratas y atacan directo lo que se evalúa).
- **Si queda tiempo:** F2 (quita riesgo a la demo).
- **Después de la evaluación:** el resto.

## Análisis y decisiones (26-11-2026)

Cada propuesta se evaluó contra el enunciado, la arquitectura de la app y las buenas prácticas de UX. Resultado: **12 aplicadas (3 adaptadas), I6 verificada sin cambios, I1–I5 postergadas.** Verificación: 40 pruebas pytest y 20 pasos E2E en navegador real, sin errores.

| # | Decisión | Qué se hizo y por qué |
|---|---|---|
| U1 | Aplicada | Números grandes con separador de miles (`125.823 USD/año`). Los valores muy pequeños usan el mismo formato que P<sub>f</sub> (`3,53·10⁻⁴`) en vez de `3,53e-04`. R<sub>E</sub> < 100 se muestra con 2 decimales. |
| U2 | Adaptada | En vez de un aviso que desaparece en 3 s, un recuadro **«Último cambio»** que queda visible en la vista hasta salir de ella (se puede explicar con calma en la demo). Diseño: valor, t<sub>min</sub> del CML gobernante, cambio de CML gobernante, condición y próxima inspección. RBI: valor, D<sub>f</sub>, R<sub>A</sub>, R<sub>E</sub> y prioridad. |
| U3 | Aplicada | Referencia = **caso demo** (por ID de equipo). Se descartó «último guardado» porque el autoguardado lo actualiza a cada cambio y la marca nunca se vería. Campo editado en ámbar + botón «↺». |
| U4 | Aplicada | Ícono «?» con definición y referencia, visible al pasar el mouse **o con el teclado** (un `title` simple no funciona con teclado ni en pantallas táctiles). CML (6 tarjetas), RBI (5) y escalera de espesores (6). |
| U5 | Aplicada | CML y equipo en una sola columna (una columna menos) y columnas CML y Condición **fijas** al desplazar de lado. A 1024 px la tabla se ve completa. |
| U6 | Adaptada | El **TAG sigue siendo el texto principal**: es el identificador único que se usa en OT y en terreno. Ahora se parte en dos líneas sin cortarse y debajo aparece la familia y la descripción en gris. Se descartó el campo `nombre_corto` (otro dato que mantener). |
| F1 | Aplicada | Caso verificado con un **cálculo independiente** (script aparte con `math.erf`, sin usar el código de la app): D<sub>f</sub> = 205,593, R<sub>A</sub> = 0,75494 m²/año, R<sub>E</sub> = 2.831,02 USD/año. Coincide con el documento; el 205,61 aparece solo si se redondean S, YS y TS en MPa. Validación 17/17 y prueba en pytest. |
| F2 | Aplicada | «Evaluado al» en la barra superior, guardado en el proyecto (`fecha_evaluacion`); el demo queda fijo al 26-11-2026. La evaluación es «al día»: las mediciones posteriores a la fecha no se consideran (y se avisa). El RBI usa la misma fecha: se quitó su fecha propia para no tener dos fuentes de verdad. La «fecha futura» de una medición se sigue juzgando con la fecha real (es un error de dato, no de escenario). |
| F3 | Aplicada | Tarjeta **«Calidad de datos»** en Planta: avisos clasificados por tipo, con enlace al CML y respetando los filtros. Se descartó mezclarlos con el filtro de condición: condición y calidad de datos son conceptos distintos y mezclarlos alteraría los totales. |
| F4 | Aplicada | Selector de recipiente, creación con valores por defecto **explícitos** («ajustar al escenario»), enlace directo `#/rbi/<equipo>`, matriz de la planta con un punto por equipo y ranking por riesgo (visible con ≥ 2 equipos evaluados). Eje de consecuencia = la mayor categoría, coherente con el nivel = el peor. |
| F5 | Aplicada | Nueva pestaña **Plan** (no dentro de Planta: responde *cuándo* inspeccionar, no *qué tan grave* está). Grupos: acción inmediata, vencidas, por mes y sin fecha. Exporta CSV. |
| F6 | Aplicada | Botón **«Imprimir ficha»**: abre todos los plegables, oculta navegación, formularios y botones, y agrega encabezado y resumen de CML. V-201 ocupa 3 hojas A4 con todos los cálculos; se priorizó conservar ecuaciones y referencias sobre el límite de 2 hojas. |
| I1–I5 | Postergadas | Fuera del alcance de la entrega y sin aporte directo a la rúbrica. I2 (importar sin reemplazar) requiere resolver conflictos de ID; I3 requiere paginar el árbol. |
| I6 | Verificada | A106 B y A53 B coinciden con ASME B31.3-2018 Tabla A-1: 20,0 / 20,0 / 20,0 / 19,9 / 19,0 ksi a 100–500 °F. Sin cambios. |

Las rutas de código son las que usa la app (`py/app.py`, `py/ui.py`, `py/proyecto.py`, `py/calc/*.py`). Donde dice "probablemente", hay que confirmar la ubicación exacta en el código.

---

## 1. Arreglos rápidos de UX/UI

### [x] U1. Formato de números grandes · Esfuerzo: bajo

- **Problema:** con C_E = 20 000 000 USD, la tarjeta de R_E muestra `1,26e+05 USD/año`. En plena demo parece un error.
- **Causa probable:** la función de formato `f(x, n, unidad)` en `py/ui.py` cambia a notación científica cuando `abs(x) >= 1e5`.
- **Propuesta:** para valores monetarios y de riesgo, usar separador de miles en vez de notación científica (`125.820 USD/año`). Mantener la notación científica solo para frecuencias pequeñas como P_f (`6,29·10⁻³`), que ya se ve bien.
- **Criterio de aceptación:** con C_E = 20 000 000, la tarjeta muestra `125.820 USD/año` y el desarrollo del cálculo muestra `125.820,xx`.

### [x] U2. Mostrar "antes → después" al cambiar una variable · Esfuerzo: bajo-medio

- **Problema:** los pasos 4 y 5 del §8 piden *mostrar el efecto* de un cambio de diseño o de consecuencia. Hoy la app recalcula, pero hay que recordar el valor anterior para notar la diferencia.
- **Propuesta:** al confirmar un cambio (Enter o Tab), mostrar un aviso con lo que cambió. Por ejemplo:
  - `P diseño 1,03 → 5,00 MPa · t_min 2,80 → 3,92 mm · CML gobernante: CML-101-04 → CML-101-02 (Bajo el mínimo)`
  - `C_E 450.000 → 20.000.000 USD · R_E 2.831 → 125.820 USD/año · Prioridad 2 → 1`
- **Dónde:** el manejador de cambios (`accion_change` / `cambio()` en `py/app.py`). Guardar una copia de los resultados antes de recalcular y comparar después.
- **Criterio de aceptación:** cada cambio en *Diseño y espesores* o en *Riesgo (RBI)* muestra un aviso con al menos el valor modificado, el t_min o riesgo resultante y cualquier cambio de condición o prioridad.

### [x] U3. Marcar campos editados y permitir volver al original · Esfuerzo: bajo

- **Problema:** en *Diseño y espesores* y *Riesgo (RBI)* el cambio se aplica sin pista visual. Para deshacerlo hay que recordar el valor.
- **Propuesta:** resaltar el campo modificado (borde o fondo de color) y agregar un ícono "↺" para volver al valor del caso demo o del último guardado.
- **Criterio de aceptación:** después de cambiar P de 1,03 a 5 MPa, el campo queda resaltado; al presionar "↺" vuelve a 1,03 y todo se recalcula.

### [x] U4. Explicación al pasar el mouse (tooltips) · Esfuerzo: bajo

- **Problema:** términos como t_min, t alerta, CR, RL, D_f, P_f, POF, C_A y C_E no se explican en pantalla.
- **Propuesta:** un ícono "?" o un `title` en cada etiqueta, con una definición de una línea y su referencia. Ejemplos:
  - **t alerta:** "t_min + CR · 2 años: margen para gestionar OT, repuestos y parada (criterio del grupo)".
  - **D_f:** "Factor de daño: multiplica la frecuencia genérica de falla. No es una probabilidad (API 581)".
  - **POF:** "Categoría de probabilidad de falla, 1 a 5 (API 581 Parte 1, Tabla 4.1M)".
- **Criterio de aceptación:** todas las tarjetas de resultados del CML y del RBI tienen su explicación.

### [x] U5. Tabla de Planta en pantallas angostas · Esfuerzo: bajo

- **Problema:** en una ventana angosta (por ejemplo, un proyector en baja resolución) la tabla de CML se sale de la pantalla y hay que desplazarse de lado. Justo las columnas *Próxima* y *Condición*, que son las importantes, quedan fuera de la vista.
- **Propuesta:** fijar la columna CML y la de Condición (`position: sticky`), o pasar a un formato de tarjetas bajo cierto ancho.
- **Criterio de aceptación:** con 1024 px de ancho se ven el CML, la próxima fecha y la condición sin desplazarse de lado.

### [x] U6. TAG largo en el árbol de equipos · Esfuerzo: bajo

- **Problema:** con los códigos anonimizados de la base UT (`PD02-910-TLK-448386-3367`) el árbol es difícil de leer.
- **Propuesta:** mostrar la descripción corta como texto principal ("Red ácido sulfúrico") y el TAG en gris debajo. Opcional: un campo `nombre_corto` en el JSON.
- **Criterio de aceptación:** con el proyecto `proyecto_planta_celulosa_demo.json` importado, el árbol se lee sin cortes.

---

## 2. Funcionalidades que suman frente a la rúbrica

### [x] F1. Caso de validación del RBI con CML-201-03 · Esfuerzo: bajo · **Prioridad alta**

- **Problema:** desde que el RBI usa CML-201-03 por defecto, la demo muestra D_f = 205,6, pero el caso de *Validación* "D_f adelgazamiento" usa el escenario antiguo (CR 0,3656 mm/año, D_f = 16,03). El resultado que se muestra no tiene respaldo independiente.
- **Propuesta:** agregar un caso con los datos de CML-201-03:

  | Entrada | Valor |
  |---|---|
  | CR largo plazo | 0,7179 mm/año |
  | age | 10,57 años (01-05-2016 → 26-11-2026) |
  | t_rdi | 16,00 mm |
  | t_min | 9,672 mm |
  | Material | SA-516-70, E = 0,85 |
  | Confianza / inspecciones | media / 2 tipo B |
  | **Esperado** | **D_f = 205,59 · P_f = 6,29·10⁻³ /año · R_A = 0,7549 m²/año (C_A = 120 m²) · R_E = 2.831 USD/año (C_E = 450.000 USD)** |

- **Dónde:** la lista de casos de la vista Validación (probablemente en `py/ui.py`) y, si existe, el test equivalente en pytest.
- **Ojo con age:** depende de la fecha de evaluación. Para que el caso sea estable conviene fijarla (ver F2) o usar una fecha explícita en el caso.
- **Criterio de aceptación:** Validación muestra 15/15 OK, y el nuevo caso coincide con lo que se ve en *Riesgo (RBI)*.

### [x] F2. Fecha de evaluación global · Esfuerzo: medio

- **Problema:** condición, próxima inspección y RBI se calculan con la fecha del computador (`date.today()`), y la nueva medición también toma hoy por defecto. Los números de las diapositivas pueden no calzar el día de la presentación, y algunos puntos cambian de condición con el tiempo: CML-910-02 pasa a vencida el 30-03-2027 y CML-448-02 el 28-05-2027.
- **Propuesta:** un selector "Evaluar al día: [fecha]" (en el encabezado o en el menú Proyecto), guardado en el JSON del proyecto (por ejemplo `fecha_evaluacion`). Por defecto, hoy.
- **Dónde:** `evaluar_todo(data, hoy)` en `py/ui.py` ya recibe `hoy`; falta pasarle la fecha elegida. Revisar también `serie_comparable` en `py/calc/corrosion.py`, que usa `date.today()` para detectar fechas futuras, y la fecha de evaluación del RBI.
- **Uso en la demo:** adelantar la fecha y mostrar en vivo cómo un punto en alerta pasa a *Inspección vencida*.
- **Criterio de aceptación:** con la fecha fija en 26-11-2026, todos los valores esperados de la guía calzan, cualquiera sea el día real.

### [x] F3. Panel de calidad de datos · Esfuerzo: medio

- **Problema:** el §4.4 pide *reconocer* datos insuficientes, fechas inconsistentes, velocidades nulas o negativas y cambios de punto, reparaciones y reemplazos. La app los detecta, pero cada aviso está escondido dentro de su CML. El filtro "Error de datos" de Planta solo se activa cuando un equipo entero falla con una excepción, no con estos avisos.
- **Propuesta:** una sección (en Planta o como pestaña propia) que liste todos los avisos: equipo, CML, tipo de aviso y enlace al CML. Opcional: que el filtro "Error de datos" incluya los CML con avisos.
- **Datos:** `velocidades()` ya devuelve `problemas` por CML; solo hay que reunirlos.
- **Criterio de aceptación:** con el proyecto combinado importado, el panel lista los avisos de CML-101-03, CML-301-03, CML-910-03, CML-910-04, CML-638-03 y CML-638-04.

### [x] F4. RBI para cualquier equipo y matriz de riesgo de la planta · Esfuerzo: medio-alto

- **Problema:** `eq_rbi()` en `py/app.py` toma solo el **primer** equipo que tenga la clave `rbi`. No se puede evaluar otro equipo ni comparar riesgos entre equipos, que es justamente para lo que sirve el RBI: priorizar.
- **Propuesta:**
  1. Un selector de equipo en *Riesgo (RBI)* (solo recipientes por ahora, que es la familia implementada). Al elegir un equipo sin datos RBI, ofrecer crearlos con valores por defecto.
  2. Una matriz 5×5 de la planta con un punto por equipo evaluado, coloreada por prioridad.
- **Ojo:** la validación del proyecto (`_rbi` en `py/proyecto.py`) ya acepta `rbi` en cualquier equipo; el límite está en la interfaz.
- **Criterio de aceptación:** se puede evaluar el desaireador del proyecto combinado y verlo junto a V-201 en la matriz de planta.

### [x] F5. Plan de inspección · Esfuerzo: medio

- **Propuesta:** una vista con las próximas inspecciones ordenadas por fecha y agrupadas por mes, con las vencidas y las "Inmediata" arriba. Opcional: exportarla a CSV.
- **Por qué:** convierte los cálculos en un plan accionable, que es lo que hace UltraPIPE.
- **Criterio de aceptación:** muestra los 21 CML del proyecto combinado con su fecha, tipo de inspección (medición de espesores) y criterio gobernante.

### [x] F6. Informe imprimible por equipo · Esfuerzo: medio

- **Propuesta:** un botón "Imprimir ficha" que abra una vista limpia (ficha técnica, esquema con marcadores, tabla de CML, gráfico y cálculos con referencias) preparada para imprimir a PDF desde el navegador (`@media print`).
- **Por qué:** respaldo en la defensa y evidencia de trazabilidad (10 %).
- **Criterio de aceptación:** al imprimir a PDF, la ficha de V-201 cabe en 1 o 2 páginas y conserva las ecuaciones y referencias.

---

## 3. Ideas para después de la evaluación

- [ ] **I1. Importar mediciones desde CSV o Excel**, con columnas TAG, CML, fecha, espesor, unidad, técnica, evento y observaciones. Permite cargar campañas completas; calza con la base UT anonimizada.
- [ ] **I2. Importar sin reemplazar**: hoy *Importar proyecto* borra el proyecto actual. Ofrecer "agregar equipos al proyecto" (avisando si hay IDs repetidos).
- [ ] **I3. Más de 200 equipos**: el límite está en `MAX_EQUIPOS` de `py/proyecto.py`. Para cargar la base completa habría que subirlo y revisar el rendimiento del árbol (paginación o carga diferida).
- [ ] **I4. Más componentes**: codos y reducciones en tuberías, cabezales en recipientes (UG-32) y fondo y techo de tanques. El enunciado los deja como ampliación opcional.
- [ ] **I5. Modo presentación**: un recorrido guiado que siga los 6 pasos del §8, con los valores esperados al lado.
- [x] **I6. Revisar la tabla de esfuerzos de A106 B / A53 B** en `py/calc/materiales.py` (19,9 ksi a 400 °F y 19,0 ksi a 500 °F) contra ASME B31.3 Tabla A-1 de la edición declarada.

---

## Resumen

| # | Mejora | Tipo | Esfuerzo | Cuándo |
|---|---|---|---|---|
| U1 | Formato de números grandes | UX/UI | Bajo | Antes de presentar |
| U2 | Antes → después al cambiar una variable | UX/UI | Bajo-medio | Antes de presentar |
| U3 | Marcar campos editados y volver al original | UX/UI | Bajo | Si queda tiempo |
| U4 | Tooltips con definiciones | UX/UI | Bajo | Antes de presentar |
| U5 | Tabla de Planta en pantallas angostas | UX/UI | Bajo | Si queda tiempo |
| U6 | TAG largo en el árbol | UX/UI | Bajo | Si queda tiempo |
| F1 | Validación del RBI con CML-201-03 | Funcionalidad | Bajo | **Antes de presentar** |
| F2 | Fecha de evaluación global | Funcionalidad | Medio | Si queda tiempo |
| F3 | Panel de calidad de datos | Funcionalidad | Medio | Después |
| F4 | RBI por equipo y matriz de planta | Funcionalidad | Medio-alto | Después |
| F5 | Plan de inspección | Funcionalidad | Medio | Después |
| F6 | Informe imprimible por equipo | Funcionalidad | Medio | Después |
| I1–I6 | Ideas a futuro | Varias | Varios | Después |
