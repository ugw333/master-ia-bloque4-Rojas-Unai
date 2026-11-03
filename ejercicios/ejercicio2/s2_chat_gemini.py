"""Sesión 2 · P4. El mismo asistente con Gemini (Chat Completions vía OpenRouter)."""
import json
import os

import openai
from dotenv import load_dotenv

from herramientas import para_chat
from s2_chat_herramientas import PREGUNTAS, SISTEMA, ejecutar_herramienta, nuevas_metricas

load_dotenv()
cliente = openai.OpenAI(base_url="https://openrouter.ai/api/v1",
                        api_key=os.environ["OPENROUTER_API_KEY"])


def preguntar_gemini(pregunta: str, max_vueltas: int = 5, metricas: dict | None = None) -> str:
    metricas = nuevas_metricas() if metricas is None else metricas
    # Diferencia con OpenAI/Claude: el sistema va como primer mensaje de la lista
    mensajes: list = [{"role": "system", "content": SISTEMA},
                      {"role": "user", "content": pregunta}]
    for vuelta in range(1, max_vueltas + 1):
        r = cliente.chat.completions.create(
            model=os.environ["GEMINI_MODEL"], messages=mensajes, tools=para_chat(),
        )
        metricas["vueltas"] = vuelta
        metricas["tokens_entrada"] += r.usage.prompt_tokens
        metricas["tokens_salida"] += r.usage.completion_tokens
        print(f"[vuelta {vuelta}] tokens: {r.usage.prompt_tokens} entrada / {r.usage.completion_tokens} salida")
        mensaje = r.choices[0].message
        mensajes.append(mensaje)
        if not mensaje.tool_calls:  # sin llamadas pendientes: es la respuesta final
            return mensaje.content or ""
        for llamada in mensaje.tool_calls:  # los argumentos llegan como texto JSON
            resultado = ejecutar_herramienta(llamada.function.name,
                                             json.loads(llamada.function.arguments), metricas)
            # Un mensaje "tool" por cada llamada
            mensajes.append({
                "role": "tool",
                "tool_call_id": llamada.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })
    return "No he podido completar la consulta en el número de pasos permitido."


if __name__ == "__main__":
    for i, p in enumerate(PREGUNTAS, 1):
        print(f"\n=== Pregunta {i}: {p}")
        print(preguntar_gemini(p))
