"""Sesión 4 · P2. Qué hay guardado en hilos.db y memoria.db."""
import json
import sqlite3
from pathlib import Path

if Path("hilos.db").exists():
    con = sqlite3.connect("hilos.db")
    hilos = con.execute("SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id").fetchall()
    print(f"hilos.db · tabla checkpoints ({len(hilos)} hilos):")
    for hilo, n in hilos:
        print(f"   {hilo:15} {n:3} checkpoints")

if Path("memoria.db").exists():
    con = sqlite3.connect("memoria.db")
    filas = con.execute("SELECT prefix, key, value FROM store ORDER BY prefix, key").fetchall()
    print(f"memoria.db · tabla store ({len(filas)} elementos):")
    for prefijo, clave, valor in filas:
        print(f"   {prefijo:12} {clave:25} {json.loads(valor)}")
