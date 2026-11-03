"""Sesión 2. Salidas estructuradas: de un correo libre a un objeto validado."""
import os
from typing import Literal

import anthropic
import openai
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from herramientas import buscar_cliente

load_dotenv()


class Linea(BaseModel):
    producto: str = Field(description="Producto tal y como lo menciona el cliente")
    cantidad: int = Field(description="Unidades o kilos pedidos")


class CorreoClasificado(BaseModel):
    tipo: Literal["pedido", "incidencia", "consulta", "mixto"]
    cliente: str | None = Field(description="Nombre del negocio si aparece; si no, null")
    lineas: list[Linea] = Field(description="Vacía si no hay pedido")
    urgente: bool
    resumen: str = Field(description="Una sola frase en español")


SISTEMA = "Extraes información de correos de clientes de un distribuidor de café para hostelería."


def con_openai(correo: str) -> CorreoClasificado:
    r = openai.OpenAI().responses.parse(
        model=os.environ["OPENAI_MODEL"], instructions=SISTEMA, input=correo,
        text_format=CorreoClasificado,
    )
    return r.output_parsed


def con_claude(correo: str) -> CorreoClasificado:
    r = anthropic.Anthropic().messages.parse(
        model=os.environ["ANTHROPIC_MODEL"], max_tokens=1024, system=SISTEMA,
        messages=[{"role": "user", "content": correo}],
        output_format=CorreoClasificado,
    )
    return r.parsed_output


def con_gemini(correo: str) -> CorreoClasificado:
    if os.getenv("GEMINI_API_KEY"):  # opcional: API nativa de Gemini
        cliente = genai.Client()  # en una variable: si no, el SDK cierra el cliente antes de usarlo
        r = cliente.interactions.create(
            model=os.environ["GEMINI_MODEL"].removeprefix("google/"),
            system_instruction=SISTEMA, input=correo,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": CorreoClasificado.model_json_schema(),
            },
        )
        return CorreoClasificado.model_validate_json(r.output_text)
    # Por defecto, vía OpenRouter con Chat Completions
    cliente = openai.OpenAI(base_url="https://openrouter.ai/api/v1",
                            api_key=os.environ["OPENROUTER_API_KEY"])
    r = cliente.chat.completions.parse(
        model=os.environ["GEMINI_MODEL"],
        messages=[{"role": "system", "content": SISTEMA}, {"role": "user", "content": correo}],
        response_format=CorreoClasificado,
    )
    return r.choices[0].message.parsed

# Conjunto de evaluación: (correo, tipo esperado). 18 casos, con ironía, dos clientes,
# inglés, sin nombre de negocio y clientes que no existen en la BD.
CASOS = [
    # Casos del kit
    ("Necesito 20 kg del blend de hostelería para el viernes. Bar La Esquina.", "pedido"),
    ("El molino hace un ruido raro desde ayer, ¿podéis venir?", "incidencia"),
    ("¿Tenéis café descafeinado de especialidad?", "consulta"),
    ("Mandadme 5 kg de Etiopía y, de paso, la cafetera gotea. Lumbre.", "mixto"),
    ("URGENTE: sin café para mañana, 10 kg de blend. Hotel Prado Suites", "pedido"),
    ("Buenas, ¿la factura de septiembre ya está emitida?", "consulta"),
    # Ironía
    ("Genial, otra vez la cafetera sin presión. Me encanta empezar así el lunes. "
     "Cafetería Atocha 12", "incidencia"),
    ("Qué maravilla, se nos ha acabado el blend justo el sábado. Mandad 15 kg. "
     "Panadería Ibiza", "pedido"),
    # Dos clientes en el mismo correo
    ("Desde Bar La Esquina, y en nombre también del Restaurante Lumbre: queremos 10 kg "
     "de blend cada uno.", "pedido"),
    # En inglés
    ("Hi, this is Hotel Prado Suites. Our grinder stopped working this morning and we "
     "can't serve coffee. Can someone come today?", "incidencia"),
    ("Do you ship decaf beans outside Madrid?", "consulta"),
    # Sin nombre de negocio
    ("Necesito 3 kg de Etiopía para mañana.", "pedido"),
    ("URGENTE: la máquina echa humo por detrás.", "incidencia"),
    # Clientes que no están en la BD (deben saltar la alerta)
    ("Somos Café Central, queremos 8 kg de blend para el lunes.", "pedido"),
    ("Cafetería Nube aquí: la cafetera pierde agua por abajo.", "incidencia"),
    # Ambiguos
    # Etiqueta corregida tras la 1.ª ejecución: pregunta + pedido es "mixto", no "pedido"
    ("¿Cuánto cuesta el descafeinado? Y apuntadme 2 kg. Bar La Esquina", "mixto"),
    ("¿Qué precio tiene la cafetera de 2 grupos?", "consulta"),
    ("Lumbre: el pedido de ayer llegó con una bolsa rota.", "incidencia"),
]


def validar_negocio(r: CorreoClasificado) -> list[str]:
    """El esquema garantiza la forma, no que tenga sentido. Devuelve los avisos."""
    avisos = [f"cantidad no válida: {l.producto} = {l.cantidad}"
              for l in r.lineas if l.cantidad <= 0]
    if r.cliente and not buscar_cliente(r.cliente):
        avisos.append(f"el cliente '{r.cliente}' no existe en la base de datos")
    return avisos


if __name__ == "__main__":
    for nombre, extraer in [("OpenAI", con_openai), ("Claude", con_claude), ("Gemini", con_gemini)]:
        aciertos, fallos = 0, []
        for i, (correo, esperado) in enumerate(CASOS, 1):
            try:
                resultado = extraer(correo)
            except Exception as e:  # salida estructurada vacía, error de red...
                fallos.append(f"caso {i}: error {type(e).__name__}: {e}")
                continue
            aciertos += resultado.tipo == esperado
            if resultado.tipo != esperado:
                fallos.append(f"caso {i}: esperado {esperado}, obtenido {resultado.tipo} "
                              f"({resultado.resumen})")
            for aviso in validar_negocio(resultado):
                print(f"  [{nombre}] caso {i}: AVISO {aviso}")
        print(f"{nombre}: {aciertos}/{len(CASOS)} tipos correctos")
        for f in fallos:
            print(f"    fallo {f}")
