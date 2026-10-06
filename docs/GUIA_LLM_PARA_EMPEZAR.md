# Empezar con un LLM para mejorar prompts — v0.0.03

Esta guía explica v0.0.03, cuya funcionalidad se ha validado localmente. Pasaron 14/14 casos API; la revisión del contenido aceptó 9/10 salidas y registró una contradicción inventada por el LLM. Revisa siempre la mejora. El código se distribuye en GitHub; las pruebas de v0.0.02 se conservan como antecedentes.

## Tu primera mejora

1. Abre el workflow `Arquinovatos_Cargar_Descargar_LLM_v0.0.03.json`.
2. En **(Down)load LLM model by Arquinovatos**, deja **Qwen3.5-4B**. La selección del modelo es su único campo obligatorio.
3. Mantén conectada su salida de modelo al Enhancer.
4. Escribe el prompt original y qué quieres mejorar. Por ejemplo: «Aclara la descripción en español. Conserva sujetos, cantidades, colores y exclusiones. Devuelve solo el prompt».
5. Deja **Ajustes avanzados** desactivado y los atributos opcionales en blanco.
6. Pulsa **Mejorar prompt**, revisa la salida y utiliza **Copiar prompt mejorado**.

Al ejecutar, el cargador reutiliza el modelo del catálogo si está instalado. Si falta, descarga ese GGUF y prepara el motor CUDA que falte. No descarga por abrir ComfyUI o por añadir el nodo. La primera ejecución puede tardar por la transferencia; después se reutilizan los archivos.

El modelo conectado tiene prioridad sobre el selector del Enhancer. El cargador prepara una referencia al archivo; la VRAM se ocupa cuando el Enhancer ejecuta la generación.

## Qué se descarga y qué solo se configura

| Elemento | ¿Se descarga o se configura? | Qué necesitas hacer |
|---|---|---|
| Modelo de texto GGUF | Se descarga una vez si falta el seleccionado del catálogo | Elegir Qwen3.5-4B para empezar |
| Motor llama.cpp para Windows x64/CUDA | Se descargan los binarios y sus DLL CUDA si faltan | Se prepara al ejecutar el cargador |
| Tokenizer: vocabulario y reglas para dividir texto | Sus datos vienen dentro del GGUF; el motor los utiliza | No descargar un tokenizer aparte para los modelos del catálogo |
| Plantilla de chat: cómo ordenar sistema/usuario/respuesta | Viene en los metadatos del GGUF recomendado | No buscar un archivo de plantilla aparte |
| Cuantización | Ya está aplicada al GGUF elegido | No hay un control que transforme el archivo mientras generas |
| Límite de salida, temperatura y contexto | Son ajustes por ejecución | Dejar los valores predeterminados hasta necesitar un cambio |
| Gestión de memoria y calentamiento | Los realiza el motor | No fijar manualmente una cantidad de VRAM ni activar un modo permanente |
| VAE, CLIP o proyector de imagen | Este enhancer de texto no los necesita | Pertenecen a otros flujos que generan o analizan imágenes |

GGUF permite guardar pesos y metadatos del tokenizer y de la plantilla de chat. Un archivo manual debe ser un LLM de texto compatible y tener una plantilla adecuada; que termine en `.gguf` no basta. [Especificación oficial GGUF](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md).

Este pack envía texto, no imágenes. La parte de lenguaje es suficiente para conversar; llama.cpp requiere componentes multimodales adicionales cuando una aplicación realmente introduce imagen/audio. Eso no ocurre aquí. [Documentación oficial de conversión y cuantización](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md).

## Los tres modelos ya incluidos en el catálogo

| Modelo | Archivo de cuantización | Descarga aproximada | Cuándo elegirlo |
|---|---|---|---|
| Qwen3.5-4B | Q4_K_M | 2,52 GiB | Opción inicial por rapidez |
| Qwen3.5-9B | Q4_K_M | 5,24 GiB | Comparar resultados cuando quieras dedicar más recursos |
| Gemma4-E4B | QAT Q4_0 | 4,80 GiB | Probar otra familia con el mismo prompt |

