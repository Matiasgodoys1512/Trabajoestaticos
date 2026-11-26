"""Ediciones y secciones normativas citadas por el motor (un solo lugar para mantenerlas).

API 510, 570 y 653: no se dispuso del texto completo; ediciones declaradas por el grupo y criterios
tomados de los apuntes del curso (clase 05). Verificar contra el documento si se obtiene.
"""
EDICION = {
    "B31.3": "ASME B31.3-2018",
    "VIII-1": "ASME BPVC VIII-1 2019",
    "II-D": "ASME BPVC II-D 2019",
    "API 650": "API 650 12ª ed. (2013)",
    "API 510": "API 510 10ª ed. (2014, Add. 1 2017)",
    "API 570": "API 570 4ª ed. (2016, Add. 1 2017, Add. 2 2018)",
    "API 653": "API 653 5ª ed. (2014, Add. 1 2018, Add. 2 2020)",
    "API 574": "API 574 4ª ed. (2016)",
    "API 581": "API RP 581 3ª ed. (2016, Add. 2 2020)",
}

# Referencia de velocidad de corrosión y vida remanente según la familia (hallazgo H2)
REF_CORROSION = {
    "tuberia": f"{EDICION['API 570']} §7.1.1",
    "recipiente": f"{EDICION['API 510']} §7.1.1",
    "tanque": f"{EDICION['API 653']} §6.3.3.2 (RCA/N)",
}
REF_INTERVALO = {
    "tuberia": f"{EDICION['API 570']} §6.3.3, intervalos máximos por clase",
    "recipiente": f"{EDICION['API 510']} §6.5.1.1",
    "tanque": f"{EDICION['API 653']} §6.3.3.2, UT externo del manto",
}
