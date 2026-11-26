# Hallazgos: evaluación de la app vs. rúbrica

**Proyecto:** Aplicación web para la gestión e inspección de equipos estáticos (MAN040-B)
**App:** https://matiasgodoys1512.github.io/Trabajoestaticos/
**Fecha de revisión:** 26-11-2026
**Método:** pruebas en vivo en el navegador y verificación manual de cálculos contra el enunciado (§3 a §10)

> Resultado general: **cumple todas las funciones mínimas**. Lo que queda son temas de coherencia y trazabilidad, que pesan en *Fundamento técnico (40 %)* y *Trazabilidad (10 %)*.

---

## 1. Correcciones pendientes

Ordenadas por impacto en la nota. Marca `[x]` al corregir.

### Prioridad alta

- [x] **H1. Faltan las ediciones de API 510, API 570 y API 653**
  - **Dónde:** pestaña *Alcance* → Referencias normativas; *Diseño/Equipo* de TK-301 (aparece literal "(edición a declarar)" en t_min API 653 §4.3.3.1 y en el intervalo API 653 §6.3.3.2); ficha del equipo ("API 653" sin año).
  - **Por qué:** el §10 exige identificar la edición y las secciones usadas.
  - **Corrección:** declarar el año y la edición de cada norma y reemplazar todos los textos "(edición a declarar)".
  - ✅ **Resuelto: ediciones declaradas en un solo lugar (`py/calc/normas.py`): API 510 10ª ed. (2014), API 570 4ª ed. (2016), API 653 5ª ed. (2014), API 574 4ª ed. (2016). Ya no aparece "(edición a declarar)"; ficha y Alcance muestran la edición. Intervalo API 510 corregido a §6.5.1.1.**

- [x] **H2. Los CML del tanque citan la norma equivocada para CR y RL**
  - **Dónde:** *Equipo* → TK-301 → cualquier CML → *Ver cálculos* → CR largo plazo, CR corto plazo y Vida remanente.
  - **Actual:** "API 570 / API 510 §7.1.1".
  - **Corrección:** que la referencia dependa de la familia; para tanques, citar API 653 (sección correspondiente a la evaluación de corrosión del manto).
  - ✅ **Resuelto: la referencia de CR y RL depende de la familia (tanque → API 653 §6.3.3.2 RCA/N; tubería → API 570 §7.1.1; recipiente → API 510 §7.1.1).**

- [x] **H3. La pestaña Diseño toma el primer CML en vez del gobernante**
  - **Dónde:** pestaña *Diseño* → "Espesores de evaluación" (tubería y recipiente).
  - **Evidencia:**
    - V-201: "Medido (último)" = 15,00 mm (CML-201-01), pero CML-201-03 está en 9,50 mm, **bajo el mínimo**.
    - 8"-HF-101: "Medido (último)" = 7,76 mm (CML-101-01); "Alerta" = 2,90 mm, mientras que en el CML-101-02 la alerta es 4,49 mm.
  - **Corrección (elegir una):**
    - usar el CML gobernante (menor espesor o menor RL) y nombrarlo; o
    - mostrar los espesores por CML, como ya se hace en el tanque.
  - ✅ **Resuelto: Diseño usa el CML gobernante (peor condición, luego menor RL), lo nombra en el título y agrega la tabla "Espesores por CML".**

- [x] **H4. En la tubería, la ecuación mostrada no corresponde al resultado del "Mínimo en servicio"**
  - **Dónde:** *Diseño* → 8"-HF-101 → Ver cálculos → Mínimo en servicio.
  - **Actual:** muestra la ecuación de presión B31.3 (3a), que da 0,816 mm, pero el resultado es 2,800 mm (espesor estructural).
  - **Corrección:** mostrar `t_min = máx(t_presión; t_estructural)` con ambos valores y la referencia del estructural (API 574), igual que en la ficha del CML.
  - ✅ **Resuelto: "Mínimo en servicio" muestra t<sub>min</sub> = máx(t<sub>presión</sub>; t<sub>estructural</sub>) con ambos valores y la referencia API 574; la ecuación B31.3 queda como tarjeta aparte.**

### Prioridad media

- [x] **H5. La nota de tolerancia de fabricación es la misma en las tres familias**
  - **Dónde:** *Diseño* → "Definiciones de espesor" (V-201 y TK-301).
  - **Actual:** "tubo sin costura hasta −12,5 %" en todas las familias.
  - **Corrección:** texto propio por familia. Recipiente: tolerancia de plancha según ASME VIII-1 UG-16. Tanque: tolerancia de plancha según API 650. Tubería: −12,5 % (ASTM A106/A53).
  - ✅ **Resuelto: nota propia por familia (tubería −12,5 % ASTM A106/A53; recipiente UG-16(c): menor entre 0,3 mm y 6 %; tanque API 650 §4.2.1.2.3: 0,3 mm).**

- [x] **H6. El RBI usa por defecto un CML que no es el crítico**
  - **Dónde:** pestaña *RBI* → V-201 → "CML gobernante" = CML-201-02.
  - **Problema:** CML-201-03 está bajo el mínimo (9,50 < 9,67 mm) y es el más severo.
  - **Corrección:** dejar CML-201-03 por defecto, o justificar en la diapositiva por qué se eligió CML-201-02.
  - **Revisar también:** la CR de largo plazo del RBI (0,3313 mm/año) no coincide con la CR del panel para CML-201-02 (0,366). Confirmar qué dato y qué Δt usa (t_rdi = 16 mm, age desde 01-05-2016) y que sea coherente con API 581 §4.5.2.
  - ✅ **Resuelto: el RBI parte en CML-201-03. La tabla del cálculo muestra la CR de largo plazo usada en D<sub>f</sub> (API 581 §4.5.2) y, al lado, la CR adoptada del panel (máx. LP/CP), lo que explica la diferencia 0,331 vs 0,366.**

