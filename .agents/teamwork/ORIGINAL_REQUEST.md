# Original User Request

## Initial Request — 2026-10-06T19:22:19Z

# Teamwork Project Prompt

> Status: Launched — En ejecución con el equipo multi-agente
> Goal: Implementar la fidelidad visual de imágenes respecto a referencias
> Requested team: Equipo multi-agente especializado en visión por computador, prompts para difusión y fiabilidad de APIs de imagen

## Descripción del Proyecto
Modernización y corrección integral del pipeline de fidelidad visual en `asVideoStudio`: resolver la desconexión entre las láminas de referencia/hojas de reparto y los motores de generación de imagen (Agnes AI, SiliconFlow, Gemini), eliminando la mutilación de prompts y dotando al sistema de inversión visual (Style & Character DNA Inversion).

Working directory: /Users/danidev/Desktop/asVideoStudio

## Roles y Agentes Especializados

1. **Agente Especialista en Inversión Visual (Vision & Style Inversion Agent)**
   - **Misión:** Analizar mediante modelos multimodales (Gemini 2.5 Flash Vision) las láminas de estilo de referencia (`lamina_estilo.png`) y las hojas de personajes (`reparto/*.png`).
   - **Tareas:** Extraer descriptores técnicos de alta densidad (técnica pictórica, paleta exacta, tratamiento de luz, textura, contorno) y anclas visuales inmutables de los personajes.
   - **Mejora:** Elimina las "referencias fantasma" (`Reference image 1`) y las sustituye por condicionamiento visual textual concreto que cualquier motor de difusión sabe interpretar.

2. **Agente Arquitecto de Prompts de Difusión (Prompt Engineering & Text Encoder Agent)**
   - **Misión:** Rediseñar la construcción de prompts en `pasos/p6_assets.py` y `yieldchat_imagen.py`.
   - **Tareas:** Purgar los 14 KB de meta-reglas en español que saturan la ventana de contexto de los text encoders (CLIP/T5), estructurando un prompt modular en inglés (`[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]`).
   - **Mejora:** Incrementa radicalmente la adherencia de estilo y evita que las escenas deriven hacia estilos genéricos o estocásticos.

3. **Agente de Integración de Motores y Resiliencia de APIs (Engine Adapter & Network Agent)**
   - **Misión:** Refactorizar `motores/imagen_openai/yieldchat_imagen.py` y asegurar la entrega en Agnes AI y SiliconFlow.
   - **Tareas:** Forzar `"response_format": "b64_json"` en Agnes AI para evitar errores 404 por URLs efímeras; eliminar el corte hardcodeado a 280 caracteres y las plantillas rígidas; implementar fallback transparente si un proveedor agota saldo o cuota.
   - **Mejora:** Garantiza que el 100% de las imágenes generadas se descarguen y almacenen en disco sin degradarse a lienzos de emergencia.

4. **Agente de Validación y Control de Calidad (Adversarial QA & Style Consistency Judge)**
   - **Misión:** Verificar programáticamente la consistencia estética y cromática de las escenas generadas respecto al preset seleccionado.
   - **Tareas:** Comparar histogramas de color, verificar cumplimiento de parámetros de encuadre y asegurar que ninguna escena quede en estado inválido o con aberraciones visuales.
   - **Mejora:** Prevención y detección temprana de desvíos de continuidad entre planos consecutivos.

## Requirements

### R1. Extracción de ADN Visual desde Láminas de Referencia
El sistema debe analizar automáticamente los archivos de referencia del estilo activo y generar un bloque de especificación de estilo reutilizable para toda la tanda.

### R2. Reestructuración Limpia del Prompt para Text Encoders
El generador de prompts debe construir descripciones estructuradas en inglés con longitud optimizada (sin instrucciones de redacción en español para LLMs y sin referencias relativas inexistentes).

### R3. Pipeline de Generación Robusto con Base64 y Sin Mutilación de Texto
Las llamadas a Agnes AI deben emitirse con el prompt completo del estilo y solicitar `b64_json` directo para evitar fallos de enlace.

## Acceptance Criteria

### Fidelidad Visual y Estilo
- [ ] Las imágenes producidas coinciden en paleta, tipo de trazo y técnica con la lámina de estilo del preset.
- [ ] Los personajes mantienen sus anclas visuales fijas (ropa, accesorios, fisionomía) entre escenas consecutivas.

### Estabilidad y Entrega
- [ ] Cero fallos por URLs efímeras 404 en Agnes AI.
- [ ] Ningún prompt de estilo es truncado artificialmente a 280 caracteres ni sobrescrito por plantillas genéricas.


## Follow-up — 2026-10-07T18:29:03Z

Instrucción del usuario sobre consumo de cuota:
"hay alguna manera de que los agentes o tu tarea no consuma la totalidad de mi cuota de gemini?"

Por favor, confirma qué medidas de mitigación o contención de cuota estás aplicando o puedes aplicar inmediatamente (reducir concurrencia, suprimir subagentes redundantes, pausar exploradores innecesarios, no invocar APIs externas de Gemini en bucle y aprovechar el código ya completado y verificado en el workspace).
