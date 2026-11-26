"""Genera los esquemas simplificados (PNG) de los equipos del caso demostrativo.

Convención de marcadores CML: coordenadas (x, y) en % del ancho/alto de la imagen, origen arriba-izquierda.
La geometría (posiciones) no debe cambiar sin actualizar las coordenadas de los CML en data/demo.json.
Estilo: trazo fino, rellenos suaves y un único acento (coherente con la interfaz).
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

TINTA, TINTA2, MUTED = "#1d1d1f", "#6e6e73", "#a1a1a6"
RELLENO, RELLENO2, ACENTO, FONDO = "#eef0f2", "#f6f7f8", "#1f7a4d", "#fbfbfd"
LW = 1.4


def lienzo(tag, subtitulo):
    fig = plt.figure(figsize=(10, 6), dpi=110)
    fig.patch.set_facecolor(FONDO)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(100, 0)
    ax.axis("off")
    ax.text(4, 89, tag, fontsize=13, weight="bold", color=TINTA, va="center")
    ax.text(4, 94.5, subtitulo, fontsize=9, color=TINTA2, va="center")
    ax.text(96, 5, "Esquema sin escala", fontsize=8, color=MUTED, ha="right", va="center")
    return fig, ax


def etiqueta(ax, x, y, texto, ha="left"):
    ax.text(x, y, texto, fontsize=8.5, color=TINTA2, ha=ha, va="center")


def tuberia():
    fig, ax = lienzo("8\"-HF-101", "Circuito CI-HF-01 · A106 Gr. B · NPS 8 Sch 40 (8,18 mm) · solo tramos rectos")
    pts = [(8, 70), (30, 70), (30, 35), (75, 35), (75, 60), (92, 60)]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=RELLENO, lw=14, solid_capstyle="butt", solid_joinstyle="round", zorder=1)
    ax.plot(xs, ys, color=ACENTO, lw=2.2, solid_joinstyle="round", zorder=2)
    ax.add_patch(Circle((8, 70), 4.6, fc="#fff", ec=TINTA, lw=LW, zorder=3))
    ax.add_patch(Circle((8, 70), 1.4, fc=TINTA, ec="none", zorder=4))
    etiqueta(ax, 8, 79, "P-101", "center")
    ax.add_patch(FancyBboxPatch((89.5, 51), 7, 18, boxstyle="round,pad=0,rounding_size=2.5", fc="#fff", ec=TINTA, lw=LW, zorder=3))
    etiqueta(ax, 93, 73, "V-201", "center")
    for x, y, vertical in [(20, 70, True), (52, 35, True), (84, 60, True)]:
        ax.plot([x, x], [y - 3.6, y + 3.6], color=TINTA, lw=2, solid_capstyle="round", zorder=4)
    ax.annotate("", xy=(46, 29.5), xytext=(38, 29.5), arrowprops=dict(arrowstyle="-|>", lw=1.2, color=TINTA2))
    etiqueta(ax, 42, 26.5, "Flujo", "center")
    fig.savefig("data/img/tuberia_L101.png", facecolor=FONDO)
    plt.close(fig)


def recipiente():
    fig, ax = lienzo("V-201", "Separador de HF · SA-516 Gr. 70 · DI 1500 mm · t nom 16 mm · E = 0,85")
    ax.plot([50, 50], [4.5, 12], color=ACENTO, lw=2.2)
    ax.plot([50, 50], [78, 86], color=ACENTO, lw=2.2)
    ax.plot([24, 38], [30, 30], color=ACENTO, lw=2.2)
    ax.add_patch(FancyBboxPatch((38, 12), 24, 66, boxstyle="round,pad=0,rounding_size=11", fc=RELLENO2, ec=TINTA, lw=LW, zorder=2))
    for y in (34.5, 55.5):
        ax.plot([38.4, 61.6], [y, y], color=MUTED, lw=.8, ls=(0, (3, 3)), zorder=3)
    for y, t in ((24, "Virola 1 (sup.)"), (45, "Virola 2"), (66, "Virola 3 (inf.)")):
        etiqueta(ax, 65, y, t)
    etiqueta(ax, 23, 27, "Entrada", "right")
    etiqueta(ax, 52, 7, "Gas")
    etiqueta(ax, 52, 84, "Líquido")
    for x in (42, 58):
        ax.plot([x, x], [76, 88], color=TINTA, lw=LW)
    ax.plot([39, 61], [88, 88], color=MUTED, lw=1)
    fig.savefig("data/img/recipiente_V201.png", facecolor=FONDO)
    plt.close(fig)


def tanque():
    fig, ax = lienzo("TK-301", "Tanque de diésel · API 650 · A283 Gr. C · D = 20 m · H = 12 m · G = 0,85")
    x0, x1, base, alto = 20, 80, 82, 12
    for i in range(5):
        y = base - (i + 1) * alto
        ax.add_patch(Rectangle((x0, y), x1 - x0, alto, fc=RELLENO2 if i % 2 else RELLENO, ec=TINTA, lw=LW, zorder=2))
        etiqueta(ax, x1 + 2, y + alto / 2, f"Virola {i + 1}")
    techo = base - 5 * alto
    ax.add_patch(Polygon([(x0, techo), (50, techo - 7), (x1, techo)], closed=True, fc="#fff", ec=TINTA, lw=LW, zorder=2))
    ax.plot([x0 - 6, x1 + 6], [base, base], color=TINTA, lw=2.2, solid_capstyle="round")
    for xx in range(x0 - 5, x1 + 6, 3):
        ax.plot([xx, xx - 1.6], [base + .4, base + 2.6], color=MUTED, lw=.8)
    fig.savefig("data/img/tanque_TK301.png", facecolor=FONDO)
    plt.close(fig)


if __name__ == "__main__":
    tuberia()
    recipiente()
    tanque()
    print("ok")
