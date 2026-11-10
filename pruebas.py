
from agente import agente
from langchain_core.messages import AIMessage
import sys

sys.stdout = open(
    "resultados_pruebas.txt",
    "w",
    encoding="utf-8"
)

casos = [
    {
        "consulta": "¿Tienes blusas negras talla M?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"]
    },
    {
        "consulta": "Busca un vestido rojo talla M y verifica si hay 2 unidades.",
        "debe_usar": ["buscar_productos", "consultar_stock"],
        "no_debe_usar": ["consultar_destino"]
    },
    {
        "consulta": "Busca la ciudad de Cochabamba en Bolivia.",
        "debe_usar": ["consultar_destino"],
        "no_debe_usar": ["consultar_stock"]
    },
    {
        "consulta": "¿Hay una chaqueta denim talla S disponible?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"]
    },
    {
        "consulta": "¿Tienes zapatos deportivos talla M?",
        "debe_usar": ["buscar_productos"],
        "no_debe_usar": ["consultar_destino"]
    }
]

aciertos = 0

for numero, caso in enumerate(casos, 1):
    print(f"\n--- CASO {numero} ---")
    print("Consulta:", caso["consulta"])

    try:
        resultado = agente.invoke(
            {"messages": [{"role": "user", "content": caso["consulta"]}]},
            config={"recursion_limit": 15}
        )

        utilizadas = [
            llamada["name"]
            for mensaje in resultado["messages"]
            if isinstance(mensaje, AIMessage)
            for llamada in mensaje.tool_calls
        ]

        cumple = (
            all(h in utilizadas for h in caso["debe_usar"])
            and all(h not in utilizadas for h in caso["no_debe_usar"])
        )

        if cumple:
            aciertos += 1

        print("Herramientas:", utilizadas)
        print("Respuesta:", resultado["messages"][-1].content)
        print("Evaluación:", "CORRECTO" if cumple else "INCORRECTO")

    except Exception as error:
        print("Error:", str(error))
        print("Evaluación: INCORRECTO")

porcentaje = aciertos / len(casos) * 100

print("\n=== RESULTADO FINAL ===")
print(f"Aciertos: {aciertos}/{len(casos)}")
print(f"Porcentaje: {porcentaje:.0f}%")
