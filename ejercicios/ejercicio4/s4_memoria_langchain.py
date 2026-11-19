"""Sesión 4. Memoria persistente con LangChain: hilos (corto plazo) y preferencias (largo plazo).

Uso:  python s4_memoria_langchain.py <cliente_id> <hilo>
      p. ej. "python s4_memoria_langchain.py 1 lunes" y después "... 1 martes"."""
import os
import sqlite3
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

load_dotenv()
MODELO = f"anthropic:{os.environ['ANTHROPIC_MODEL']}"


@dataclass
class Contexto:
    cliente_id: str  # lo fija la aplicación tras identificar al cliente; el modelo no puede cambiarlo
    olvido_pedido: bool = False


def _espacio(runtime: ToolRuntime[Contexto]) -> tuple[str, str]:
    return ("clientes", runtime.context.cliente_id)  # namespace: aísla la memoria de cada cliente


def hilos_del_cliente(cliente_id: str) -> set[str]:
    return {c.config["configurable"]["thread_id"] for c in checkpointer.list(None)
            if c.config["configurable"]["thread_id"].startswith(f"{cliente_id}-")}


@tool
def recordar_preferencia(clave: str, valor: str, runtime: ToolRuntime[Contexto]) -> str:
    """Guarda una preferencia estable del cliente (horario de entrega, producto habitual,
    forma de contacto). No guardes datos personales sensibles ni datos de pago."""
    runtime.store.put(_espacio(runtime), clave, {"valor": valor})
    return f"Preferencia '{clave}' guardada."


@tool
def ver_preferencias(runtime: ToolRuntime[Contexto]) -> dict:
    """Devuelve las preferencias guardadas del cliente actual."""
    return {item.key: item.value["valor"] for item in runtime.store.search(_espacio(runtime))}


@tool
def olvidar_preferencias(runtime: ToolRuntime[Contexto]) -> str:
    """Borra las preferencias y las conversaciones del cliente actual. Úsala si el cliente
    pide que olvidemos sus datos."""
    for item in runtime.store.search(_espacio(runtime)):
        runtime.store.delete(_espacio(runtime), item.key)
    actual = runtime.config["configurable"]["thread_id"]
    for hilo in hilos_del_cliente(runtime.context.cliente_id) - {actual}:
        checkpointer.delete_thread(hilo)
    # el hilo actual se borra en el main: si se borra aquí, se vuelve a guardar al acabar el turno
    runtime.context.olvido_pedido = True
    return "Preferencias y conversaciones eliminadas."


SISTEMA = """Eres el asistente comercial de Tostadero Retiro.
Al empezar cada conversación consulta ver_preferencias y tenlas en cuenta.
Cuando el cliente exprese una preferencia estable, guárdala con recordar_preferencia.
Si pide que olvides sus datos, usa olvidar_preferencias y confírmalo."""


def conectar(fichero: str, **kw) -> sqlite3.Connection:
    con = sqlite3.connect(fichero, check_same_thread=False, **kw)
    con.execute("PRAGMA secure_delete = ON")  # que lo borrado no quede en el fichero
    return con


# Dos almacenes distintos: hilos de conversación y memoria a largo plazo
checkpointer = SqliteSaver(conectar("hilos.db"))
store = SqliteStore(conectar("memoria.db", isolation_level=None))
store.setup()

agente = create_agent(
    model=MODELO,
    tools=[recordar_preferencia, ver_preferencias, olvidar_preferencias],
    system_prompt=SISTEMA,
    context_schema=Contexto,
    checkpointer=checkpointer,
    store=store,
    middleware=[SummarizationMiddleware(model=MODELO, trigger=("tokens", 3000),
                                        keep=("messages", 10))],
)

if __name__ == "__main__":
    cliente_id, hilo = sys.argv[1], sys.argv[2]
    config = {"configurable": {"thread_id": f"{cliente_id}-{hilo}"}}
    contexto = Contexto(cliente_id=cliente_id)
    n = len(agente.get_state(config).values.get("messages", []))
    print(f"[hilo {cliente_id}-{hilo}: {n} mensajes guardados de sesiones anteriores]")
    while texto := input("Cliente: ").strip():
        if not sys.stdin.isatty():
            print(texto)
        estado = agente.invoke({"messages": [{"role": "user", "content": texto}]},
                               config, context=contexto)
        for m in estado["messages"][n:]:
            for llamada in getattr(m, "tool_calls", None) or []:
                print(f"   [herramienta] {llamada['name']}({llamada['args']})")
        n = len(estado["messages"])
        print("Asistente:", estado["messages"][-1].text)
        if contexto.olvido_pedido:
            checkpointer.delete_thread(config["configurable"]["thread_id"])
            print("[hilo actual borrado; fin de la sesión]")
            break
