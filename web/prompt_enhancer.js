import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const ENHANCER = "Arquinovatos_Prompt_Enhancer";
const MODEL_NODE = "Arquinovatos_LLM_Model";
const PACK_NODES = new Set([ENHANCER, MODEL_NODE, "Arquinovatos_Model_Loader", "Arquinovatos_Model_Downloader"]);
const DOWNLOAD_NOTICE = "Si no tienes el modelo seleccionado, se descargará automáticamente al ejecutar. El motor también se instala si falta.";
const LABELS = {
    prompt_positivo: "Prompt positivo a mejorar",
    instrucciones: 'Prompt para que el LLM mejore el "prompt a mejorar"',
    modelo: "Selección de modelo", modelo_input: "Modelo cargado / descargado",
    modelo_archivo: "Modelo o archivo local", ruta_modelo: "Ruta a un GGUF del PC (opcional)",
    perfil: "Familia del modelo", instalar_motor: "Instalar motor si hace falta",
    formato_prompt: "Formato (opcional)", estilo: "Estilo (opcional)",
    lente_mm: "Lente en mm (opcional)", hora_dia: "Hora del día (opcional)",
    composicion: "Composición (opcional)", iluminacion: "Iluminación (opcional)",
    paleta_color: "Paleta de color (opcional)",
    ajustes_avanzados: "Ajustes avanzados", tokens_maximos: "Tokens máximos de salida",
    creatividad: "Creatividad", contexto: "Ventana de contexto",
};
const ADVANCED_TOOLTIPS = {
    tokens_maximos: "Límite de tokens de la respuesta. Más tokens permiten textos largos, pero aumentan el tiempo de generación.",
    creatividad: "Variación de la respuesta. Los valores bajos son más consistentes; los altos permiten más cambios.",
    contexto: "Capacidad total para instrucciones, prompt y respuesta. Un contexto mayor consume más memoria.",
};

/** Keep only the target and its input dependencies; never follow output links. */
export function buildTargetPrompt(output, targetId) {
    const target = String(targetId);
    if (!Object.hasOwn(output, target)) throw new Error("El nodo está desactivado o no está en el workflow ejecutable.");
    const kept = {};
    const pending = [target];
    while (pending.length) {
        const id = pending.pop();
        if (Object.hasOwn(kept, id)) continue;
        const entry = output[id];
        if (!entry) throw new Error(`Falta el nodo de entrada ${id}.`);
        kept[id] = entry;
        for (const value of Object.values(entry.inputs || {})) {
            if (Array.isArray(value) && value.length === 2 && Number.isInteger(value[1]) && Object.hasOwn(output, String(value[0]))) pending.push(String(value[0]));
        }
    }
    return kept;
}

function executionIdFor(node, output) {
    const root = app.rootGraph || app.graph;
    if (node.graph === root && Object.hasOwn(output, String(node.id))) return String(node.id);
    const matches = [];
    function walk(graph, path, seen) {
        if (!graph || seen.has(graph)) return;
        const visited = new Set([...seen, graph]);
        for (const candidate of graph.nodes || graph._nodes || []) {
            const candidatePath = [...path, String(candidate.id)];
            if (candidate === node) matches.push(candidatePath.join(":"));
            if (candidate.subgraph) walk(candidate.subgraph, candidatePath, visited);
        }
    }
    walk(root, [], new Set());
    const executable = matches.filter((id) => Object.hasOwn(output, id));
    if (executable.length !== 1) throw new Error("No se pudo identificar una única instancia ejecutable del nodo. Abre el workflow que contiene este nodo.");
    return executable[0];
}

function makeButton(text, title = text) {
    const element = document.createElement("button");
    element.type = "button"; element.textContent = text; element.title = title;
    Object.assign(element.style, { padding: "5px 9px", minHeight: "28px", cursor: "pointer", borderRadius: "4px", border: "1px solid var(--border-color, #555)", background: "var(--comfy-input-bg, #252525)", color: "var(--input-text, #eee)", font: "12px/1.35 sans-serif", flex: "1 1 auto" });
    element.addEventListener("pointerdown", (event) => { event.stopPropagation(); element.style.transform = "scale(.97)"; });
    for (const type of ["pointerup", "pointerleave", "pointercancel", "blur"]) element.addEventListener(type, () => { element.style.transform = ""; });
    return element;
}

