
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
Responde en español.
Usa las herramientas para consultar catálogo, stock y ciudades.
No inventes precios, productos, existencias, cobertura de envío ni tarifas.
Pide aclaración si hay varias ciudades posibles.
No registres pedidos, cobres ni cambies inventario.
Si una herramienta falla, explícalo de forma breve.
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
            run_limit=5,
            exit_behavior="end"
        )
    ]
)


if __name__ == "__main__":
    resultado = agente.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Busca un vestido rojo talla M y verifica si hay 2 unidades disponibles."
                }
            ]
        },
        config={"recursion_limit": 15}
    )

    print(resultado["messages"][-1].content)
