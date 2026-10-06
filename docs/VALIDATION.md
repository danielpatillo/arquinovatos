# Validación y límites — v0.0.03

**Estado de esta iteración: funcionalidad validada localmente, con una limitación semántica comprobada.** Estos resultados no acreditan fidelidad completa de las respuestas del LLM. Los resultados de v0.0.02 se mantienen como antecedentes separados.

## Comprobaciones locales de v0.0.03

Fecha: 6 de octubre de 2026. Se reutilizaron los tres GGUF y el motor CUDA ya instalados, sin descargar nuevos modelos.

| Comprobación | Resultado y alcance |
|---|---|
| Backend | 48/48 pruebas unitarias |
| Interfaz en DOM Chromium | 22/22 casos; transporte de generación simulado, cola real comprobada por separado |
| Matriz API real | 14/14 casos funcionales: diez inferencias, tres preparaciones con modelos existentes y un error esperado por ruta manual inexistente |
| Ajustes efectivos | 10/10 inferencias: normal 768/0,15/4096; avanzado 512/0,05/8192 |
| Restablecimiento con avanzado desactivado | Valores editados 512/0,95/8192 ignorados; valores efectivos 768/0,15/4096 tras la ejecución avanzada |
| Revisión independiente del contenido | 9/10 salidas aceptadas; una rechazada por una condición nueva incompatible con la casa |
| Fin de generación y recursos | Las diez inferencias terminaron con `finish_reason=stop` y registraron cierre del servidor |
| Botones en ComfyUI real | **Mejorar prompt** generó y **Copiar prompt mejorado** produjo texto idéntico mediante pegar y comparar los valores del campo |

El nodo combinado, su selector único, las opciones manuales agrupadas y el interruptor avanzado se verificaron también en la interfaz real. La copia se comprobó pulsando el botón, pegando el contenido en el campo del prompt mediante el navegador y comparando sus valores exactos; después se restauró la entrada original. La lectura de portapapeles de la herramienta había mostrado una muestra antigua, por lo que el informe conserva esa discrepancia y el método de comprobación real.

El caso rechazado es **Disabled advanced values ignored; defaults restored**. Aunque conservó explícitamente casa blanca, techo rojo, lago azul, exactamente tres pinos y las exclusiones originales, añadió «un entorno untouched por la civilización». Esa condición generaliza la ausencia de intervención humana y entra en conflicto con la casa requerida, además de introducir inglés en una respuesta solicitada en español. Los parámetros y el restablecimiento funcionaron; el contenido no recibió aprobación completa.

Las peticiones completas para permitir personas y añadir únicamente «sin vehículos» sí conservaron los sujetos, colores, cantidades y las exclusiones solicitadas. El tren de plástico azul mantuvo exactamente dos vagones rojos sobre una mesa de madera. Qwen3.5-9B, Gemma4-E4B y el formato Booru conservaron los datos comprobados en sus muestras. Se registraron aparte advertencias de redacción, copia no literal de exclusiones, párrafo separado, «sin distracciones» y repetición del lago en Booru. La indicación «Procura 80 a 140 palabras» es orientación, no una garantía de longitud.

Los informes locales `live_verification.json` y `pack_semantic_review.json` conservan entradas, instrucciones, respuestas, parámetros y el veredicto por caso. SHA256 del informe API revisado: `a99520f415335a10e06eb6fab22133e4378b2992093e37483d4dd8ad6faec70f`. Las matrices iniciales fallidas también se preservan. No se repitieron generaciones para ocultar una muestra, ni se añadió otra llamada al LLM o un filtro semántico posterior.

## Contrato funcional comprobado