function makeTextarea(label) {
    const element = document.createElement("textarea");
    element.readOnly = true; element.rows = 1; element.setAttribute("aria-label", label);
    Object.assign(element.style, { display: "block", width: "100%", minHeight: "0", resize: "none", boxSizing: "border-box", background: "var(--comfy-input-bg, #151515)", color: "var(--input-text, #eee)", font: "12px/1.4 monospace", padding: "6px 7px", border: "1px solid var(--border-color, #555)", borderRadius: "4px", overflowY: "hidden", overflowWrap: "anywhere", whiteSpace: "pre-wrap" });
    return element;
}

function createSizing(node) {
    if (node._arquinovatosSizing) return node._arquinovatosSizing;
    const sizing = { entries: [], frame: 0, removed: false, updating: false, expectedHeight: 0, observers: [] };
    const mirror = makeTextarea("Medición interna");
    mirror.removeAttribute("aria-label"); mirror.setAttribute("aria-hidden", "true"); mirror.tabIndex = -1;
    Object.assign(mirror.style, { position: "fixed", left: "-100000px", top: "0", visibility: "hidden", height: "0", pointerEvents: "none" });
    const block = document.createElement("div");
    Object.assign(block.style, { position: "fixed", left: "-100000px", top: "0", visibility: "hidden", height: "auto", overflowWrap: "anywhere", whiteSpace: "pre-wrap", pointerEvents: "none" });
    document.body.append(mirror, block);
    sizing.textHeight = (element, width) => {
        const style = getComputedStyle(element);
        for (const property of ["font", "lineHeight", "letterSpacing", "paddingTop", "paddingBottom", "paddingLeft", "paddingRight", "borderTopWidth", "borderBottomWidth", "borderLeftWidth", "borderRightWidth", "boxSizing", "wordBreak", "overflowWrap", "whiteSpace"]) mirror.style[property] = style[property];
        mirror.style.width = `${Math.max(80, width)}px`; mirror.style.height = "0"; mirror.value = element.value || " ";
        const height = Math.ceil(mirror.scrollHeight + (parseFloat(style.borderTopWidth) || 0) + (parseFloat(style.borderBottomWidth) || 0));
        element.style.height = `${Math.max(1, height)}px`;
        return Math.max(1, height);
    };
    sizing.blockHeight = (element, width) => {
        const style = getComputedStyle(element);
        Object.assign(block.style, { width: `${Math.max(80, width)}px`, font: style.font, lineHeight: style.lineHeight, letterSpacing: style.letterSpacing });
        block.textContent = element.textContent || " ";
        return Math.max(1, block.scrollHeight);
    };
    sizing.fix = (widget, height) => {
        widget.options ||= {};
        // Comfy's DOM host subtracts two margins from computedHeight. Layout
        // therefore requests content height PLUS those margins, not just content.
        const margin = widget.margin ?? widget.options.margin ?? 10;
        widget._arquinovatosHeight = height + margin * 2;
        widget.options.getMinHeight = widget.options.getMaxHeight = widget.options.getHeight = () => widget._arquinovatosHeight;
        widget.options.minNodeSize = [280, 0];
    };
    sizing.layout = () => {
        sizing.frame = 0;
        if (sizing.removed || sizing.updating) return;
        sizing.updating = true;
        try {
            for (const entry of sizing.entries) if (entry.widget.type !== "hidden" && !entry.widget.hidden) entry.measure(Math.max(80, (node.size?.[0] || 440) - 20));
            const height = Math.ceil(node.computeSize()[1]);
            sizing.expectedHeight = height;
            if (Math.abs((node.size?.[1] || 0) - height) > 1) node.setSize([node.size[0], height]);
            node.setDirtyCanvas(true, true);
        } finally { sizing.updating = false; }
    };
    sizing.schedule = () => { if (!sizing.removed && !sizing.frame) sizing.frame = requestAnimationFrame(sizing.layout); };
    sizing.observe = (element) => {
        const observer = new ResizeObserver((entries) => {
            const width = entries[0]?.contentRect.width;
            const height = entries[0]?.contentRect.height;
            if (width && (Math.abs((element._arquinovatosWidth || 0) - width) > .5 || Math.abs((element._arquinovatosObservedHeight || 0) - height) > .5)) {
                element._arquinovatosWidth = width;
                element._arquinovatosObservedHeight = height;
                sizing.schedule();
            }
        });
        observer.observe(element); sizing.observers.push(observer);
    };
    const removed = node.onRemoved;
    node.onRemoved = function () {
        sizing.removed = true;
        if (sizing.frame) cancelAnimationFrame(sizing.frame);
        sizing.observers.forEach((observer) => observer.disconnect()); mirror.remove(); block.remove();
        return removed?.apply(this, arguments);
    };
    for (const method of ["onResize", "onConfigure", "onAdded"]) {
        const previous = node[method];
        node[method] = function () { const result = previous?.apply(this, arguments); sizing.schedule(); return result; };
    }
    node._arquinovatosSizing = sizing;
    return sizing;
}

