"""Sesión 3 · P2. Experimentos con el agente.

Uso: python s3_experimentos.py [1-5]   (sin argumento: todos)"""
import sys

from herramientas import DEFINICIONES, _consulta
from s3_agente import SISTEMA, Agente, crear_herramientas

CORREO_LUMBRE = ("Buenas, os escribo del Restaurante Lumbre. La cafetera de dos grupos no "
                 "calienta y hoy no podemos servir cafés. ¿Además, cuándo llega el pedido pendiente?")
CORREO_AGOSTO = "¿Revisáis las máquinas en agosto?"
CORREO_REVISION = ("Hola, somos Bar La Esquina. ¿Revisáis las máquinas en agosto? Nos gustaría "
                   "que le echarais un ojo a la cafetera de 2 grupos antes de las vacaciones.")


def aprobar(nombre, args):
    print(f"  [humano] APRUEBA {nombre}")
    return True


def rechazar(nombre, args):
    print(f"  [humano] RECHAZA {nombre}")
    return False


def sin_frase(nombre: str, frase: str) -> list[dict]:
    return [dict(d, description=d["description"].replace(frase, "")) if d["name"] == nombre else d
            for d in DEFINICIONES]


def correr(titulo: str, agente: Agente, correo: str):
    print(f"\n=== {titulo}\nCorreo: {correo}\n")
    antes = _consulta("SELECT COUNT(*) AS n FROM incidencias")[0]["n"]
    respuesta = agente.ejecutar(correo)
    despues = _consulta("SELECT COUNT(*) AS n FROM incidencias")[0]["n"]
    print(f"\nRespuesta al cliente:\n{respuesta}\n")
    print(f"{agente.llamadas} llamadas · {agente.tokens_entrada}+{agente.tokens_salida} tokens · "
          f"incidencias creadas: {despues - antes}")


def exp1():
    correr("EXP 1 · Correo de ejemplo", Agente(SISTEMA, crear_herramientas(), aprobador=aprobar),
           CORREO_LUMBRE)


def exp2():
    correr("EXP 2 · max_pasos=2",
           Agente(SISTEMA, crear_herramientas(), max_pasos=2, aprobador=aprobar), CORREO_LUMBRE)


def exp3():
    correr("EXP 3 · Se rechaza la incidencia",
           Agente(SISTEMA, crear_herramientas(), aprobador=rechazar), CORREO_LUMBRE)


def exp4():
    sin_guarda = sin_frase("crear_incidencia", " Úsala solo si el cliente describe una avería concreta.")
    correr("EXP 4a · Agosto, descripción original",
           Agente(SISTEMA, crear_herramientas(), aprobador=aprobar), CORREO_AGOSTO)
    correr("EXP 4b · Agosto, sin la frase",
           Agente(SISTEMA, crear_herramientas(sin_guarda), aprobador=aprobar), CORREO_AGOSTO)
    correr("EXP 4c · Revisión con cliente, descripción original",
           Agente(SISTEMA, crear_herramientas(), aprobador=aprobar), CORREO_REVISION)
    correr("EXP 4c · Revisión con cliente, sin la frase",
           Agente(SISTEMA, crear_herramientas(sin_guarda), aprobador=aprobar), CORREO_REVISION)


def exp5():
    sistema = SISTEMA.replace("1. Identifica al cliente con buscar_cliente antes de usar su id.\n", "")
    sin_regla = sin_frase("buscar_cliente", " Úsala antes de cualquier otra herramienta que pida cliente_id.")
    correr("EXP 5a · Sin el paso 1",
           Agente(sistema, crear_herramientas(), aprobador=aprobar), CORREO_LUMBRE)
    correr("EXP 5b · Sin el paso 1 ni la regla de buscar_cliente",
           Agente(sistema, crear_herramientas(sin_regla), aprobador=aprobar), CORREO_LUMBRE)


EXPERIMENTOS = {"1": exp1, "2": exp2, "3": exp3, "4": exp4, "5": exp5}

if __name__ == "__main__":
    for clave in sys.argv[1:] or EXPERIMENTOS:
        EXPERIMENTOS[clave]()