- Nodo combinado `Arquinovatos_LLM_Model`, mostrado como **(Down)load LLM model by Arquinovatos**, con selector como única entrada obligatoria.
- Reutilización del catálogo y preparación automática de un GGUF/motor ausente al ejecutar; ningún efecto de descarga al importar.
- Opciones manuales agrupadas y opcionales; una ruta inválida debe producir un error explícito sin cambiar de modelo.
- `ajustes_avanzados=false` ignora los tres widgets; activado aplica valores solo por ejecución.
- `tokens_maximos=768` en 128–2048, `creatividad=0.15` en 0–1 y `contexto=4096` en 2048–8192.
- Contexto y límite de salida validados juntos, sin aceptar respuestas cortadas; los ajustes por ejecución no reescriben la configuración privada.
- Modelos, plantillas, calentamiento y cierre del motor preservados; nodos/workflows anteriores compatibles.
- Nuevos workflows básico y avanzado, interfaz desplegable y textos ajustables.

La adquisición de GGUF/motor ausentes por el nodo combinado se cubre en las pruebas del backend; la matriz real de esta iteración reutilizó archivos existentes. La transferencia real y la comprobación SHA de los archivos del mismo catálogo pertenecen a v0.0.02, descrita abajo. No se cuentan como una nueva descarga de v0.0.03.

## Antecedentes confirmados de v0.0.02

El entorno anterior fue Windows x64, RTX 5090 Laptop de aproximadamente 24 GB VRAM, Python 3.12.10, Torch 2.13.0+cu130, ComfyUI 0.39.0, frontend 1.53.10 y llama.cpp CUDA b11433. El modelo inicial fue Qwen3.5-4B Q4_K_M.

La iteración v0.0.02 obtuvo 39 pruebas unitarias de backend y 14 comprobaciones DOM. Una descarga real a carpeta vacía validó 2.707.513.696 bytes del GGUF 4B, SHA256 y cabecera GGUF; luego se ejecutó ese archivo mediante ruta manual. El instalador real preparó el motor en un destino aislado y confirmó versión/dispositivo CUDA.

En su matriz API se aceptaron 18/18 casos: catorce inferencias, tres usos de modelos cacheados y un error esperado por archivo inexistente. La revisión incluyó acción, sujetos, cantidades, colores, exclusiones, opciones, formatos y lente. La mediana local fue 136,53 tokens/s y 3,461 s totales. El botón real generó en 3,807 s y copió el texto exacto. Estas medidas pertenecen a aquellos prompts/equipo, no son promesas de rendimiento de v0.0.03.

El ZIP público anterior se descargó sin autenticación; coincidieron 25 archivos y pasaron sus 39 pruebas de backend. Los informes completos y las copias de intentos anteriores permanecen en documentación local, fuera del paquete público.

## Límites que siguen aplicando

El enhancer devuelve texto y no ejecuta Qwen Image ni MiniMax H3; tampoco analiza imágenes de referencia. Un GGUF manual debe ser un LLM de texto con arquitectura y plantilla compatibles con llama.cpp.

Los valores predeterminados son un punto de partida para el equipo de 24 GB VRAM. Contexto, buffers, otros modelos abiertos y longitud del prompt afectan la memoria y duración. Un techo de 768 tokens no es una cantidad objetivo; el contexto también cuenta la entrada. Reducir temperatura cambia la variación y no garantiza conservar literalmente todos los detalles.

Un LLM puede omitir o inventar datos, incluso con temperatura 0,15. Los diagnósticos de esta iteración favorecieron el valor inicial conservador en Qwen3.5-4B y las instrucciones completas/coherentes para editar exclusiones; no acreditan fidelidad universal. Revisar la salida sigue siendo necesario. Las correcciones explícitas de lente y el serializador Booru se auditan y no prueban fidelidad semántica universal. Las opciones vacías no deben añadir atributos.

Consultar la [guía para empezar](GUIA_LLM_PARA_EMPEZAR.md) y las fuentes primarias enlazadas allí. Para ejecutar las pruebas del código, usar `python -m unittest discover -s tests -v`. La revisión humana del prompt sigue siendo necesaria aunque pasen las pruebas funcionales.