function labelMultilineInput(node, widget) {
    const input = widget.element;
    if (!(input instanceof HTMLTextAreaElement) || !LABELS[widget.name] || widget._arquinovatosInput) return;
    const sizing = createSizing(node);
    const uniqueId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    input.setAttribute("aria-label", LABELS[widget.name]); input.id ||= `arquinovatos-${uniqueId}`; input.rows = 1;
    Object.assign(input.style, { display: "block", flex: "0 0 auto", minHeight: "0", resize: "none", width: "100%", boxSizing: "border-box", overflowY: "hidden", overflowWrap: "anywhere", whiteSpace: "pre-wrap" });
    const wrapper = document.createElement("div");
    Object.assign(wrapper.style, { display: "flex", flexDirection: "column", gap: "4px", width: "100%", height: "auto", boxSizing: "border-box", padding: "2px", color: "var(--input-text, #eee)" });
    const label = document.createElement("label"); label.htmlFor = input.id; label.textContent = LABELS[widget.name];
    Object.assign(label.style, { flex: "0 0 auto", font: "12px/1.35 sans-serif", overflowWrap: "anywhere" });
    wrapper.append(label, input); widget.element = wrapper; widget._arquinovatosInput = input;
    // Preserve ComfyUI's original store-backed values, serialization and input bindings.
    const oldSet = widget.options.setValue;
    widget.options.setValue = function (value) { const result = oldSet?.call(this, value); sizing.schedule(); return result; };
    input.addEventListener("input", sizing.schedule);
    sizing.fix(widget, 54);
    sizing.entries.push({ widget, measure(width) { sizing.fix(widget, sizing.textHeight(input, width - 4) + sizing.blockHeight(label, width - 4) + 8); } });
    sizing.observe(wrapper);
}

function nativeWidgetVisibility(widget, visible) {
    if (!widget._arquinovatosVisibility) {
        widget._arquinovatosVisibility = {
            type: widget.type, hidden: widget.hidden,
            ownCompute: Object.hasOwn(widget, "computeSize"), computeSize: widget.computeSize,
            ownHeight: Object.hasOwn(widget, "computedHeight"), computedHeight: widget.computedHeight,
        };
    }
    const original = widget._arquinovatosVisibility;
    if (visible) {
        widget.type = original.type;
        widget.hidden = original.hidden;
        if (original.ownCompute) widget.computeSize = original.computeSize;
        else delete widget.computeSize;
        if (original.ownHeight) widget.computedHeight = original.computedHeight;
        else delete widget.computedHeight;
    } else {
        widget.type = "hidden";
        widget.hidden = true;
        // Legacy canvas adds four pixels after computeSize; cancel that gap.
        // Current Comfy additionally skips hidden widgets entirely.
        widget.computeSize = () => [0, -4];
        widget.computedHeight = 0;
    }
    // Values, callbacks, options.serialize and widget-store identity stay intact.
}

