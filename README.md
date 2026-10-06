# Arquinovatos_Prompt_Enhancer

**v0.0.03 — funcionalidad validada localmente.** Versión de paquete Python: `0.0.3`. Mejora prompts con modelos de texto locales mediante llama.cpp. Pasaron 14/14 casos funcionales API; la revisión independiente aceptó 9/10 salidas por su contenido. Una salida añadió una condición que contradice la casa del prompt: revisa siempre el resultado. Los resultados y límites están en [VALIDATION.md](docs/VALIDATION.md).

## Empezar

Abre `workflows/Arquinovatos_Cargar_Descargar_LLM_v0.0.03.json`. En **(Down)load LLM model by Arquinovatos**, deja **Qwen3.5-4B**, conecta su modelo al Enhancer, escribe tu prompt e instrucciones y pulsa **Mejorar prompt**. El selector de modelo es el único campo obligatorio del cargador. Los ajustes avanzados del Enhancer empiezan desactivados.

Si falta el modelo del catálogo o el motor CUDA, se preparan al ejecutar el cargador. Los archivos ya instalados se reutilizan. Añadir un nodo o abrir ComfyUI no provoca descargas. El cargador no ocupa VRAM hasta que el Enhancer genera.

La [guía para principiantes](docs/GUIA_LLM_PARA_EMPEZAR.md) explica qué se descarga, qué significan los ajustes y cuándo modificarlos.

## Instalar

Clona el repositorio dentro de `custom_nodes` y reinicia ComfyUI:

```sh
git clone https://github.com/danielpatillo/arquinovatos ComfyUI/custom_nodes/Arquinovatos_Prompt_Enhancer
```

Para conservar una versión concreta, instala un commit de su historial. Consulta [PUBLICATION.md](docs/PUBLICATION.md). También puede usarse **Install via Git URL** si esa función está habilitada en tu Manager.

El backend Python usa la biblioteca estándar. La instalación automática del motor está preparada para **Windows x64 con NVIDIA CUDA**, mediante binarios oficiales fijados en `catalog.json`. En otras plataformas se necesita un llama-server compatible configurado manualmente; esta integración necesita un backend CUDA operativo. El equipo de referencia tiene 24 GB de VRAM.

## Nodos y compatibilidad

| Nodo | Uso |
|---|---|
| **(Down)load LLM model by Arquinovatos** (`Arquinovatos_LLM_Model`) | Carga el GGUF seleccionado o descarga el modelo del catálogo que falte; prepara un motor ausente |
| `Arquinovatos_Prompt_Enhancer` | Mejora el prompt y devuelve texto, información y mensajes efectivos |
| `Arquinovatos_Model_Loader` | Cargador anterior conservado para workflows existentes |
| `Arquinovatos_Model_Downloader` | Descargador anterior conservado para workflows existentes |

Conecta `modelo_llm` a `modelo_input` del Enhancer. El modelo conectado tiene prioridad sobre su selector.

Las opciones manuales del cargador están agrupadas y son opcionales. Una ruta manual tiene que apuntar a un GGUF de texto compatible existente; una ruta errónea produce un error y nunca cambia silenciosamente al modelo del catálogo. El perfil no convierte una arquitectura no compatible.

## Modelos y componentes

| Selección | GGUF del catálogo | Tamaño aproximado |
|---|---|---|
| **Qwen3.5-4B** — predeterminado por rapidez | Q4_K_M | 2,52 GiB |
| Qwen3.5-9B | Q4_K_M | 5,24 GiB |
| Gemma4-E4B | QAT Q4_0 | 4,80 GiB |

Se mantienen los tres modelos y sus licencias. `catalog.json` fija revisiones, URLs, tamaños y hashes. El GGUF ya está cuantizado e incluye los datos del tokenizer y la plantilla de chat necesarios para estos modelos. Este enhancer trabaja solo con texto: no descarga VAE, CLIP ni componentes de imagen.

## Ajustes avanzados

| Campo | Predeterminado | Rango del widget |
|---|---|---|
| `ajustes_avanzados` | `false` | Activado/desactivado |
| `tokens_maximos` | 768 | 128–2048 |
| `creatividad` | 0,15 | 0–1 |
| `contexto` | 4096 | 2048–8192 |

