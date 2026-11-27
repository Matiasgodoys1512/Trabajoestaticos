# Fundamentos técnicos del prototipo

Resumen de ecuaciones, valores y criterios usados por el motor de cálculo (`py/calc/`).
Unidades internas: **SI** (mm, MPa, °C, m, años). Conversión: 1 ksi = 6,894757 MPa; 1 in = 25,4 mm.

> ⚠️ = verificar contra el documento (no estaba en la carpeta de referencias o requiere confirmación del grupo).

## Ediciones declaradas

| Documento | Edición | Fuente usada |
|---|---|---|
| ASME B31.3 | 2018 | MD/PDF carpeta |
| ASME BPVC VIII Div. 1 | 2019 | MD/PDF carpeta |
| ASME BPVC II Parte D (Customary) | 2019 | PDF carpeta (Tabla 1A, p. 82–84) |
| API 650 | 12ª ed., 2013 | MD/PDF carpeta |
| API RP 580 | 3ª ed., 2016 | MD/PDF carpeta |
| API RP 581 | 3ª ed., 2016 + Add. 2 (2020) | MD/PDF carpeta |
| API 510 / 570 / 653 | ⚠️ edición a declarar | **No están en la carpeta**; criterios tomados de clases (ppt 05) y conocimiento general |

## Materiales (catálogo acotado, rango ≤ 260 °C / 500 °F)

| Familia | Material | S admisible | Fuente |
|---|---|---|---|
| Tubería | ASTM A106 Gr. B (sin costura, E = 1,0) | 20,0 ksi = 137,9 MPa (≤ 300 °F); 19,9 ksi a 400 °F; 19,0 ksi a 500 °F | B31.3 Tabla A-1 / A-1A |
| Tubería | ASTM A53 Gr. B (sin costura, E = 1,0) | Igual que A106 B | B31.3 Tabla A-1 |
| Recipiente | SA-516 Gr. 70 (SMYS 38 ksi, SMTS 70 ksi) | 20,0 ksi = 137,9 MPa (≤ 500 °F); 19,4 ksi a 600 °F | II-D Tabla 1A, línea 33 |
| Tanque | A283 Gr. C (Y = 205 MPa, T = 380 MPa) | Sd = 137 MPa; St = 154 MPa | API 650 Tabla 5.2a |
| Tanque | A36 (Y = 250 MPa, T = 400 MPa) | Sd = 160 MPa; St = 171 MPa | API 650 Tabla 5.2a |

## Espesores (definiciones usadas en la app)

- **t<sub>nom</sub>**: espesor nominal de compra/fabricación.
- **t<sub>calc</sub>**: espesor requerido por presión según el código de diseño.
- **t<sub>diseño</sub>** = t<sub>calc</sub> + CA (sobreespesor por corrosión). En tuberías se suma además la tolerancia de fabricación (−12,5 % para tubo sin costura): t<sub>compra</sub> ≥ t<sub>diseño</sub> / 0,875.
- **t<sub>min</sub> (servicio)**: espesor mínimo admisible en servicio = máx(t<sub>calc</sub>, t<sub>estructural</sub>). **No** incluye CA.
- **t<sub>alerta</sub>** = t<sub>min</sub> + CR · T<sub>int</sub>, donde T<sub>int</sub> es el plazo de intervención (por defecto 2 años): se alerta cuando el espesor queda a menos de lo que se perdería durante el plazo necesario para planificar una reparación o un reemplazo.
- **t<sub>medido</sub>**: lectura de UT en el CML.

### Tubería: ASME B31.3 §304.1.2, ec. (3a)
t = P·D / [2 (S·E·W + P·Y)], válida para t < D/6. Y = 0,4 (acero ferrítico ≤ 482 °C, Tabla 304.1.1); W = 1,0 (≤ 427 °C, Tabla 302.3.5).
t<sub>estructural</sub>: ingresado por el usuario (⚠️ API 574 da valores por defecto según el NPS).

### Recipiente: ASME VIII-1 UG-27(c)
- (c)(1) circunferencial: t₁ = P·R / (S·E − 0,6·P), válida para P ≤ 0,385·S·E.
- (c)(2) longitudinal: t₂ = P·R / (2·S·E + 0,4·P).
- t = máx(t₁; t₂), con R = radio interior. En cilindros gobierna normalmente (c)(1).

### Tanque: API 650 §5.6.3.2 (método de 1 pie) y API 653 §4.3.3.1 ⚠️
- Diseño: td = 4,9·D·(H − 0,3)·G / Sd + CA; prueba hidrostática: tt = 4,9·D·(H − 0,3) / St [mm; D, H en m].
- Espesor de diseño = máx(td; tt; mínimo nominal §5.6.1.1: 5 mm si D < 15 m, 6 mm hasta 36 m, 8 mm hasta 60 m, 10 mm sobre 60 m).
- Servicio (API 653): t<sub>min</sub> = 4,9·D·(H − 0,3)·G / (S·E), con S = mín(0,80·Y; 0,429·T) para las virolas 1 y 2, y S = mín(0,88·Y; 0,472·T) para las demás. t<sub>min</sub> ≥ 2,54 mm (0,1 in).
- H se mide desde el fondo de la virola evaluada hasta el nivel máximo de líquido.

## Corrosión y vida remanente (API 510 / 570, clase 05)
- CR<sub>LP</sub> = (t<sub>inicial</sub> − t<sub>actual</sub>) / Δt(inicial→actual)
- CR<sub>CP</sub> = (t<sub>previa</sub> − t<sub>actual</sub>) / Δt(previa→actual)
- CR adoptada = máx(CR<sub>LP</sub>, CR<sub>CP</sub>) (criterio conservador, ppt 05 lámina 11).
- RL = (t<sub>actual</sub> − t<sub>min</sub>) / CR