function setupVisibility(node, enhancer, combinedModel) {
    const sizing = createSizing(node);
    const groups = node._arquinovatosVisibilityGroups ||= [];
    if (enhancer) {
        const toggle = node.widgets?.find((widget) => widget.name === "ajustes_avanzados");
        const advanced = (node.widgets || []).filter((widget) => Object.hasOwn(ADVANCED_TOOLTIPS, widget.name));
        if (toggle && advanced.length) {
            for (const widget of advanced) {
                widget.tooltip = ADVANCED_TOOLTIPS[widget.name];
                widget.options ||= {};
                widget.options.tooltip = ADVANCED_TOOLTIPS[widget.name];
            }
            let previousVisible;
            const sync = () => {
                const visible = toggle.value === true;
                if (visible === previousVisible) return;
                previousVisible = visible;
                advanced.forEach((widget) => nativeWidgetVisibility(widget, visible));
                sizing.schedule(); node.setDirtyCanvas(true, true);
            };
            const callback = toggle.callback;
            toggle.callback = function () { const result = callback?.apply(this, arguments); sync(); return result; };
            toggle.tooltip = "Activa opciones de longitud, variación y contexto. Al desactivar se usan los valores predeterminados.";
            groups.push({ sync }); sync();
        }
    }
    if (combinedModel) {
        const manual = (node.widgets || []).filter((widget) => widget.name === "ruta_modelo" || widget.name === "perfil");
        if (manual.length) {
            const details = document.createElement("details");
            Object.assign(details.style, { width: "100%", height: "auto", boxSizing: "border-box", padding: "2px", font: "11px/1.4 sans-serif", color: "var(--input-text, #eee)" });
            const summary = document.createElement("summary");
            summary.textContent = "Modelo del PC (opcional)";
            summary.style.cursor = "pointer";
            for (const name of ["pointerdown", "pointerup", "mousedown", "mouseup", "click", "contextmenu"]) summary.addEventListener(name, (event) => event.stopPropagation());
            const explanation = document.createElement("div");
            explanation.textContent = "Una ruta manual tiene prioridad. Si el archivo no existe o no es un GGUF válido, se muestra un error; no se descarga otro modelo.";
            Object.assign(explanation.style, { paddingTop: "5px", overflowWrap: "anywhere" });
            details.append(summary, explanation);
            const section = node.addDOMWidget("arquinovatos_modelo_manual", "customtext", details, { serialize: false, hideOnZoom: false, getValue: () => "", setValue: () => {} });
            section.serialize = false; section.serializeValue = () => undefined;
            // Insert the nonserialized heading before the original native fields;
            // the serialized native field order remains exactly the backend order.
            const index = node.widgets.indexOf(manual[0]);
            node.widgets.splice(node.widgets.indexOf(section), 1);
            node.widgets.splice(index, 0, section);
            sizing.fix(section, 20);
            sizing.entries.push({ widget: section, measure() { sizing.fix(section, Math.ceil(details.scrollHeight)); } });
            sizing.observe(details);
            let previousOpen;
            const sync = () => {
                if (details.open === previousOpen) return;
                previousOpen = details.open;
                manual.forEach((widget) => nativeWidgetVisibility(widget, details.open));
                sizing.schedule(); node.setDirtyCanvas(true, true);
            };
            details.addEventListener("toggle", sync);
            groups.push({ sync }); sync();
            node._arquinovatosManual = { details, fields: manual, section };
        }
    }
    const configure = node.onConfigure;
    node.onConfigure = function () {
        const result = configure?.apply(this, arguments);
        groups.forEach((group) => group.sync());
        sizing.schedule(); return result;
    };
}

async function copyText(element, button, initial) {
    if (!element.value) return;
    try { await navigator.clipboard.writeText(element.value); button.textContent = "Copiado"; setTimeout(() => { button.textContent = initial; }, 1600); }
    catch { element.focus(); element.select(); button.textContent = "Seleccionado: usa Ctrl+C"; }
}
const messageText = (value) => Array.isArray(value) ? value.join("\n") : typeof value === "string" ? value : "";