Los tamaños corresponden a los archivos del catálogo, no a toda la memoria usada al generar. No se han añadido modelos en esta iteración.

«4 bits» describe la familia de cuantización que reduce el tamaño de los pesos. En variantes como Q4_K_M puede haber tensores de otras precisiones; no significa exactamente cuatro bits para cada dato. Cambiar la cuantización exigiría otro archivo preparado previamente. El nodo no convierte ni recuantiza modelos. [Herramienta oficial de cuantización](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md).

Son modelos de pesos abiertos y mantienen sus licencias originales. La licencia MIT del pack no sustituye la de los pesos o las DLL. Consulta `catalog.json` y `THIRD_PARTY_NOTICES.md` del pack.

## Valores predeterminados para empezar

| Ajuste del Enhancer | Valor inicial | Rango de esta interfaz | Cuándo cambiarlo |
|---|---|---|---|
| Ajustes avanzados | Desactivado | Desactivado/activado | Activarlo solo para modificar los tres ajustes siguientes |
| Tokens máximos | 768 | 128–2048 | Aumentar si una respuesta necesaria se corta; reducir si quieres poner un techo menor |
| Creatividad / temperatura | 0,15 | 0–1 | Mantener para edición conservadora; aumentar si aceptas más alternativas |
| Contexto | 4096 | 2048–8192 | Aumentar cuando los textos de entrada y la salida reservada no caben |

Los predeterminados son el punto de partida elegido para este equipo de 24 GB de VRAM y prompts habituales. La memoria disponible también depende de lo que tenga cargado ComfyUI. El motor gestiona sus buffers; no hay una casilla que reserve una cantidad fija de VRAM. Un contexto mayor puede necesitar más memoria.

**Desactivar Ajustes avanzados hace que los tres valores de sus widgets se ignoren** y se use la configuración predeterminada/local. Activarlo los aplica solamente a esa ejecución; no modifica el GGUF ni reescribe la configuración privada.

### 768 tokens es un techo, no una petición de escribir 768

Un token es una unidad que usa el modelo para representar texto: puede ser una palabra, parte de una palabra o puntuación. No hay una conversión fija a palabras o caracteres. Si termina una respuesta útil antes, puede devolver muchos menos de 768 tokens. Para pedir concisión, escribe también «devuelve un prompt breve» en tus instrucciones.

