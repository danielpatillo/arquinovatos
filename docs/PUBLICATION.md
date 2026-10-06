# Publicación y registro en Manager

El repositorio público del pack es [danielpatillo/arquinovatos](https://github.com/danielpatillo/arquinovatos). Hugging Face conserva los GGUF de sus propietarios; el pack referencia sus revisiones y hashes y no redistribuye los pesos.

## Estado de v0.0.03

**Distribución v0.0.03 (paquete Python 0.0.3).** GitHub aloja las fuentes, workflows, pruebas y licencias de esta entrega. Pasaron 14/14 casos funcionales API y los controles efectivos de las diez inferencias. La revisión del contenido aceptó 9/10 salidas y conserva el fallo restante: no se acredita fidelidad completa del LLM. Los resultados se explican en [VALIDATION.md](VALIDATION.md). Para fijar la entrega utiliza su commit en el historial del repositorio; los informes privados de publicación/descarga y hashes de esta máquina se conservan fuera del paquete.

El paquete público verificado anteriormente corresponde a **v0.0.02**. Su código funcional se publicó en [1fea90f](https://github.com/danielpatillo/arquinovatos/commit/1fea90f673644019990f1831c7a762d215c5c5cb), seguido de documentación en [d3ae5e4](https://github.com/danielpatillo/arquinovatos/commit/d3ae5e4c5fd8ffffd84d10fa590f3c86d66271cf). La descarga anónima de ese paquete coincidió con los 25 archivos revisados; los resultados históricos se explican en [VALIDATION.md](VALIDATION.md).

## Búsqueda pública en Manager

La solicitud de incorporación es [ComfyUI-Manager PR #3353](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3353). Sigue pendiente de aceptación del catálogo; un repositorio descargable o una PR abierta no acreditan que el pack aparezca en la búsqueda pública. La nueva iteración mantiene el mismo repositorio y la compatibilidad de los nodos anteriores.

El archivo `node_list.json` describe el nuevo `Arquinovatos_LLM_Model` y los nodos conservados. No hace falta abrir una solicitud duplicada para cambiar la versión del mismo pack.

Las vías oficiales son:

1. **Catálogo de Manager:** aceptación de la PR y actualización del catálogo/cache por los usuarios. [Instrucciones oficiales](https://github.com/Comfy-Org/ComfyUI-Manager#how-to-register-your-custom-node-into-comfyui-manager).
2. **Comfy Registry:** crear o utilizar un editor real, fijar `PublisherId` y publicar mediante su clave. No se ha publicado una versión en Registry ni se incluye una clave en el paquete. [Guía oficial](https://docs.comfy.org/registry/publishing).

La instalación manual por Git URL depende de las funciones habilitadas en Manager y puede utilizarse mientras se tramita la incorporación. Colocar el pack dentro de `ComfyUI/custom_nodes` y reiniciar también permite instalarlo.

## Separar los estados al informar

| Estado | Evidencia necesaria |
|---|---|
| Preparado localmente | Código/documentación presentes |
| Funcionalidad validada v0.0.03 | Informes nuevos de backend, interfaz y ejecución real; revisión semántica con fallos y límites visibles |
| Publicado v0.0.03 | Commit público y descarga que coincida con sus fuentes |
| Incorporado al catálogo | PR aceptada o versión Registry aprobada |
| Encontrado en Manager | Búsqueda observable tras actualizar el catálogo |

Los hashes y datos privados de esta máquina se conservan fuera del repositorio público. No añadir modelos, binarios, registros o configuración local al ZIP de código.