Con el interruptor desactivado, los tres widgets se ignoran y se usa la configuración predeterminada/local. Activado, sus valores afectan solo a esa ejecución; no reescriben la configuración.

768 es un límite de tokens nuevos, no una cantidad objetivo ni un número de palabras. El contexto incluye entrada y respuesta. La temperatura inicial 0,15 se elige para edición conservadora; bajar la temperatura reduce la variación, pero no garantiza fidelidad literal. Para cambiar reglas, escribe una petición completa y coherente en el campo de instrucciones. La [guía](docs/GUIA_LLM_PARA_EMPEZAR.md) muestra cómo permitir personas conservando las otras exclusiones.

En la prueba local, una respuesta describió un «entorno untouched por la civilización» aunque debía conservar una casa. Los controles de generación funcionaron, pero esa salida se rechazó por añadir una condición incompatible. No se oculta ni se corrige automáticamente esa muestra; la revisión humana de sujetos, cantidades, colores y exclusiones sigue siendo necesaria.

La memoria y el calentamiento se gestionan automáticamente. Por defecto el motor se cierra al terminar cada generación y en errores, liberando VRAM. No hay un control para mantenerlo cargado permanentemente.

## Controles del prompt

**Mejorar prompt** ejecuta el Enhancer y sus antecesores; **Copiar prompt mejorado** copia el resultado. Los campos de texto y la altura del nodo se ajustan al texto. La información y los mensajes efectivos se pueden desplegar.

Todos los atributos opcionales empiezan vacíos: formato, estilo, lente en mm, hora, composición, iluminación y paleta. Solo se aplican los que elijas. La corrección explícita de una lente numérica omitida se registra junto con la respuesta original del modelo.

Formatos disponibles:

- **Qwen Image 2511:** instrucciones de edición en lenguaje natural para [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511); el nodo no analiza una imagen de referencia.
- **MiniMax H3:** JSON con `integrated_multimodal_description`, `overall_soundscape` y `non_diegetic_music`, según la [guía oficial](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing). Sonido o música no pedidos quedan vacíos.
- **JSON estructurado:** esquema propio `{"prompt": "texto completo"}`.
- **Booru tags:** una única generación JSON interna separa sujetos, acciones, atributos, escena y exclusiones; el serializador produce etiquetas y conserva negaciones, sin otra llamada al LLM.
- **Lenguaje natural:** prosa. El valor en blanco y **Sin formato específico** no añaden instrucciones de formato.

Las salidas conectables son `prompt_mejorado`, `informacion` y `prompt_utilizado`. La última contiene los mensajes exactos enviados al LLM. Las evidencias se guardan en `output/Arquinovatos_Prompt_Enhancer` de ComfyUI. Revisa el resultado antes de utilizarlo.

## Workflows y configuración local

- `Arquinovatos_Cargar_Descargar_LLM_v0.0.03.json`: uso inicial con ajustes avanzados desactivados.
- `Arquinovatos_Mejora_Avanzada_v0.0.03.json`: ejemplo avanzado con temperatura 0,25, techo 1024 y contexto 4096.
- Se incluyen equivalentes `.api.json`.

Configuración privada: `ComfyUI/user/Arquinovatos_Prompt_Enhancer/runtime.local.json`, o un JSON indicado por `ARQUINOVATOS_LLM_CONFIG`. No es necesaria para una instalación inicial. Las rutas relativas se resuelven respecto de ese archivo; no publiques datos de tu equipo.

Código propio: MIT. Modelos, motor y DLL mantienen sus licencias, descritas en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). La incorporación a búsquedas públicas de Manager sigue en [PR #3353](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3353).

## English quick start

Use the v0.0.03 combined loader workflow, select Qwen3.5-4B, connect its model to the Enhancer, enter the original prompt and editing instructions, then click **Mejorar prompt**. Missing catalogue GGUF/CUDA runtime files are prepared on execution; an invalid manual path reports an error without falling back. Advanced generation controls default off. Local functionality passed 14/14 API cases; independent content review accepted 9/10 outputs. Review every output because the model can add incompatible restrictions.