Condición (prioridad): **bajo el mínimo** (t<sub>actual</sub> < t<sub>min</sub>, aunque haya una sola lectura) > **información insuficiente** (sin CR: < 2 mediciones comparables) > **vencida** > **alerta** > **normal**.

Validaciones: menos de 2 mediciones comparables → "información insuficiente"; fechas duplicadas o desordenadas → error; CR ≤ 0 → se informa y no se calcula RL por esa vía; t<sub>actual</sub> < t<sub>min</sub> → "bajo el mínimo". Una medición marcada como **reemplazo/reparación/cambio de punto** reinicia la serie comparable.

## Próxima inspección (mediciones de espesor)
| Norma | Intervalo |
|---|---|
| API 510 §7.1.1 ⚠️ | mín(RL/2; 10 años). Si RL < 4 años: mín(RL; 2 años). CR ≤ 0: 10 años. Sin CR: programar 2ª medición. |
| API 570 §6.3.3 (ppt 05 lám. 13) | mín(RL/2; máximo de la tabla por clase: Clase 1 = 5, Clase 2 = 10, Clase 3 = 10 años). Si RL < 4: mín(RL; 2). CR ≤ 0 o sin CR: máximo de la clase. |
| API 653 §6.3.3.2 ⚠️ (UT externo del manto) | CR conocida: mín(RCA/(2·N) = RL/2; 15 años). CR desconocida: 5 años. CR ≤ 0: 15 años. Fuera de alcance: inspección interna y fondo (datos pendientes). |

Fecha próxima = fecha de la última medición + intervalo. Estado **vencida** si hoy > fecha próxima.

## RBI: API RP 581 Parte 2 §4 (adelgazamiento generalizado): tubería, recipiente y manto de tanque
1. Art = Cr·age<sub>tk</sub> / t<sub>rdi</sub> (sin cladding, ec. 2.12).
2. FS = (YS + TS)/2 · E · 1,1 (ec. 2.13).
3. SR<sub>P</sub> = S·E·máx(t<sub>min</sub>, t<sub>c</sub>) / (FS·t<sub>rdi</sub>) (ec. 2.14).
4. Prior (Tabla 4.5): baja 0,5/0,3/0,2; media 0,7/0,2/0,1; alta 0,8/0,15/0,05.
5. Condicional (Tabla 4.6) para E/D/C/B/A: Co1 = 0,33/0,4/0,5/0,7/0,9; Co2 = 0,33/0,33/0,3/0,2/0,09; Co3 = 0,33/0,27/0,2/0,1/0,01.
6. I<sub>i</sub> = Pr<sub>i</sub> · Π Co<sub>i</sub>^N; Po<sub>i</sub> = I<sub>i</sub> / ΣI (ec. 2.16–2.17, Bayes).
7. β<sub>i</sub> = (1 − DS<sub>i</sub>·Art − SR<sub>P</sub>) / √(DS<sub>i</sub>²·Art²·COV<sub>Δt</sub>² + (1 − DS<sub>i</sub>·Art)²·COV<sub>Sf</sub>² + SR<sub>P</sub>²·COV<sub>P</sub>²), con DS = 1, 2, 4; COV<sub>Δt</sub> = 0,20; COV<sub>Sf</sub> = 0,20; COV<sub>P</sub> = 0,05 (ec. 2.18).
8. D<sub>fB</sub> = Σ Po<sub>i</sub>·Φ(−β<sub>i</sub>) / 1,56·10⁻⁴ (ec. 2.19); D<sub>f</sub> = máx(D<sub>fB</sub>·F<sub>IP</sub>·F<sub>DL</sub> / F<sub>OM</sub>; 0,1) (ec. 2.20).
9. P<sub>f</sub>(t) = gff · F<sub>MS</sub> · D<sub>f</sub>, con gff total de la Parte 2, Tabla 3.1: PIPE y Vessel = 3,06·10⁻⁵; Tank650 COURSE-1-10 = 1,00·10⁻⁴ fallas/año; F<sub>MS</sub> = 10^(−0,02·pscore + 1) (ec. 2.10).
   S en SR<sub>P</sub>: tubería y recipiente a la T de diseño (B31.3 Tabla A-1 / II-D Tabla 1A); tanque, S<sub>d</sub> de API 650 Tabla 5.2a. El fondo del tanque (TANKBOTTOM, gff 7,2·10⁻⁴) no se evalúa.
10. R<sub>A</sub> = P<sub>f</sub> · C<sub>A</sub> [m²/año]; R<sub>E</sub> = P<sub>f</sub> · C<sub>E</sub> [USD/año]. Categorías: Parte 1, Tablas 4.1M y 4.2.

**Una inspección no recupera espesor**: solo cambia los Po<sub>i</sub> (menor incertidumbre sobre la CR real) y, por lo tanto, el D<sub>f</sub>.
Modelo académico simplificado: un solo mecanismo, sin cladding, F<sub>OM</sub> = F<sub>IP</sub> = F<sub>DL</sub> = 1 por defecto, consecuencias ingresadas por el usuario.

## Validación de datos (seguridad)
`py/proyecto.py` valida todo proyecto importado o recuperado del navegador: familias y materiales del catálogo, rangos físicos de cada dato de diseño, fechas ISO entre 1950 y 2100, espesores 0–300 mm, IDs únicos, coordenadas 0–100 %, imágenes solo PNG/JPG (rutas locales o embebidas) y adjuntos solo PDF embebido. Un archivo con errores se rechaza completo, indicando el motivo.