- [x] **H7. Un CML bajo el mínimo muestra una fecha pasada como "Próxima"**
  - **Dónde:** *Panel* → CML-201-03 → Próxima = 21-05-2025.
  - **Corrección:** cuando t < t_min, mostrar "Inmediata / evaluar (FFS, reparación o reemplazo)" en lugar de una fecha.
  - ✅ **Resuelto: un CML bajo el mínimo muestra "Inmediata" (evaluación FFS API 579-1, reparación o reemplazo) en el panel y en el indicador.**

### Prioridad baja (preparar para la defensa)

- [x] **H8. En la tubería, la próxima inspección coincide con la llegada a t_min**
  - **Dónde:** CML-101-02: RL = 1,3 años e intervalo = 1,3 años (06-02-2027), justo cuando la proyección cruza t_min.
  - **Nota:** es válido según API 570 ("RL < 4 años → hasta RL completa, máx. 2 años"), pero el profesor puede preguntarlo. Preparar la justificación u ofrecer un criterio más conservador (p. ej. RL/2).
  - ✅ **Preparado: el criterio ahora dice "RL < 4 años: mín(RL; 2 años), la norma permite hasta la RL completa". Justificación para la defensa: es lo que permite API 570/510; el plazo de alerta (CR·2 años) ya avisa antes.**

- [x] **H9. Agregar el enlace al repositorio de GitHub en la app** (opcional, facilita la revisión).
  - ✅ **Resuelto: enlace al repositorio en la pestaña Alcance.**

- [x] **H10. Verificar que el JSON exportado incluya los adjuntos subidos por el usuario**
  - **Por qué:** el §6 exige que el respaldo conserve los adjuntos o permita restablecerlos.
  - **Prueba:** subir un PNG y un PDF a un equipo, *Exportar*, *Restablecer demo*, *Importar* y comprobar que reaparecen.
  - ✅ **Verificado con prueba automática en navegador: se sube PNG y PDF, se exporta, se restablece y al importar reaparecen ambos.**

---

## 2. Lo que ya cumple (no tocar)

| § | Requisito | Evidencia |
|---|---|---|
| 3 | Publicada en GitHub Pages con Python | PyScript 2025.11.1 + `py/app.py` |
| 3 | 3 familias, ≥3 CML, ≥3 campañas, esquema por familia | 8"-HF-101, V-201, TK-301 con isométrico/esquema |
| 4.1 | Registro y estructura de planta | Planta → Área → Sistema → Equipo → Componente (CML); crear/editar/eliminar; circuito y clase API 570 |
| 4.2 | Esfuerzos admisibles y espesores | S interpolado por temperatura (S(250 °C) = 19,2 ksi); rango −29 a 260 °C validado; nominal/compra/requerido/mínimo/medido/alerta |
| 4.2 | Ecuaciones verificadas a mano | UG-27 = 9,672 mm ✔ · API 650 td = 7,114 / 8,614 mm ✔ · API 653 t_min = 5,978 mm ✔ · B31.3 (3a) con P = 5 MPa = 3,92 mm ✔ |
| 4.3 | Documentación y marcadores CML | Marcadores (x, y) % por condición; carga de PNG/JPG y PDF |
| 4.4 | Mediciones y corrosión | Medición de prueba 3,20 mm → CR LP 0,745, CR CP 0,636, RL 0,54 años ✔; gráfico t vs tiempo; rechaza fechas futuras; eventos de reemplazo/reparación/cambio de punto |
| 4.5 | Próxima inspección | API 570 (clase, RL < 4 años), API 510 (RL/2), API 653 (RCA/2N); alcance de tanques declarado (solo manto) |
| 4.5 | Estados | Normal, alerta, bajo el mínimo, vencida, insuficiente |
| 5 | RBI API 581 | D_f (ec. 2.12–2.20) separado de P_f; C_A [m²] y C_E [USD] con base de valoración; R_A y R_E por separado; matriz 5×5; prioridad; efecto de la inspección explicado |
| 5 | Cambio de consecuencia en vivo | C_E = 20 MM USD → categoría E, Prioridad 1 ✔ |
| 6 | Panel y filtros | Filtros por área, familia y condición |
| 6 | Conservación de datos | Autoguardado en localStorage (persiste al recargar), exportar/importar JSON, CSV, restablecer demo |
| 6 | Validación independiente | 14/14 casos OK (tolerancia 0,5 %), por familia + RBI; casos de las 5 condiciones |
| 7 | Herramientas e IA declaradas | Pestaña Alcance |

---

## 3. No evaluable desde la app (revisar en la presentación)

- [ ] Diapositivas con los 3 a 5 integrantes identificados.
- [ ] Enlaces a la app publicada y al repositorio de GitHub.
- [ ] Fundamentos, fuentes con edición, validaciones y limitaciones.
- [ ] Uso de IA: herramientas, tareas apoyadas y comprobaciones realizadas.
- [ ] Guion de demo (§8): 3 familias → ubicación y esquema → nueva medición → cambio de variable de diseño → cambio de consecuencia RBI → guardar/recuperar + validación.
- [ ] Ejecución local probada como respaldo.
- [ ] Reparto de la exposición: 3 min fundamentos / 9 min demo / 3 min validación.
