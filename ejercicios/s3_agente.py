"""Sesión 3. Un agente desde cero: bucle, límite de pasos, trazas y aprobación humana.

Proveedor: Claude (Messages API). El patrón es idéntico con OpenAI o Gemini."""
import json
import os
from dataclasses import dataclass
from typing import Callable

import anthropic
from dotenv import load_dotenv

from herramientas import DEFINICIONES, FUNCIONES

load_dotenv()


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    esquema: dict
    funcion: Callable
    requiere_aprobacion: bool = False


def preguntar_en_consola(nombre: str, args: dict) -> bool:
    return input(f"  ¿Aprobar {nombre}({args})? [s/N] ").strip().lower() == "s"


class Agente:
    def __init__(self, sistema: str, herramientas: list[Herramienta], max_pasos: int = 8,
                 aprobador: Callable[[str, dict], bool] = preguntar_en_consola,
                 verbose: bool = True):
        self.llm = anthropic.Anthropic(max_retries=3)
        self.modelo = os.environ["ANTHROPIC_MODEL"]
        self.sistema, self.max_pasos = sistema, max_pasos
        self.herramientas = {h.nombre: h for h in herramientas}
        self.aprobador, self.verbose = aprobador, verbose
        # Métricas de la última ejecución (P4: medir cuánto cuesta el camino agéntico)
        self.llamadas = self.tokens_entrada = self.tokens_salida = 0
        self.traza: list[str] = []

    def _log(self, linea: str):
        self.traza.append(linea)
        if self.verbose:
            print(linea)

    def _definiciones(self) -> list[dict]:
        return [{"name": h.nombre, "description": h.descripcion, "input_schema": h.esquema}
                for h in self.herramientas.values()]

    def _ejecutar(self, nombre: str, args: dict) -> tuple[object, bool]:
        """Devuelve (resultado, es_error). Los errores vuelven al modelo para que se corrija."""
        h = self.herramientas.get(nombre)
        if h is None:
            return f"La herramienta {nombre} no existe.", True
        if h.requiere_aprobacion and not self.aprobador(nombre, args):
            return "Un operador humano ha rechazado esta acción. No la repitas.", True
        try:
            salida = h.funcion(**args)
        except Exception as e:  # argumentos inventados, fallo de BD...
            return f"Error al ejecutar {nombre}: {e}", True
        # Errores de negocio devueltos como dato ({"error": ...}) también se marcan como error
        return salida, isinstance(salida, dict) and "error" in salida

    def ejecutar(self, objetivo: str) -> str:
        self.llamadas = self.tokens_entrada = self.tokens_salida = 0
        self.traza = []
        mensajes: list = [{"role": "user", "content": objetivo}]
        for paso in range(1, self.max_pasos + 1):
            r = self.llm.messages.create(
                model=self.modelo, max_tokens=2048, system=self.sistema,
                tools=self._definiciones(), messages=mensajes,
            )
            self.llamadas += 1
            self.tokens_entrada += r.usage.input_tokens
            self.tokens_salida += r.usage.output_tokens
            mensajes.append({"role": "assistant", "content": r.content})
            if r.stop_reason != "tool_use":  # condición de parada: respuesta final
                return "".join(b.text for b in r.content if b.type == "text")
            resultados = []
            for bloque in r.content:
                if bloque.type == "text" and bloque.text.strip():
                    self._log(f"[paso {paso}] razonamiento visible: {bloque.text.strip()[:100]}")
                if bloque.type != "tool_use":
                    continue
                salida, es_error = self._ejecutar(bloque.name, bloque.input)
                marca = " (ERROR)" if es_error else ""
                self._log(f"[paso {paso}] {bloque.name}({bloque.input}) -> {str(salida)[:90]}{marca}")
                resultados.append({
                    "type": "tool_result", "tool_use_id": bloque.id, "is_error": es_error,
                    "content": json.dumps(salida, ensure_ascii=False, default=str),
                })
            mensajes.append({"role": "user", "content": resultados})
        self._log(f"[límite] {self.max_pasos} pasos agotados")
        return "He alcanzado el límite de pasos sin terminar. Paso el caso a una persona."


SISTEMA = """Eres el agente de atención técnica de Tostadero Retiro S.L.
Objetivo: resolver correos de clientes usando las herramientas.
Procedimiento:
1. Identifica al cliente con buscar_cliente antes de usar su id.
2. Si hay una avería, registra una incidencia con la prioridad adecuada
   (alta si el local no puede servir café).
3. Si preguntan por pedidos, consulta los datos reales; no inventes cifras.
4. Termina con una respuesta breve al cliente, en español y con tono cordial."""


def crear_herramientas(definiciones: list[dict] = DEFINICIONES) -> list[Herramienta]:
    return [
        Herramienta(d["name"], d["description"], d["parameters"], FUNCIONES[d["name"]],
                    requiere_aprobacion=(d["name"] == "crear_incidencia"))
        for d in definiciones
    ]


if __name__ == "__main__":
    agente = Agente(SISTEMA, crear_herramientas())
    correo = ("Buenas, os escribo del Restaurante Lumbre. La cafetera de dos grupos no "
              "calienta y hoy no podemos servir cafés. ¿Además, cuándo llega el pedido pendiente?")
    print(agente.ejecutar(correo))
    print(f"\n[métricas] {agente.llamadas} llamadas, "
          f"{agente.tokens_entrada} tokens de entrada, {agente.tokens_salida} de salida")
