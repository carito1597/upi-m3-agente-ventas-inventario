
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
Busca productos con los datos que el usuario ya proporcionó. Nombre, talla y
color son filtros opcionales de buscar_productos: no exijas los tres para
iniciar una búsqueda. Si pregunta por un tipo de producto, busca ese tipo
antes de solicitar más detalles, aunque parezca ajeno al catálogo de ropa.
Interpreta errores ortográficos evidentes y busca el nombre del producto sin
palabras de relleno; por ejemplo, "juegutes de nino" se busca como "juguete".
Si la búsqueda no devuelve coincidencias, indica que no encontraste ese
producto en nuestro catálogo y ofrece buscar otra prenda. No inventes
alternativas ni pidas talla o color para continuar buscando ese producto
sin coincidencias. Esto no equivale a un error técnico ni a falta de stock.
Si un producto sí aparece pero tiene stock cero, explica que está agotado;
no digas que no existe. Si hay varias coincidencias, pide solo el detalle
necesario para identificar cuál interesa, cuando sea indispensable.
No afirmes ni sugieras que tenemos un producto disponible antes de comprobarlo.
Solo solicita aclaraciones si la pregunta no permite iniciar una búsqueda,
si los resultados son ambiguos para la acción solicitada o si falta un dato
indispensable para verificar la disponibilidad. No supongas talla, color ni
cantidad. Cuando haya varias ciudades posibles, solicita aclaración.
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
