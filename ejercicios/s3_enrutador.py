"""Sesión 3 · P4. Enrutador: un workflow barato delante del agente.

clasificar (s2) -> consulta  -> un LLM de una sola llamada (camino barato)
                -> el resto  -> el agente de s3 (camino caro, con herramientas)

Mide llamadas y tokens del enrutador frente a mandar todo al agente.
Uso: python s3_enrutador.py"""
import json
import os
import urllib.request

import openai
from dotenv import load_dotenv

from herramientas import _consulta
from llm_client import LLM
from s2_extraer_correo import SISTEMA as SISTEMA_EXTRACCION, CorreoClasificado
from s3_agente import SISTEMA, Agente, crear_herramientas

load_dotenv()


def _catalogo() -> str:
    return "\n".join(f"- {p['nombre']} ({p['sku']}): {p['precio']:.2f} €"
                     for p in _consulta("SELECT sku, nombre, precio FROM productos"))


SISTEMA_CONSULTAS = f"""Eres el servicio de atención al cliente de Tostadero Retiro S.L., un
tostadero de Madrid que vende café y máquinas a bares, restaurantes, hoteles y cafeterías.
Respondes consultas generales en un solo mensaje: breve (máximo 4 frases), en español,
cordial y tuteando al cliente.

Lo único que sabes del negocio es este catálogo con precios sin IVA:
{_catalogo()}

Reglas:
- Usa solo la información de arriba. No inventes horarios, plazos, políticas ni precios.
- Si la consulta necesita datos de su cuenta (pedidos, facturas, entregas, incidencias)
  o información que no tienes, di que lo pasas al equipo y que le responderán hoy.
- Si el correo describe una avería o un pedido, no lo gestiones: di que lo pasas al equipo."""

# Precio de la llamada de clasificación (sesión 2): con_openai devuelve solo el objeto, así que
# repetimos su misma llamada aquí para quedarnos también con r.usage.
def clasificar(correo: str) -> tuple[CorreoClasificado, int, int]:
    r = openai.OpenAI(max_retries=3).responses.parse(
        model=os.environ["OPENAI_MODEL"], instructions=SISTEMA_EXTRACCION, input=correo,
        text_format=CorreoClasificado,
    )
    return r.output_parsed, r.usage.input_tokens, r.usage.output_tokens


def aprobar_siempre(nombre, args):  # medición desatendida: en producción aquí va una persona
    return True


agente = Agente(SISTEMA, crear_herramientas(), aprobador=aprobar_siempre, verbose=False)


def atender(correo: str, barato: LLM) -> dict:
    """Devuelve la respuesta y el gasto por modelo: {modelo: [llamadas, t_in, t_out]}."""
    clasificacion, c_in, c_out = clasificar(correo)
    gasto = {os.environ["OPENAI_MODEL"]: [1, c_in, c_out]}
    if clasificacion.tipo == "consulta":  # camino barato y predecible
        r = barato.responder(SISTEMA_CONSULTAS, correo)
        gasto[barato.modelo] = [1, r.tokens_entrada, r.tokens_salida]
        return {"tipo": clasificacion.tipo, "camino": "barato", "texto": r.texto, "gasto": gasto}
    texto = agente.ejecutar(correo)  # camino agéntico para lo complejo
    gasto[agente.modelo] = [agente.llamadas, agente.tokens_entrada, agente.tokens_salida]
    return {"tipo": clasificacion.tipo, "camino": "agente", "texto": texto, "gasto": gasto,
            "traza": agente.traza}


def solo_agente(correo: str) -> dict:
    texto = agente.ejecutar(correo)
    return {"texto": texto, "traza": agente.traza,
            "gasto": {agente.modelo: [agente.llamadas, agente.tokens_entrada, agente.tokens_salida]}}


def precios_openrouter() -> dict[str, tuple[float, float]]:
    """USD por token (entrada, salida), leídos de la API pública de OpenRouter."""
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as f:
        datos = json.load(f)["data"]
    return {m["id"]: (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"]))
            for m in datos}


def resumir(gastos: list[dict], precios: dict) -> tuple[int, int, int, float]:
    llamadas = t_in = t_out = 0
    usd = 0.0
    for gasto in gastos:
        for modelo, (n, i, o) in gasto.items():
            llamadas, t_in, t_out = llamadas + n, t_in + i, t_out + o
            p_in, p_out = precios.get(modelo, (0.0, 0.0))
            usd += i * p_in + o * p_out
    return llamadas, t_in, t_out, usd


# Casos de la sesión 2 ampliados: (correo, tipo esperado)
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
    precios = precios_openrouter()
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

    print("\n" + "=" * 78 + "\nRESUMEN (12 correos)\n" + "=" * 78)
    print(f"{'Estrategia':40} {'llamadas':>8} {'tok entrada':>12} {'tok salida':>11} {'USD':>9}")
    filas = [("Todo al agente", [b["gasto"] for b in base])]
    filas += [(f"Enrutador (barato = {m})", [r["gasto"] for r in rs]) for m, rs in resultados.items()]
    for nombre, gastos in filas:
        n, i, o, usd = resumir(gastos, precios)
        print(f"{nombre:40} {n:8} {i:12} {o:11} {usd:9.5f}")

    rs = next(iter(resultados.values()))
    print("\nClasificación (con_openai):",
          sum(r["tipo"] == e for r, (_, e) in zip(rs, CASOS)), f"/ {len(CASOS)} tipos correctos")
    print("Correos por el camino barato:", sum(r["camino"] == "barato" for r in rs), f"/ {len(CASOS)}")
    print("\nSolo consultas (camino barato) — tokens de salida por modelo:")
    for modelo, rs in resultados.items():
        consultas = [r["gasto"][modelo] for r in rs if r["camino"] == "barato"]
        if consultas:
            print(f"  {modelo:28} {sum(c[2] for c in consultas):6} tokens de salida "
                  f"({sum(c[2] for c in consultas) / len(consultas):.0f} por consulta)")
