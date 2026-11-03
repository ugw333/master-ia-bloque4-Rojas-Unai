"""Sesión 3 · P2. Experimentos con el agente: los cinco de la tabla del enunciado.

Cada experimento cambia una sola cosa (límite, aprobación, descripción o prompt) y
guarda la traza. Uso: python s3_experimentos.py [1-5]   (sin argumento: todos)"""
import sys

from herramientas import DEFINICIONES, _consulta
from s3_agente import SISTEMA, Agente, crear_herramientas

CORREO_LUMBRE = ("Buenas, os escribo del Restaurante Lumbre. La cafetera de dos grupos no "
                 "calienta y hoy no podemos servir cafés. ¿Además, cuándo llega el pedido pendiente?")
CORREO_AGOSTO = "¿Revisáis las máquinas en agosto?"
CORREO_REVISION = ("Hola, somos Bar La Esquina. ¿Revisáis las máquinas en agosto? Nos gustaría "
                   "que le echarais un ojo a la cafetera de 2 grupos antes de las vacaciones.")

FRASE_GUARDA = " Úsala solo si el cliente describe una avería concreta."
PASO_1 = "1. Identifica al cliente con buscar_cliente antes de usar su id.\n"
REGLA_BUSCAR = " Úsala antes de cualquier otra herramienta que pida cliente_id."


def aprobar(nombre, args):
    print(f"  [humano] APRUEBA {nombre}")
    return True


def rechazar(nombre, args):
    print(f"  [humano] RECHAZA {nombre}")
    return False


def num_incidencias() -> int:
    return _consulta("SELECT COUNT(*) AS n FROM incidencias")[0]["n"]


def correr(titulo: str, agente: Agente, correo: str):
    print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}\nCorreo: {correo}\n")
    antes = num_incidencias()
    respuesta = agente.ejecutar(correo)
    print(f"\n--- Respuesta al cliente ---\n{respuesta}\n")
    print(f"[métricas] {agente.llamadas} llamadas · {agente.tokens_entrada}+{agente.tokens_salida} "
          f"tokens · incidencias creadas: {num_incidencias() - antes}")


def exp1():
    correr("EXP 1 · Correo de ejemplo (se aprueba la incidencia)",
           Agente(SISTEMA, crear_herramientas(), aprobador=aprobar), CORREO_LUMBRE)


def exp2():
    correr("EXP 2 · max_pasos=2",
           Agente(SISTEMA, crear_herramientas(), max_pasos=2, aprobador=aprobar), CORREO_LUMBRE)


def exp3():
    correr("EXP 3 · El humano rechaza la incidencia",
           Agente(SISTEMA, crear_herramientas(), aprobador=rechazar), CORREO_LUMBRE)


def exp4():
    # Control: descripción original. Variante: sin la frase que limita su uso.
    correr("EXP 4a · '¿Revisáis las máquinas en agosto?' con la descripción ORIGINAL",
           Agente(SISTEMA, crear_herramientas(), aprobador=aprobar), CORREO_AGOSTO)
    sin_guarda = [dict(d, description=d["description"].replace(FRASE_GUARDA, ""))
                  if d["name"] == "crear_incidencia" else d for d in DEFINICIONES]
    assert sin_guarda != DEFINICIONES, "no se ha encontrado la frase a quitar"
    correr("EXP 4b · Mismo correo SIN 'Úsala solo si el cliente describe una avería'",
           Agente(SISTEMA, crear_herramientas(sin_guarda), aprobador=aprobar), CORREO_AGOSTO)
    # Variante más tentadora: hay cliente identificable y se menciona una máquina concreta
    for etiqueta, defs in [("ORIGINAL", DEFINICIONES), ("SIN la frase", sin_guarda)]:
        correr(f"EXP 4c · Revisión preventiva con cliente y máquina, descripción {etiqueta}",
               Agente(SISTEMA, crear_herramientas(defs), aprobador=aprobar), CORREO_REVISION)


def exp5():
    sistema_sin_paso1 = SISTEMA.replace(PASO_1, "")
    assert sistema_sin_paso1 != SISTEMA, "no se ha encontrado el paso 1"
    correr("EXP 5a · SISTEMA sin el paso 1 (identificar al cliente)",
           Agente(sistema_sin_paso1, crear_herramientas(), aprobador=aprobar), CORREO_LUMBRE)
    # La misma regla está repetida en la descripción de buscar_cliente: la quitamos también
    sin_regla = [dict(d, description=d["description"].replace(REGLA_BUSCAR, ""))
                 if d["name"] == "buscar_cliente" else d for d in DEFINICIONES]
    assert sin_regla != DEFINICIONES, "no se ha encontrado la regla de buscar_cliente"
    correr("EXP 5b · Sin paso 1 NI la regla en la descripción de buscar_cliente",
           Agente(sistema_sin_paso1, crear_herramientas(sin_regla), aprobador=aprobar),
           CORREO_LUMBRE)


EXPERIMENTOS = {"1": exp1, "2": exp2, "3": exp3, "4": exp4, "5": exp5}

if __name__ == "__main__":
    for clave in sys.argv[1:] or EXPERIMENTOS:
        EXPERIMENTOS[clave]()
