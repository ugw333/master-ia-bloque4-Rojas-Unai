"""Sesión 3. El mismo agente con LangChain 1.x: create_agent + middleware.

Uso: python s3_agente_langchain.py [modelo]
     p. ej. python s3_agente_langchain.py openai:google/gemini-3.8-flash"""
import os
import sys
from typing import Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ModelCallLimitMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import herramientas as h
from s3_agente import SISTEMA

load_dotenv()


@tool
def buscar_cliente(texto: str) -> list[dict]:
    """Busca clientes por nombre (coincidencia parcial). Devuelve id, nombre, tipo y distrito."""
    return h.buscar_cliente(texto)


@tool
def consultar_pedidos(cliente_id: int) -> list[dict]:
    """Lista los pedidos de un cliente con fecha, estado y total en euros."""
    return h.consultar_pedidos(cliente_id)


@tool
def crear_incidencia(cliente_id: int, maquina: str, descripcion: str,
                     prioridad: Literal["baja", "media", "alta"]) -> dict:
    """Registra una avería de una máquina de un cliente (maquina = SKU, p. ej. MAQ-010)."""
    return h.crear_incidencia(cliente_id, maquina, descripcion, prioridad)


MODELO = sys.argv[1] if len(sys.argv) > 1 else f"anthropic:{os.environ['ANTHROPIC_MODEL']}"

agente = create_agent(
    model=MODELO,  # o "openai:google/gemini-3.8-flash": cambiar de proveedor es una cadena
    tools=[buscar_cliente, consultar_pedidos, crear_incidencia],
    system_prompt=SISTEMA,
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={"crear_incidencia": True}),
        ModelCallLimitMiddleware(run_limit=8),  # equivale a nuestro max_pasos
    ],
    checkpointer=InMemorySaver(),  # imprescindible para pausar y reanudar
)

if __name__ == "__main__":
    print(f"Modelo: {MODELO}")
    config = {"configurable": {"thread_id": "correo-lumbre-001"}}
    correo = ("Os escribo del Restaurante Lumbre: la cafetera de dos grupos no calienta "
              "y hoy no podemos servir cafés.")
    estado = agente.invoke({"messages": [{"role": "user", "content": correo}]}, config)
    while "__interrupt__" in estado:  # el grafo se ha pausado esperando a una persona
        decisiones = []
        for peticion in estado["__interrupt__"][0].value["action_requests"]:
            ok = input(f"¿Aprobar {peticion['name']}({peticion['args']})? [s/N] ").lower() == "s"
            decisiones.append({"type": "approve" if ok else "reject"})
        estado = agente.invoke(Command(resume={"decisions": decisiones}), config)
    # Traza: la reconstruimos a posteriori a partir del estado del grafo
    for m in estado["messages"]:
        for llamada in getattr(m, "tool_calls", []) or []:
            print(f"[traza] {llamada['name']}({llamada['args']})")
    print(estado["messages"][-1].text)
