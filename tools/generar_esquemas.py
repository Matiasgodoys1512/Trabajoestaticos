"""Genera los esquemas simplificados (PNG) de los equipos del caso demostrativo.
Convención de marcadores CML: coordenadas (x, y) en % del ancho/alto de la imagen, origen arriba-izquierda."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle, Polygon

AZUL, GRIS, NEGRO = "#2b5d8a", "#9aa5b1", "#222"


def lienzo(titulo):
    fig = plt.figure(figsize=(10, 6), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100); ax.set_ylim(100, 0); ax.axis("off")
    ax.add_patch(Rectangle((0.5, 0.5), 99, 99, fill=False, ec=NEGRO, lw=1.2))
    ax.add_patch(Rectangle((62, 88), 37.5, 11.5, fill=False, ec=NEGRO, lw=1))
    ax.text(63, 92.5, titulo, fontsize=10, weight="bold", va="center")
    ax.text(63, 97, "Esquema sin escala · MAN040-B", fontsize=8, va="center", color="#555")
    return fig, ax


def tuberia():
    fig, ax = lienzo("ISO-101 · Línea 8\"-HF-101")
    pts = [(8, 70), (30, 70), (30, 35), (75, 35), (75, 60), (92, 60)]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=AZUL, lw=9, solid_capstyle="butt", solid_joinstyle="round")
    ax.add_patch(Circle((8, 70), 5, fc="white", ec=NEGRO, lw=1.5)); ax.text(8, 80, "P-101\n(bomba)", ha="center", fontsize=8)
    ax.add_patch(Rectangle((90, 52), 8, 16, fc="white", ec=NEGRO, lw=1.5)); ax.text(94, 72, "V-201", ha="center", fontsize=8)
    for x, y in [(20, 70), (52, 35), (84, 60)]:
        ax.plot([x, x], [y - 4, y + 4], color=NEGRO, lw=2)
    ax.annotate("", xy=(45, 30), xytext=(38, 30), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(41, 27, "Flujo", fontsize=8, ha="center")
    ax.text(10, 10, "Circuito CI-HF-01 · A106 Gr. B · NPS 8 Sch 40 (8,18 mm)", fontsize=9)
    ax.text(10, 15, "Solo tramos rectos (alcance del prototipo)", fontsize=8, color="#555")
    fig.savefig("data/img/tuberia_L101.png"); plt.close(fig)


def recipiente():
    fig, ax = lienzo("V-201 · Separador de HF")
    ax.add_patch(FancyBboxPatch((38, 12), 24, 66, boxstyle="round,pad=0,rounding_size=10", fc="#e8eef4", ec=NEGRO, lw=1.8))
    for y in (24, 45, 66):
        ax.plot([38, 62], [y, y], color=GRIS, lw=1, ls="--")
    ax.text(64, 24, "Virola 1 (sup.)", fontsize=8); ax.text(64, 45, "Virola 2", fontsize=8); ax.text(64, 66, "Virola 3 (inf.)", fontsize=8)
    ax.plot([25, 38], [30, 30], color=AZUL, lw=6); ax.text(14, 28, "Entrada", fontsize=8)
    ax.plot([50, 50], [4, 12], color=AZUL, lw=5); ax.text(52, 6, "Gas", fontsize=8)
    ax.plot([50, 50], [78, 86], color=AZUL, lw=5); ax.text(52, 84, "Líquido", fontsize=8)
    for x in (42, 58):
        ax.plot([x, x], [78, 88], color=NEGRO, lw=2)
    ax.text(5, 10, "SA-516 Gr. 70 · DI 1500 mm · t nom 16 mm · E = 0,85", fontsize=9)
    fig.savefig("data/img/recipiente_V201.png"); plt.close(fig)


def tanque():
    fig, ax = lienzo("TK-301 · Tanque de diésel")
    x0, x1, base = 20, 80, 82
    alto = 12
    for i in range(5):
        y = base - (i + 1) * alto
        ax.add_patch(Rectangle((x0, y), x1 - x0, alto, fc="#e8eef4" if i % 2 == 0 else "#f6f8fa", ec=NEGRO, lw=1.2))
        ax.text(x1 + 1.5, y + alto / 2, f"Virola {i + 1}", fontsize=8, va="center")
    techo = base - 5 * alto
    ax.add_patch(Polygon([(x0, techo), (50, techo - 8), (x1, techo)], closed=True, fc="white", ec=NEGRO, lw=1.2))
    ax.plot([x0 - 5, x1 + 5], [base, base], color=NEGRO, lw=2.5)
    ax.text(5, 8, "API 650 · A283 Gr. C · D = 20 m · H = 12 m · G = 0,85", fontsize=9)
    fig.savefig("data/img/tanque_TK301.png"); plt.close(fig)


if __name__ == "__main__":
    tuberia(); recipiente(); tanque(); print("ok")