El límite de salida controla lo nuevo que genera el LLM. El contexto incluye entrada y salida: instrucciones internas, plantilla, prompt original, tus instrucciones, opciones seleccionadas y respuesta. Un contexto de 4096 no permite añadir 4096 tokens de entrada y otros 768 de salida por encima. El pack cuenta la entrada y comunica el exceso o una respuesta incompleta. [Parámetros y límites del servidor llama.cpp](https://github.com/ggml-org/llama.cpp/blob/b11433/tools/server/README.md).

En JSON o Booru estructurado, el LLM también genera la estructura interna necesaria. El techo se aplica a esa generación, no al número de palabras de la línea que ves al final.

### Temperatura baja no garantiza que copie todos los detalles

La temperatura cambia la variación al escoger tokens. En esta iteración, Qwen3.5-4B empieza con 0,15 para edición conservadora. Menos variación no convierte al modelo en un comprobador literal ni asegura exactitud: incluso a 0,15 puede inventar una restricción o conservar una que pediste cambiar. Pide expresamente qué conservar y revisa cantidades, colores y exclusiones. Una temperatura de 0 tampoco sustituye esa revisión. [Documentación oficial del muestreo](https://github.com/ggml-org/llama.cpp/blob/b11433/tools/server/README.md).

En una muestra local, el original requería una casa y la respuesta añadió «un entorno untouched por la civilización». Los controles funcionaron, pero esa condición nueva contradice la casa y se rechazó en la revisión. Es un ejemplo concreto de por qué hay que comprobar el contenido, incluso cuando la ejecución termina correctamente.

El workflow `Arquinovatos_Mejora_Avanzada_v0.0.03.json` muestra un ejemplo con ajustes activados: temperatura 0,25, techo 1024 y contexto 4096. Es un ejemplo editable, no una promesa de mayor precisión.

## Cómo cambiar una regla del prompt

Escribe una petición completa y coherente en el campo **Prompt para que el LLM mejore el "prompt a mejorar"**. Si vas a cambiar una exclusión, reemplaza las instrucciones anteriores por la petición que describe ese cambio y lo que debe conservarse. Un modelo pequeño puede confundirse al mezclar una instrucción larga de copiar todas las exclusiones originales con otra que pide retirar una.

Por ejemplo, si el prompt original excluye personas y ahora quieres permitirlas, utiliza estas instrucciones completas:

```text
Mejora la descripción visual en español. Conserva la casa blanca, el techo rojo, el lago azul y exactamente tres pinos. Permite personas en la escena y no las prohíbas. Mantén sin texto y sin logotipos. No añadas otras prohibiciones. Devuelve solo el prompt mejorado.
```

Para añadir únicamente otra exclusión, puedes reemplazar el campo por:

```text
Mejora los detalles visuales en español, conservando los sujetos, colores y cantidades. Mantén sin personas, sin texto y sin logotipos. Añade únicamente una exclusión nueva: sin vehículos. Escribe todas estas exclusiones y no añadas otras. Devuelve solo el prompt mejorado.
```

La petición coherente facilita la edición, pero no garantiza el resultado. Comprueba que una regla retirada ya no aparezca, que las restantes sigan presentes y que no se añadan otras. La longitud orientativa del párrafo tampoco es un compromiso exacto del LLM.

## Calentar el modelo y liberar la memoria

llama.cpp hace por defecto un calentamiento breve al arrancar, mediante una ejecución vacía. Prepara el motor; no entrena el modelo ni mejora su conocimiento. El pack no necesita un botón para ello. [Opción oficial de warmup](https://github.com/ggml-org/llama.cpp/blob/b11433/tools/server/README.md).

El proceso se cierra después de cada generación por defecto y libera su VRAM. Por eso cada ejecución vuelve a incluir carga y calentamiento, además de generar texto. Los archivos descargados permanecen en disco para reutilizarlos. No se añade un control para dejarlo cargado permanentemente.

## Si ya tienes un GGUF en el PC

Abre la sección de opciones manuales del cargador y escribe una **ruta absoluta** al GGUF compatible. El perfil es opcional; deja `Automático` salvo que conozcas la compatibilidad del archivo.

Una ruta manual elegida debe existir y ser válida. Si es incorrecta, el nodo informa del problema: no sustituye tu modelo por otro ni inicia una descarga de un modelo diferente. Una ruta manual válida se comprueba antes de preparar un motor ausente.

Los nodos anteriores `Arquinovatos_Model_Loader` y `Arquinovatos_Model_Downloader` siguen disponibles para workflows existentes. Para empezar usa el nodo combinado.

## Formatos y atributos opcionales

Formato, estilo, lente, hora, composición, iluminación y paleta empiezan en blanco y no añaden instrucciones hasta que eliges un valor. Elige un formato para el generador al que llevarás el texto: el enhancer no ejecuta ese generador.

Las tres salidas son el prompt mejorado, la información de ejecución y los mensajes exactos utilizados para mejorar el prompt. Puedes revisar esos mensajes para entender qué se pidió al LLM.

Si no aparece el pack en la búsqueda pública de Manager, su [solicitud #3353](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3353) sigue pendiente de incorporación. El repositorio público es [danielpatillo/arquinovatos](https://github.com/danielpatillo/arquinovatos); consulta el estado de la versión en `docs/PUBLICATION.md`.
