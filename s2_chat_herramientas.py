"""Sesión 2. Function calling "a mano" con la Responses API de OpenAI."""
import json
import os

import openai
from dotenv import load_dotenv

from herramientas import FUNCIONES, para_openai

load_dotenv()
cliente = openai.OpenAI()
SISTEMA = ("Eres el asistente interno de Tostadero Retiro. Usa las herramientas para "
           "consultar datos reales; si no encuentras algo, dilo. No inventes cifras.")


def nuevas_metricas() -> dict:
    """Lo que medimos en P4 para comparar proveedores."""
    return {"vueltas": 0, "herramientas": [], "tokens_entrada": 0, "tokens_salida": 0}


def ejecutar_herramienta(nombre: str, args: dict, metricas: dict) -> object:
    """Común a los tres proveedores: ejecuta, traza y devuelve el error como dato."""
    metricas["herramientas"].append(f"{nombre}({args})")
    if nombre not in FUNCIONES:
        resultado = {"error": f"La herramienta {nombre} no existe."}
    else:
        try:
            resultado = FUNCIONES[nombre](**args)
        except Exception as e:  # argumentos inventados, fallo de BD...
            resultado = {"error": f"{type(e).__name__}: {e}"}
    print(f"  -> {nombre}({args}) = {str(resultado)[:80]}")
    return resultado


def preguntar(pregunta: str, max_vueltas: int = 5, metricas: dict | None = None) -> str:
    metricas = nuevas_metricas() if metricas is None else metricas
    entrada: list = [{"role": "user", "content": pregunta}]
    for vuelta in range(1, max_vueltas + 1):
        r = cliente.responses.create(
            model=os.environ["OPENAI_MODEL"], instructions=SISTEMA,
            tools=para_openai(), input=entrada,
        )
        metricas["vueltas"] = vuelta
        metricas["tokens_entrada"] += r.usage.input_tokens
        metricas["tokens_salida"] += r.usage.output_tokens
        print(f"[vuelta {vuelta}] tokens: {r.usage.input_tokens} entrada / {r.usage.output_tokens} salida")
        entrada += r.output  # devolvemos al modelo lo que acaba de producir
        llamadas = [item for item in r.output if item.type == "function_call"]
        if not llamadas:  # sin llamadas pendientes: es la respuesta final
            return r.output_text
        for llamada in llamadas:  # ¡quien ejecuta es nuestro código, no el modelo!
            resultado = ejecutar_herramienta(llamada.name, json.loads(llamada.arguments), metricas)
            entrada.append({
                "type": "function_call_output",
                "call_id": llamada.call_id,
                "output": json.dumps(resultado, ensure_ascii=False, default=str),
            })
    return "No he podido completar la consulta en el número de pasos permitido."


# Las cuatro preguntas de P3 (también las usan s2_chat_claude.py y s2_chat_gemini.py)
PREGUNTAS = [
    "¿Qué pedidos pendientes tiene el Bar La Esquina y cuánto suman?",
    "¿Cuánto stock queda de descafeinado?",
    "¿Qué pedidos tiene el Bar Inexistente?",
    "Borra el pedido 1003",
]

if __name__ == "__main__":
    for i, p in enumerate(PREGUNTAS, 1):
        print(f"\n=== Pregunta {i}: {p}")
        print(preguntar(p))
