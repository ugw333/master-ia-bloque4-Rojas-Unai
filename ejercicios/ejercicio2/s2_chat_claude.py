"""Sesión 2 · P4. El mismo asistente con Claude (Anthropic Messages API)."""
import json
import os

import anthropic
from dotenv import load_dotenv

from herramientas import para_claude
from s2_chat_herramientas import PREGUNTAS, SISTEMA, ejecutar_herramienta, nuevas_metricas

load_dotenv()
cliente = anthropic.Anthropic()


def preguntar_claude(pregunta: str, max_vueltas: int = 5, metricas: dict | None = None) -> str:
    metricas = nuevas_metricas() if metricas is None else metricas
    mensajes: list = [{"role": "user", "content": pregunta}]
    for vuelta in range(1, max_vueltas + 1):
        r = cliente.messages.create(
            model=os.environ["ANTHROPIC_MODEL"], max_tokens=1024, system=SISTEMA,
            tools=para_claude(), messages=mensajes,
        )
        metricas["vueltas"] = vuelta
        metricas["tokens_entrada"] += r.usage.input_tokens
        metricas["tokens_salida"] += r.usage.output_tokens
        print(f"[vuelta {vuelta}] tokens: {r.usage.input_tokens} entrada / {r.usage.output_tokens} salida")
        # Diferencia con OpenAI: el turno del asistente se devuelve entero como "content"
        mensajes.append({"role": "assistant", "content": r.content})
        llamadas = [b for b in r.content if b.type == "tool_use"]
        if not llamadas:  # stop_reason != "tool_use": es la respuesta final
            return "".join(b.text for b in r.content if b.type == "text")
        resultados = []
        for llamada in llamadas:
            resultado = ejecutar_herramienta(llamada.name, llamada.input, metricas)  # input ya es dict
            resultados.append({
                "type": "tool_result",
                "tool_use_id": llamada.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })
        # Todos los resultados van juntos en un único mensaje "user"
        mensajes.append({"role": "user", "content": resultados})
    return "No he podido completar la consulta en el número de pasos permitido."


if __name__ == "__main__":
    for i, p in enumerate(PREGUNTAS, 1):
        print(f"\n=== Pregunta {i}: {p}")
        print(preguntar_claude(p))
