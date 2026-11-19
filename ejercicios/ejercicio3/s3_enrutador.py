"""Sesión 3 · P4. Enrutador: las consultas van por un LLM barato y el resto al agente.

Uso: python s3_enrutador.py"""
import os

import openai
from dotenv import load_dotenv

from herramientas import _consulta
from llm_client import LLM
from s2_extraer_correo import SISTEMA as SISTEMA_EXTRACCION, CorreoClasificado
from s3_agente import SISTEMA, Agente, crear_herramientas

load_dotenv()

CATALOGO = "\n".join(f"- {p['nombre']} ({p['sku']}): {p['precio']:.2f} €"
                     for p in _consulta("SELECT sku, nombre, precio FROM productos"))

SISTEMA_CONSULTAS = f"""Eres el servicio de atención al cliente de Tostadero Retiro S.L., un
tostadero de Madrid que vende café y máquinas a bares, restaurantes, hoteles y cafeterías.
Respondes consultas generales en un solo mensaje: breve (máximo 4 frases), en español,
cordial y tuteando al cliente.

Lo único que sabes del negocio es este catálogo con precios sin IVA:
{CATALOGO}

Reglas:
- Usa solo la información de arriba. No inventes horarios, plazos, políticas ni precios.
- Si la consulta necesita datos de su cuenta (pedidos, facturas, entregas, incidencias)
  o información que no tienes, di que lo pasas al equipo y que le responderán hoy.
- Si el correo describe una avería o un pedido, no lo gestiones: di que lo pasas al equipo."""

# USD por millón de tokens (entrada, salida), precios de OpenRouter
PRECIOS = {"openai/gpt-5.4-mini": (0.75, 4.5), "anthropic/claude-haiku-4.5": (1.0, 5.0),
           "google/gemini-3.8-flash": (0.825, 4.125), "openai/gpt-5.4-nano": (0.2, 1.25)}

agente = Agente(SISTEMA, crear_herramientas(), aprobador=lambda nombre, args: True, verbose=False)


def clasificar(correo: str):
    # igual que con_openai de la sesión 2, pero devolviendo también los tokens
    r = openai.OpenAI(max_retries=3).responses.parse(
        model=os.environ["OPENAI_MODEL"], instructions=SISTEMA_EXTRACCION, input=correo,
        text_format=CorreoClasificado,
    )
    return r.output_parsed, r.usage.input_tokens, r.usage.output_tokens


def atender(correo: str, barato: LLM) -> dict:
    clasificacion, t_in, t_out = clasificar(correo)
    gasto = {os.environ["OPENAI_MODEL"]: [1, t_in, t_out]}
    if clasificacion.tipo == "consulta":
        r = barato.responder(SISTEMA_CONSULTAS, correo)
        gasto[barato.modelo] = [1, r.tokens_entrada, r.tokens_salida]
        return {"tipo": clasificacion.tipo, "camino": "barato", "texto": r.texto, "gasto": gasto}
    texto = agente.ejecutar(correo)
    gasto[agente.modelo] = [agente.llamadas, agente.tokens_entrada, agente.tokens_salida]
    return {"tipo": clasificacion.tipo, "camino": "agente", "texto": texto, "gasto": gasto}


def solo_agente(correo: str) -> dict:
    texto = agente.ejecutar(correo)
    return {"texto": texto,
            "gasto": {agente.modelo: [agente.llamadas, agente.tokens_entrada, agente.tokens_salida]}}


def total(gastos: list[dict]) -> tuple[int, int, int, float]:
    llamadas = t_in = t_out = 0
    usd = 0.0
    for gasto in gastos:
        for modelo, (n, i, o) in gasto.items():
            llamadas, t_in, t_out = llamadas + n, t_in + i, t_out + o
            p_in, p_out = PRECIOS.get(modelo, (0, 0))
            usd += (i * p_in + o * p_out) / 1e6
    return llamadas, t_in, t_out, usd


CASOS = [
    ("Necesito 20 kg del blend de hostelería para el viernes. Bar La Esquina.", "pedido"),
    ("El molino hace un ruido raro desde ayer, ¿podéis venir? Panadería Ibiza", "incidencia"),
    ("¿Tenéis café descafeinado de especialidad?", "consulta"),
    ("Mandadme 5 kg de Etiopía y, de paso, la cafetera gotea. Lumbre.", "mixto"),
    ("URGENTE: sin café para mañana, 10 kg de blend. Hotel Prado Suites", "pedido"),
    ("Buenas, ¿la factura de septiembre ya está emitida?", "consulta"),
    ("¿Qué precio tiene la cafetera de dos grupos?", "consulta"),
    ("¿Hacéis envíos fuera de Madrid?", "consulta"),
    ("¿Revisáis las máquinas en agosto?", "consulta"),
    ("Hola, ¿qué orígenes de café en grano tenéis ahora mismo?", "consulta"),
    ("Hotel Prado Suites: ¿cuándo llega nuestro último pedido?", "consulta"),
    ("La cafetera de Cafetería Atocha 12 pierde presión y el café sale aguado.", "incidencia"),
]

if __name__ == "__main__":
    baratos = [LLM("gemini"), LLM("openai", modelo="openai/gpt-5.4-nano")]
    resultados = {b.modelo: [] for b in baratos}
    base = []

    for i, (correo, esperado) in enumerate(CASOS, 1):
        print(f"\n### Caso {i} (esperado: {esperado}): {correo}")
        b = solo_agente(correo)
        base.append(b)
        print(f"  [solo agente] {b['gasto']}\n    {b['texto'][:160]!r}")
        for barato in baratos:
            r = atender(correo, barato)
            resultados[barato.modelo].append(r)
            print(f"  [enrutador · {barato.modelo}] tipo={r['tipo']} camino={r['camino']} "
                  f"{r['gasto']}\n    {r['texto'][:160]!r}")

    print("\nEstrategia                                llamadas  entrada  salida      USD")
    filas = [("Todo al agente", [b["gasto"] for b in base])]
    filas += [(f"Enrutador (barato = {m})", [r["gasto"] for r in rs]) for m, rs in resultados.items()]
    for nombre, gastos in filas:
        n, t_in, t_out, usd = total(gastos)
        print(f"{nombre:40} {n:9} {t_in:8} {t_out:7} {usd:8.5f}")

    rs = resultados[baratos[0].modelo]
    print("\nClasificación:", sum(r["tipo"] == e for r, (_, e) in zip(rs, CASOS)), f"/ {len(CASOS)}")
    print("Por el camino barato:", sum(r["camino"] == "barato" for r in rs), f"/ {len(CASOS)}")
