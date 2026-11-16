
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware


from herramientas import (
    buscar_productos,
    consultar_stock,
    consultar_destino
)

# Cargar la API Key desde .env
load_dotenv()

# Configurar el modelo
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    reasoning_effort="low",
    max_retries=2,
    model_kwargs={"parallel_tool_calls": False}
)

# Instrucciones del agente
instrucciones = """
Eres un asistente de ventas de ropa en Bolivia.
Responde siempre en español, de manera breve y precisa.
Consulta buscar_productos antes de informar productos, precios o existencias.
Usa consultar_stock para verificar la disponibilidad de un producto por su ID
y la cantidad solicitada. Basa tus afirmaciones únicamente en los resultados
de las herramientas y expresa todos los precios en bolivianos (Bs).
No inventes productos, precios, existencias, cobertura de envío ni tarifas.
Tu alcance es consultar el catálogo, la disponibilidad y las localidades.
No realices ni prometas registrar compras o pedidos, procesar pagos, reservar
productos, notificar reposiciones ni gestionar envíos. No cambies inventario.
Usa consultar_destino para buscar localidades mediante Open-Meteo.
Encontrar una ciudad solo confirma una coincidencia geográfica; no confirma
cobertura de envío, tarifas ni tiempos de entrega. No puedes verificar esos datos.
Si una herramienta devuelve un mensaje que comienza con ERROR:, explica
brevemente el problema en español, sin inventar resultados ni presentarlo como
una búsqueda sin coincidencias o como falta de stock.
Los productos agotados y las búsquedas sin coincidencias son resultados normales.
Solicita aclaraciones cuando falte información indispensable, cuando no puedas
identificar el producto o cuando haya varias ciudades posibles. No supongas
la talla, el color, la cantidad ni la ciudad si son necesarios para responder.
"""

# Crear agente ReAct

agente = create_agent(
    model=llm,
    tools=[
        buscar_productos,
        consultar_stock,
        consultar_destino
    ],
    system_prompt=instrucciones,
    middleware=[
        ModelCallLimitMiddleware(
            run_limit=int(os.getenv("MODEL_RUN_LIMIT", "5")),
            exit_behavior="end"
        ),
    ]
)



def ejecutar_consulta(consulta):
    """Consulta al agente sin pausas de aprobación para herramientas de lectura."""
    print("\nCONSULTA:", consulta, flush=True)
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": consulta}]},
        config={"recursion_limit": 15},
    )
    print("RESPUESTA:", resultado["messages"][-1].content)
    return resultado


if __name__ == "__main__":
    import sys

    consulta = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Busca un vestido rojo talla M y verifica si hay 2 unidades disponibles."
    )
    ejecutar_consulta(consulta)
