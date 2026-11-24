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

- **t_nom**: espesor nominal de compra/fabricación.
- **t_calc**: espesor requerido por presión según el código de diseño.
- **t_diseño** = t_calc + CA (sobreespesor por corrosión). En tuberías se suma además la tolerancia de fabricación (−12,5 % para tubo sin costura): t_compra ≥ t_diseño / 0,875.
- **t_min (servicio)**: espesor mínimo admisible en servicio = máx(t_calc, t_estructural). **No** incluye CA.
- **t_alerta** = t_min + CR · T_int, donde T_int es el plazo de intervención (por defecto 2 años): se alerta cuando el espesor queda a menos de lo que se perdería durante el plazo necesario para planificar una reparación o un reemplazo.
- **t_medido**: lectura de UT en el CML.

### Tubería: ASME B31.3 §304.1.2, ec. (3a)
t = P·D / [2 (S·E·W + P·Y)], válida para t < D/6. Y = 0,4 (acero ferrítico ≤ 482 °C, Tabla 304.1.1); W = 1,0 (≤ 427 °C, Tabla 302.3.5).
t_estructural: ingresado por el usuario (⚠️ API 574 da valores por defecto según el NPS).

### Recipiente: ASME VIII-1 UG-27(c)(1) (esfuerzo circunferencial)
t = P·R / (S·E − 0,6·P), con R = radio interior; válida para P ≤ 0,385·S·E.

### Tanque: API 650 §5.6.3.2 (método de 1 pie) y API 653 §4.3.3.1 ⚠️
- Diseño: td = 4,9·D·(H − 0,3)·G / Sd + CA [mm; D, H en m].
- Servicio (API 653): t_min = 4,9·D·(H − 0,3)·G / (S·E), con S = mín(0,80·Y; 0,429·T) para las virolas 1 y 2, y S = mín(0,88·Y; 0,472·T) para las demás. t_min ≥ 2,5 mm.
- H se mide desde el fondo de la virola evaluada hasta el nivel máximo de líquido.

## Corrosión y vida remanente (API 510 / 570, clase 05)
- CR_LP = (t_inicial − t_actual) / Δt(inicial→actual)
- CR_CP = (t_previa − t_actual) / Δt(previa→actual)
- CR adoptada = máx(CR_LP, CR_CP) (criterio conservador, ppt 05 lámina 11).
- RL = (t_actual − t_min) / CR

Validaciones: menos de 2 mediciones comparables → "información insuficiente"; fechas duplicadas o desordenadas → error; CR ≤ 0 → se informa y no se calcula RL por esa vía; t_actual < t_min → "bajo el mínimo". Una medición marcada como **reemplazo/reparación/cambio de punto** reinicia la serie comparable.

## Próxima inspección (mediciones de espesor)
| Norma | Intervalo |
|---|---|
| API 510 §7.1.1 ⚠️ | mín(RL/2; 10 años). Si RL < 4 años: mín(RL; 2 años). |
| API 570 §6.3.3 (ppt 05 lám. 13) | mín(RL/2; máximo de la tabla por clase: Clase 1 = 5, Clase 2 = 10, Clase 3 = 10 años). Si RL < 4: mín(RL; 2). |
| API 653 §6.3.3.2 ⚠️ (UT externo del manto) | CR conocida: mín(RCA/(2·N) = RL/2; 15 años). CR desconocida: 5 años. Fuera de alcance: inspección interna y fondo (datos pendientes). |

Fecha próxima = fecha de la última medición + intervalo. Estado **vencida** si hoy > fecha próxima.

## RBI: API RP 581 Parte 2 §4 (adelgazamiento generalizado), aplicado al recipiente
1. Art = Cr·age_tk / t_rdi (sin cladding, ec. 2.12).
2. FS = (YS + TS)/2 · E · 1,1 (ec. 2.13).
3. SR_P = S·E·máx(t_min, t_c) / (FS·t_rdi) (ec. 2.14).
4. Prior (Tabla 4.5): baja 0,5/0,3/0,2; media 0,7/0,2/0,1; alta 0,8/0,15/0,05.
5. Condicional (Tabla 4.6) para E/D/C/B/A: Co1 = 0,33/0,4/0,5/0,7/0,9; Co2 = 0,33/0,33/0,3/0,2/0,09; Co3 = 0,33/0,27/0,2/0,1/0,01.
6. I_i = Pr_i · Π Co_i^N; Po_i = I_i / ΣI (ec. 2.16–2.17, Bayes).
7. β_i = (1 − DS_i·Art − SR_P) / √(DS_i²·Art²·COV_Δt² + (1 − DS_i·Art)²·COV_Sf² + SR_P²·COV_P²), con DS = 1, 2, 4; COV_Δt = 0,20; COV_Sf = 0,20; COV_P = 0,05 (ec. 2.18).
8. D_fB = Σ Po_i·Φ(−β_i) / 1,56·10⁻⁴ (ec. 2.19); D_f = máx(D_fB·F_IP·F_DL / F_OM; 0,1) (ec. 2.20).
9. P_f(t) = gff · F_MS · D_f, con gff = 3,06·10⁻⁵ fallas/año (Tabla 3.1) y F_MS = 10^(−0,02·pscore + 1) (ec. 2.10).
10. R_A = P_f · C_A [m²/año]; R_E = P_f · C_E [USD/año]. Categorías: Parte 1, Tablas 4.1M y 4.2.

**Una inspección no recupera espesor**: solo cambia los Po_i (menor incertidumbre sobre la CR real) y, por lo tanto, el D_f.
Modelo académico simplificado: un solo mecanismo, sin cladding, F_OM = F_IP = F_DL = 1 por defecto, consecuencias ingresadas por el usuario.