function addOutputDisplay(node, enhancer) {
    if (node._arquinovatosDisplay) return;
    const sizing = createSizing(node);
    const container = document.createElement("div");
    // Inline auto overrides the h-full class Comfy adds at mount. Measuring a
    // constrained flex container would otherwise shrink the result and feed its
    // undersized height back into the next node-layout pass.
    Object.assign(container.style, { display: "flex", flexDirection: "column", gap: "6px", padding: "4px 2px", width: "100%", height: "auto", boxSizing: "border-box", color: "var(--input-text, #eee)" });
    const combinedModel = node.comfyClass === MODEL_NODE;
    const title = document.createElement("div"); title.textContent = enhancer ? "Prompt mejorado · v0.0.03" : "Modelo LLM · v0.0.03";
    title.style.font = "600 12px/1.35 sans-serif";
    const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "flex", gap: "6px", flexWrap: "wrap" });
    const runLabel = enhancer ? "Mejorar prompt" : combinedModel ? "Cargar / descargar modelo" : node.comfyClass === "Arquinovatos_Model_Downloader" ? "Descargar modelo" : "Cargar modelo";
    const run = makeButton(runLabel, "Ejecuta este nodo y sus entradas. Los nodos posteriores no se ejecutan.");
    const status = document.createElement("div"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); status.hidden = true;
    Object.assign(status.style, { font: "11px/1.35 sans-serif", overflowWrap: "anywhere" });
    buttons.append(run); container.append(title);
    if (combinedModel) {
        const notice = document.createElement("div");
        notice.textContent = DOWNLOAD_NOTICE;
        notice.setAttribute("aria-label", "Descarga automática de modelo y motor");
        Object.assign(notice.style, { font: "11px/1.4 sans-serif", overflowWrap: "anywhere" });
        container.append(notice);
    }
    container.append(buttons, status);
    const output = makeTextarea("Prompt mejorado, solo lectura"); output.placeholder = "El prompt mejorado aparecerá aquí.";
    const copy = makeButton("Copiar prompt mejorado");
    if (enhancer) { buttons.append(copy); container.append(output); }
    copy.addEventListener("click", (event) => { event.stopPropagation(); copyText(output, copy, "Copiar prompt mejorado"); });
    const infoDetails = document.createElement("details");
    const infoSummary = document.createElement("summary"); infoSummary.textContent = "Información de ejecución";
    const info = document.createElement("div"); info.setAttribute("aria-label", "Información de ejecución");
    Object.assign(info.style, { whiteSpace: "pre-wrap", overflowWrap: "anywhere", font: "11px/1.4 sans-serif", paddingTop: "5px" });
    info.textContent = "Ejecuta el nodo para consultar el modelo y los tiempos.";
    infoDetails.append(infoSummary, info); container.append(infoDetails);
    const usedDetails = document.createElement("details");
    const usedSummary = document.createElement("summary"); usedSummary.textContent = "Prompt utilizado para mejorar";
    const usedPrompt = makeTextarea("Prompt utilizado para mejorar el prompt, solo lectura");
    const copyUsed = makeButton("Copiar prompt utilizado"); copyUsed.style.marginTop = "5px";
    usedDetails.append(usedSummary, usedPrompt, copyUsed); if (enhancer) container.append(usedDetails);
    for (const details of [infoDetails, usedDetails]) {
        details.style.font = "11px/1.4 sans-serif";
        const summary = details.querySelector("summary");
        summary.style.cursor = "pointer";
        // Keep native disclosure toggling, while canvas handlers cannot turn a
        // disclosure click into a node drag/selection/context-menu interaction.
        for (const name of ["pointerdown", "pointerup", "mousedown", "mouseup", "click", "contextmenu"]) {
            summary.addEventListener(name, (event) => event.stopPropagation());
        }
        details.addEventListener("toggle", sizing.schedule);
    }
    copyUsed.addEventListener("click", (event) => { event.stopPropagation(); copyText(usedPrompt, copyUsed, "Copiar prompt utilizado"); });
    const widget = node.addDOMWidget("arquinovatos_resultado", "customtext", container, { serialize: false, hideOnZoom: false, margin: 10, getValue: () => output.value, setValue: (value) => { output.value = typeof value === "string" ? value : ""; sizing.schedule(); } });
    widget.serialize = false; widget.serializeValue = () => undefined;
    sizing.fix(widget, enhancer ? 142 : 80);
    sizing.entries.push({ widget, measure(width) {
        if (enhancer) sizing.textHeight(output, width - 4);
        if (enhancer && usedDetails.open) sizing.textHeight(usedPrompt, width - 4);
        const natural = container.scrollHeight || 8 + sizing.blockHeight(title, width - 4) + 28 + (enhancer ? parseFloat(output.style.height) + 6 : 0) + 22 + (enhancer ? 22 : 0);
        sizing.fix(widget, Math.ceil(natural));
    } });
    sizing.observe(container);
    const display = { output, info, copy, usedPrompt, usedDetails, run, status, promptId: null, busy: false, timer: 0 };
    node._arquinovatosDisplay = display;
    display.setBusy = (busy, text) => {
        display.busy = busy; run.disabled = busy; run.style.cursor = busy ? "wait" : "pointer"; run.style.opacity = busy ? ".65" : "1";
        run.textContent = busy ? enhancer ? "Mejorando…" : "Procesando…" : runLabel;
        if (text !== undefined) { status.textContent = text; status.hidden = !text; }
        sizing.schedule();
    };
    display.accept = (message) => {
        output.value = messageText(message?.text); info.textContent = messageText(message?.info) || "Ejecución terminada.";
        usedPrompt.value = messageText(message?.used_prompt); copy.textContent = "Copiar prompt mejorado"; copyUsed.textContent = "Copiar prompt utilizado";
        display.setBusy(false, ""); if (display.timer) clearTimeout(display.timer); display.timer = 0;
    };
    const finish = (event) => {
        if (!display.promptId || event.detail?.prompt_id !== display.promptId) return;
        display.setBusy(false, event.type === "execution_error" ? `Error: ${event.detail?.exception_message || "Consulta los errores de ComfyUI."}` : event.type === "execution_interrupted" ? "Ejecución cancelada." : "");
    };
    const eventNames = ["execution_error", "execution_interrupted", "execution_success"];
    for (const name of eventNames) api.addEventListener(name, finish);
    const previousRemoved = node.onRemoved;
    node.onRemoved = function () { if (display.timer) clearTimeout(display.timer); for (const name of eventNames) api.removeEventListener(name, finish); return previousRemoved?.apply(this, arguments); };
    async function recoverResult() {
        if (!display.busy || sizing.removed || !display.promptId) return;
        try {
            const response = await api.fetchApi(`/history/${encodeURIComponent(display.promptId)}`);
            if (response.ok) {
                const item = (await response.json())[display.promptId];
                const result = item?.outputs?.[display.executionId];
                if (result) { display.accept(result); return; }
                if (item?.status?.completed) {
                    const error = item.status.messages?.findLast?.((value) => value[0] === "execution_error");
                    display.setBusy(false, error ? `Error: ${error[1]?.exception_message || "Consulta los errores de ComfyUI."}` : "Ejecución terminada sin resultado. Consulta los errores de ComfyUI."); return;
                }
            }
        } catch { /* Reconnection must not queue the same job again. */ }
        display.timer = setTimeout(recoverResult, 2000);
    }
    run.addEventListener("click", async (event) => {
        event.stopPropagation(); if (display.busy) return; display.setBusy(true, "Preparando ejecución…");
        try {
            const prompt = await app.graphToPrompt();
            const target = executionIdFor(node, prompt.output);
            const selected = buildTargetPrompt(prompt.output, target);
            const response = await api.queuePrompt(0, { output: selected, workflow: prompt.workflow }, { partialExecutionTargets: [target] });
            if (!response?.prompt_id) throw new Error("ComfyUI no devolvió un identificador de ejecución.");
            display.promptId = response.prompt_id; display.executionId = target;
            display.setBusy(true, "En cola: este nodo y sus entradas."); display.timer = setTimeout(recoverResult, 2000);
        } catch (error) {
            const detail = error?.response?.error;
            display.setBusy(false, `Error: ${detail?.message || error?.message || String(error)}${detail?.details ? " " + detail.details : ""}`);
        }
    });
    node.setSize([Math.max(node.size?.[0] || 0, 440), node.size?.[1] || 100]); sizing.schedule();
}

app.registerExtension({
    name: "Arquinovatos.PromptEnhancer.v0.0.03",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!PACK_NODES.has(nodeData.name)) return;
        const enhancer = nodeData.name === ENHANCER;
        const combinedModel = nodeData.name === MODEL_NODE;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            for (const widget of this.widgets || []) if (LABELS[widget.name]) { widget.label = LABELS[widget.name]; labelMultilineInput(this, widget); }
            for (const input of this.inputs || []) if (LABELS[input.name]) input.label = LABELS[input.name];
            setupVisibility(this, enhancer, combinedModel);
            addOutputDisplay(this, enhancer); return result;
        };
        const executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) { const result = executed?.apply(this, arguments); addOutputDisplay(this, enhancer); this._arquinovatosDisplay.accept(message); this.setDirtyCanvas(true, true); return result; };
        const draw = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function () {
            const result = draw?.apply(this, arguments); const sizing = this._arquinovatosSizing;
            this._arquinovatosVisibilityGroups?.forEach((group) => group.sync());
            if (sizing && !sizing.updating && Math.abs((this.size?.[1] || 0) - sizing.expectedHeight) > 1) sizing.schedule();
            return result;
        };
    },
});
