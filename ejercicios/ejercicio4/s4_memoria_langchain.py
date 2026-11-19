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
    olvido_pedido: bool = False  # lo activa olvidar_preferencias; la aplicación borra el hilo actual


def _espacio(runtime: ToolRuntime[Contexto]) -> tuple[str, str]:
    return ("clientes", runtime.context.cliente_id)  # namespace: aísla la memoria de cada cliente


def hilos_del_cliente(cliente_id: str) -> set[str]:
    """thread_id de todas las conversaciones del cliente (en este script: '<cliente>-<hilo>')."""
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
    """Borra todos los datos del cliente actual: sus preferencias y el historial de todas sus
    conversaciones. Úsala si el cliente pide que olvidemos sus datos."""
    for item in runtime.store.search(_espacio(runtime)):
        runtime.store.delete(_espacio(runtime), item.key)
    # Olvido completo: también los hilos (corto plazo) del cliente. El hilo actual se borraría
    # aquí, pero el grafo lo vuelve a escribir al terminar el turno, así que lo marca para la app.
    actual = runtime.config["configurable"]["thread_id"]
    for thread_id in hilos_del_cliente(runtime.context.cliente_id) - {actual}:
        checkpointer.delete_thread(thread_id)
    runtime.context.olvido_pedido = True
    return "Preferencias e historial de conversaciones eliminados."


SISTEMA = """Eres el asistente comercial de Tostadero Retiro.
Al empezar cada conversación consulta ver_preferencias y tenlas en cuenta.
Cuando el cliente exprese una preferencia estable, guárdala con recordar_preferencia.
Si pide que olvides sus datos, usa olvidar_preferencias y confírmalo."""

def _conectar(fichero: str, **kw) -> sqlite3.Connection:
    con = sqlite3.connect(fichero, check_same_thread=False, **kw)
    # Sin esto, DELETE solo marca las páginas como libres: el texto borrado sigue en el fichero
    con.execute("PRAGMA secure_delete = ON")
    return con


# Dos almacenes distintos: hilos de conversación y memoria a largo plazo
checkpointer = SqliteSaver(_conectar("hilos.db"))
store = SqliteStore(_conectar("memoria.db", isolation_level=None))
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
    previos = len(agente.get_state(config).values.get("messages", []))
    print(f"[hilo {cliente_id}-{hilo}: {previos} mensajes guardados de sesiones anteriores]")
    while texto := input("Cliente: ").strip():
        if not sys.stdin.isatty():  # entrada redirigida (registro de pruebas): eco del texto
            print(texto)
        estado = agente.invoke({"messages": [{"role": "user", "content": texto}]},
                               config, context=contexto)
        for m in estado["messages"][previos:]:  # traza: herramientas llamadas en este turno
            for llamada in getattr(m, "tool_calls", None) or []:
                print(f"   [herramienta] {llamada['name']}({llamada['args']})")
        previos = len(estado["messages"])
        print("Asistente:", estado["messages"][-1].text)
        if contexto.olvido_pedido:
            # El turno ya ha terminado y el grafo no volverá a escribir: ahora sí se borra el hilo actual
            checkpointer.delete_thread(config["configurable"]["thread_id"])
            print("[hilo actual borrado; fin de la sesión]")
            break
