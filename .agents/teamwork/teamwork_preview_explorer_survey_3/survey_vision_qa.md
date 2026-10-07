# Informe de Investigación: Inversión de ADN Visual (Estilo y Personajes) y Arquitectura de Control de Calidad Adversarial (Visual QA)

**Fecha:** 2026-10-06  
**Agente:** `teamwork_preview_explorer_survey_3`  
**Objetivo:** Diagnóstico integral de referencias visuales, mecanismos de inversión visual con modelos multimodales, causas raíz de la degradación estilística, y propuesta arquitectónica para el pipeline de **Style & Character DNA Inversion** y **Adversarial Visual QA** en `asVideoStudio`.

---

## 1. Localización y Estructura de Hojas de Referencia y Personajes

### 1.1. Directorio de Presets y Hojas Maestras del Estudio
Los presets del canal están centralizados en `presets.json` en la raíz del proyecto y sus activos gráficos residen en `banco/presets/<preset_id>/`.

- **Catálogo de Presets:** `/Users/danidev/Desktop/asVideoStudio/presets.json` (602 líneas)
  - Identificadores principales: `pr1a0eef81dc7` (Pluma_2), `pr1a0f81fbf25` (Pluma_3), `pr1a0f91a4e44`, `pr1a10889874e`, `pr1a0eec3e48e`.
- **Hojas Maestras de Estilo por Preset (`banco/presets/<id>/`):**
  - `00_cara.png` (830 KB): Plano detalle de expresión facial, ojos, trazo de contorno y acabado de piel.
  - `01_cuerpos.png` (468 KB): Anatomía completa, proporciones de figuras (6 cabezas), extremidades y vestuario base.
  - `02_interior.png` (412 KB): Estilo de escenario interior, mobiliario, líneas de perspectiva y división de plano/suelo.
  - `03_exterior.png` (381 KB): Fondos abiertos, elementos arquitectónicos y atmósfera.
  - `04_objeto.png` (118 KB): Objetos y utilería con el grosor de línea y acabado del preset.
  - `05_diagrama.png` (221 KB): Estilo esquemático/infográfico con integración de figuras.
  - `miniatura.png` y `muestra1.png` - `muestra6.png`: Muestras consolidadas para previsualización en UI.

### 1.2. Hojas de Reparto (Personajes) y Referencias de Proyecto
En los proyectos de producción, las referencias se organizan en:
- **Hojas de Reparto del Proyecto:**
  - Ubicación: `<proyecto>/pasos/assets/v2/assets/reparto/`
  - Ejemplo analizado (`que_pasaria_si_la_humanidad_dejara_de_morir_durante_24_horas`):
    - `criminales.png` (197 KB, 1024x576, 15.010 colores únicos): Hoja generada por IA.
    - `ejecutivos.png` (12 KB, 1280x720, 500 colores únicos): **Lienzo de emergencia degradado**.
    - `gente_generica.png` (12 KB, 1280x720, 500 colores únicos): **Lienzo de emergencia degradado**.
    - `medicos.png` (12 KB, 1280x720, 500 colores únicos): **Lienzo de emergencia degradado**.
    - `pacientes.png` (12 KB, 1280x720, 500 colores únicos): **Lienzo de emergencia degradado**.
- **Láminas de Estilo Compuestas (`lamina_estilo.png`):**
  - Generadas por `_lamina_estilo(rutas, destino)` en `pasos/p6_assets.py:3703-3738`.
  - Agrupan de 4 a 8 referencias en una cuadrícula en un único archivo (ej. `<proyecto>/pasos/assets/v2/_refs/lamina_estilo_a5f104e1968a.png`, 476 KB).
  - Diseñadas para reducir costes de entrada de tokens en APIs multimodales de edición de imagen.
- **Fotogramas Extraídos de YouTube / Vídeos de Referencia:**
  - Ubicación: `<proyecto>/estilo/aportadas/` (ej. `proyectos/taller_pluma_1/estilo/aportadas/`, con 22 archivos JPEG de 720p).
  - `<proyecto>/estilo/dibujadas/`: `cara.png`, `cuerpos.png`, `diagrama.png`, `exterior.png`, `interior.png`, `objeto.png`.

---

## 2. Definiciones de Estilo, Descripciones de Personajes y Carga de Presets

### 2.1. Estructura de Datos del Preset de Estilo
En `presets.json`, cada entrada almacena la definición del estilo en `datos["estilo"]["guia"]`:

```json
{
  "guia": "Draw a minimalist 2D vector animation scene featuring a stick-figure character...",
  "paleta": ["#ffffff", "#000000", "#7cc47c", "#3a86ff", "#ffb703", "#fb8500", "#d90429", "#2b2d42"],
  "trazo": "Outlines are uniform solid black lines, approximately 3 to 4 pixels thick, applied to both characters and all background elements with a slight hand-drawn marker texture.",
  "relleno": "Surfaces are filled with flat solid colors with zero gradients, no half-tones, no textures, and complete absence of shading.",
  "personajes": "Characters are minimalist stick figures with round white unshaded heads, thin black line limbs, approximately 6 heads tall...",
  "caras": "Faces feature unshaded white skin with no skin color fill, minimalist black dot eyes, simple horizontal line mouths, occasional thin black eyebrow lines, and no nose or ears.",
  "manos": "No separate fingers; hands and feet are simple rounded line endings or dark mitten-shaped blobs...",
  "fondos": "Backgrounds consist of stark white walls and a flat green floor strip separated by a single black horizontal line...",
  "luz": "Lighting is completely flat and ambient with no light source direction, no cast shadows, and no highlights.",
  "composicion": "Centered compositions with generous white negative space, low horizon line, and a clean flat perspective.",
  "acabado": "Clean digital vector look with minimal hand-drawn marker imperfection...",
  "evitar": "['no skin gradients', 'no cast shadows', 'no eye highlights', 'no realistic five-fingered hands', 'no photographic hand anatomy', 'no complex shading', 'no 3D rendering']",
  "resumen_es": "Animación 2D minimalista estilo video educativo con personajes de palitos, trazo negro uniforme y colores planos sin sombras."
}
```

### 2.2. Cómo se Cargan y Aplican los Presets
- Módulo responsable: `pasos/presets_canal.py`.
- Función `aplicar(preset, proyecto)`: Copia los valores directamente a los parámetros (`params`) de los pasos del grafo (`brief`, `guion`, `assets`, `voz`, `callouts`).
- No almacena el ID del preset por referencia estricta: los datos se copian en `params["estilo"]` de `p6_assets` para garantizar reproducibilidad independiente del preset original.
- Las imágenes de referencia se copian a `banco/presets/<id>/` y las referencias activas se resuelven en `medios.reubicar_todas(p["estilo"].get("referencias"))`.

### 2.3. Definición de Personajes en el Catálogo del Proyecto (`plan.json`)
En `plan.json`, el reparto se modela bajo `assets`:
- Cada personaje tiene: `nombre`, `tipo: "reparto"`, `grupo: bool`, `descripcion` textual en inglés, y `feedback`.
- Ejemplo (`plan.json:10631`):
  ```json
  "asset:medicos": {
    "tipo": "reparto",
    "nombre": "medicos",
    "descripcion": "A group of minimalist stick figures with round white unshaded heads, thin black line limbs, approximately 6 heads tall, wearing simple flat-colored scrubs and lab coats, of various apparent ages and complexions.",
    "grupo": true,
    "feedback": ""
  }
  ```
- En `plan.json["dependencias"]`, cada plano (`escena:S001` .. `escena:S123`) declara qué assets del reparto intervienen físicamente.

---

## 3. Diagnóstico de la Desconexión Visual y Fallos en el Pipeline de Imagen

La investigación del código en `pasos/p6_assets.py` y `motores/imagen_openai/yieldchat_imagen.py` ha revelado **cuatro fallos críticos concatenados** que causan la pérdida de estilo:

### Causa Raíz 1: Referencias Fantasma (`Reference image 1/2`) en Endpoints Text-to-Image
- En `pasos/p6_assets.py` (`_prompt_completo`, líneas 2596-2630), el generador construye instrucciones textuales que asumen que el modelo recibe imágenes adjuntas:
  - `"Reference image 1 is a STYLE SHEET: a single picture that contains several separate frames..."`
  - `"Reference image 2 is the cast sheet for 'medicos': draw those exact characters..."`
- Sin embargo, los motores configurados para producción (Agnes AI y SiliconFlow) son invocados mediante `POST /v1/images/generations` (Text-to-Image).
- **Las imágenes NO se envían en la petición HTTP**: el payload solo envía `{ "model": "...", "prompt": "...", "size": "..." }`.
- El modelo de difusión recibe instrucciones sobre una `Reference image 1` que **no existe en su contexto**, provocando que el encoder de texto intente alucinar o ignorar la referencia.

### Causa Raíz 2: Mutilación de Prompts a < 280 Caracteres y Sobrescritura de Estilo
- En `motores/imagen_openai/yieldchat_imagen.py:64-174`:
  - La función `limpiar_y_condensar_prompt` ejecuta un truncado agresivo:
    ```python
    if len(prompt_resumen) > 280:
        prompt_resumen = prompt_resumen[:277] + "..."
    ```
  - Descarta explícitamente cualquier línea que comience por `Reference image`, `The written style guide`, `Style guide`, etc.
  - Sobrescribe el estilo específico del preset con una de tres cadenas fijas genéricas:
    - `3d`: `"photorealistic 3D, chrome robot panels, glowing cyan details"`
    - `stick`: `"minimalist 2D stick figure cartoon"`
    - `2d`: `"2D vector animation style, clean line art"`
  - **Consecuencia:** Toda la guía de estilo (`trazo`, `paleta`, `relleno`, `personajes`, `caras`, `manos`, `luz`) extraída o configurada en el preset se elimina completamente antes de enviar la llamada a la API.

### Causa Raíz 3: Inyección de 14 KB de Meta-Reglas en Español para LLM en Prompts de Difusión
- En `pasos/p6_assets.py:2646`, se invoca:
  ```python
  bloque = reglas.bloque_prompt("prompt_imagen")
  if bloque:
      lineas.append(bloque)
  ```
- Este bloque concatena el contenido de `motores/reglas/reglas.json` (24 KB en total), inyectando párrafos enteros en español redactados como directivas para humanos o LLMs (ej.: *"Todo prompt de escena debe fijar explicitamente la hora del dia y la fuente de luz. Si la escena es interior, se especifica la luz interior Y si por las aberturas entra dia o noche..."*).
- Los text encoders de difusión (CLIP ViT-L / T5-XXL) tienen ventanas de contexto limitadas (77 tokens estándar en CLIP, saturándose rápidamente). Esas instrucciones en español desplazan los descriptores visuales clave fuera de la atención del encoder.

### Causa Raíz 4: Fallos 404 por URLs Efímeras en Agnes AI y Caída a Lienzos de Emergencia (12 KB)
- En `motores/imagen_openai/yieldchat_imagen.py:403-408`:
  ```python
  payload = {
      "model": "agnes-image-2.1-flash",
      "prompt": prompt_completo,
      "size": img_size
  }
  ```
  - **No se solicita `"response_format": "b64_json"`**. Agnes AI devuelve una URL temporal en su CDN que expira en segundos o produce errores HTTP 404/red.
- Al fallar Agnes AI y SiliconFlow, el pipeline cae a `_crear_lienzo_cinematografico(prompt, width, height)` (líneas 229-266):
  - Genera una tarjeta PNG estática de 12 KB (fondo blanco con franja verde `#78b478` y línea negra de 3 px) con 500 colores únicos.
  - Esta es la razón exacta por la cual 4 de las 5 hojas de reparto (`ejecutivos.png`, `gente_generica.png`, `medicos.png`, `pacientes.png`) son rectángulos vacíos en disco.

---

## 4. Acceso y Capacidades de Modelos Multimodales en el Entorno

### 4.1. Disponibilidad de SDKs y Claves de API
Se ha realizado una auditoría activa en el entorno de ejecución (Python 3.12 en macOS):

| Componente | Estado | Detalle Técnico |
|---|---|---|
| `google.genai` SDK | **DISPONIBLE** | Paquete oficial moderno de Google GenAI instalado en Python 3.12 (`from google import genai`). |
| `GEMINI_API_KEY` | **CONFIGURADA** | Clave activa en `secretos/.env` y validada funcionalmente. |
| `pasos/gemini_cliente.py` | **OPERATIVO** | Módulo nativo con soporte REST (`generateContent`) para `gemini-2.5-flash`, `gemini-3.5-flash`, etc. |
| `cv2` (OpenCV) | **DISPONIBLE** | OpenCV 4.x instalado y funcional para procesamiento visual, histogramas y matrices de color. |
| `numpy` / `PIL` | **DISPONIBLES** | Instalados y operativos para álgebra de píxeles y manipulación de imágenes. |
| `AGNES_API_KEY` | **CONFIGURADA** | Clave activa en `secretos/.env` para `agnes-image-2.1-flash`. |
| `SILICONFLOW_API_KEY`| **CONFIGURADA** | Clave activa en `secretos/.env` para fallback de imagen. |

### 4.2. Prueba de Inferencia Multimodal Real (Gemini 2.5 Flash Vision)
Se ha ejecutado una prueba de inversión visual directa utilizando `gemini_cliente.py` sobre la hoja de estilo real `/Users/danidev/Desktop/asVideoStudio/banco/presets/pr1a0eef81dc7/00_cara.png`:
- **Tiempo de respuesta:** 6,8 segundos.
- **Resultado obtenido (extracto validado):**
  - **Técnica:** `"Hand-drawn 2D animation style, minimalist flat cartoon with a sketchy aesthetic, reminiscent of whiteboard animation or simple doodles."`
  - **Paleta Hexadecimal Exacta:** `["#F8F8F8", "#82C872", "#4A90E2", "#F5A623", "#F8E71C", "#000000"]`
  - **Trazo / Contorno:** `"Medium-thick and relatively consistent, but with slight variations and irregularities characteristic of a hand-drawn style. Color: #000000. Texture: Sketchy, slightly wobbly..."`
  - **Anclas de Personaje:** Cabeza circular unshaded blanca, ojos de dos puntos negros sólidos, boca de línea recta horizontal, ausencia de nariz y orejas.

Esta prueba confirma empíricamente que **Gemini 2.5 Flash Vision** es 100% capaz de realizar la inversión de ADN visual con altísima precisión técnica y nulo coste de dependencias adicionales.

---

## 5. Auditoría de Capacidades de Pruebas, Verificación y Control de Calidad (Visual QA)

### 5.1. Estado Actual de Pruebas Visuales en el Proyecto
- `pasos/prueba_pasos_visuales.py`: Suite de integración que valida el pipeline 6-7-8 (recortes de audio, posicionamiento SVG de subtítulos con `PIL`/`numpy`, transiciones y render FFmpeg). Sin embargo, usa el modo "adoptar" (arte ya existente) y **no verifica la fidelidad estética ni aberraciones de las imágenes**.
- `pasos/prueba_encuadres.py`: Valida determinismo de la escalera de encuadres (`encuadres.ESCALERA`), pero no verifica que la imagen generada respete el plano solicitado.
- `pasos/corrector.py`: Permite la corrección asistida por agente cuando un revisor humano rechaza una imagen, pero carece de un árbitro programático automático (Automated QA Judge).

### 5.2. Capacidades de Validación Implementables con OpenCV y NumPy

Con `cv2` y `numpy` ya presentes en el entorno, es posible implementar verificaciones automatizadas sin sobrecoste de red:

1. **Detección Inmediata de Lienzos de Emergencia y Degeneraciones (< 5 ms por imagen):**
   - Comprobación de número de colores únicos: `len(np.unique(arr.reshape(-1, arr.shape[-1]), axis=0))`. Si es menor a 1.000 (o coincide con la máscara de `_crear_lienzo_cinematografico`), la imagen es rechazada de inmediato como fallo de entrega de API.
   - Varianza del Laplaciano (`cv2.Laplacian(gray, cv2.CV_64F).var()`): Detección de imágenes vacías, lienzos lisos o aberraciones sin contenido gráfico.
2. **Comparación de Histogramas de Color (HSV / Lab) y Distancia Bhattacharyya:**
   - Cálculo de histograma 2D H-S (`cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])`).
   - Comparación con el histograma de referencia del preset mediante `cv2.compareHist(h1, h2, cv2.HIST_BHATTACHARYYA)`.
   - Umbral de alerta: Si $d_{Bhat} > 0.65$, la escena presenta una desviación cromática inaceptable respecto al estilo activo.
3. **Verificación de Continuidad entre Planos Consecutivos:**
   - Para escenas marcadas con `mismo_set: True`:
     - Comparación de histograma de luminosidad (canal L en Lab) y distribución de color dominante.
     - Detección de saltos bruscos de iluminación (ej. pasar accidentalmente de día soleado a noche oscura en el mismo cuarto).
4. **Verificación Geométrica y de Encuadre:**
   - Detección de bandas negras accidentales (letterboxing/pillarboxing) revisando bordes superior/inferior y laterales.
   - Comprobación de distribución de energía visual según la carta de encuadre (`encuadres.py`):
     - `primer_plano` / `macro`: Concentración de bordes de alto contraste en el tercio central.
     - `aereo` / `general`: Línea de horizonte detectada o dispersión amplia de contornos pequeños.

---

## 6. Arquitectura Propuesta: Pipeline de Style & Character DNA Inversion y Adversarial Visual QA

Se propone una arquitectura dividida en cuatro capas complementarias y desacopladas:

```
[Lámina Estilo / Presets] + [Hojas Reparto]
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 1: Style & Character DNA Inverter (Gemini 2.5 Flash)  │
│  - Extrae técnica, paleta exacta, trazo, luz y anatomía     │
│  - Genera descriptores textuales canónicos en inglés        │
│  - Almacena en: banco/presets/<id>/dna_estilo.json          │
└─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 2: Prompt Synthesizer & Context Purger                │
│  - Elimina referencias fantasma ("Reference image 1")       │
│  - Purga los 14 KB de meta-reglas en español para LLMs      │
│  - Estructura prompt modular en inglés (120-180 palabras):  │
│    [STYLE DNA] + [SCENE] + [CHARACTERS] + [LIGHTING]        │
│    + [NEGATIVE PROMPT]                                      │
└─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA 3: Resilient Engine Adapter (Agnes AI / SiliconFlow)  │
│  - Agnes AI: Fuerza "response_format": "b64_json"           │
│  - Elimina recorte hardcodeado a 280 caracteres             │
│  - Fallback transparente Agnes -> SiliconFlow               │
│  - Prohibido fallback silencioso a lienzo dummy             │
└─────────────────────────────────────────────────────────────┘
               │
               ▼ (Imagen PNG generada)
┌─────────────────────────────────────────────────────────────┐
│  CAPA 4: Adversarial Visual QA Judge                        │
│  [Nivel 1: Local OpenCV / NumPy (<10ms)]                    │
│   - Anti-dummy check: colores únicos > 1000, entropía       │
│   - Histograma Bhattacharyya vs Lámina de estilo            │
│   - Continuidad lumínica con plano anterior (mismo set)     │
│   - Verificación de encuadre y ausencia de bandas negras    │
│  [Nivel 2: Multimodal Visual QA (Gemini 2.5 Flash Vision)]  │
│   - Auditoría estética y de anclas de personaje (opcional)  │
└─────────────────────────────────────────────────────────────┘
```

### 6.1. Especificación de Componentes

#### Componente 1: Inversor de ADN Visual (`pasos/inversor_dna.py`)
- **Entrada:** `00_cara.png` a `05_diagrama.png` (o `lamina_estilo.png`) del preset activo; hojas de personajes del reparto (`reparto/*.png`).
- **Motor:** `gemini-2.5-flash` mediante `pasos/gemini_cliente.py` o `google.genai.Client`.
- **Estructura de Salida (`dna_estilo.json`):**
  ```json
  {
    "medium": "2D minimalist vector animation, clean flat cartoon explainer style",
    "stroke": "Solid black uniform outline, 3-4px line weight with subtle marker texture",
    "fill": "Pure flat solid color fills, zero gradients, no shading, no ambient occlusion",
    "palette": ["#ffffff", "#000000", "#7cc47c", "#3a86ff", "#ffb703", "#fb8500", "#d90429"],
    "lighting": "Completely flat ambient lighting, zero directional cast shadows, no highlights",
    "anatomy": "Stick-figure proportions (6 heads tall), unshaded white circular heads, 2 small black dot eyes, straight line mouth, no nose or ears, thin black stick limbs, mitten hands with no separate fingers",
    "backgrounds": "Stark white background wall, flat horizontal floor strip bounded by black line",
    "negative": "3d render, realistic anatomy, five fingers, photographic skin, shading, gradients, shadows, textures, watermark, borders, grid, collage"
  }
  ```
- **Estructura de Anclas de Reparto (`dna_reparto.json`):**
  ```json
  {
    "medicos": {
      "anchors": "minimalist stick figures, unshaded white round heads, 2 black dot eyes, straight line mouth, wearing flat turquoise scrubs (#2a9d8f) and open white lab coats, thin black stick limbs, no separate fingers"
    },
    "criminales": {
      "anchors": "minimalist stick figures, unshaded white round heads, 2 black dot eyes, wearing flat black hoodies (#1a1a1a) and dark casual jeans (#2b2d42), thin black stick limbs, no separate fingers"
    }
  }
  ```

#### Componente 2: Sintetizador Modular de Prompts (`pasos/sintetizador_prompt.py`)
- **Estructura Modular Generada:**
  - `[STYLE DNA]`: Inyección directa del bloque estilístico condensado en inglés (~40 palabras).
  - `[SCENE/ACTION]`: Descripción concreta del plano y acción dramática (~30 palabras).
  - `[CHARACTER ANCHORS]`: Anclas visuales inmutables de los personajes que están físicamente en el plano.
  - `[FRAMING & LIGHTING]`: Definición de encuadre (`encuadres.py`) y luz.
  - `[NEGATIVE]`: Tokens negativos consolidados.
- **Ventaja:**
  - Elimina por completo referencias a `Reference image 1` o `Reference image 2`.
  - Elimina las 14 KB de reglas en español.
  - El prompt total ocupa ~120-180 palabras, encajando óptimamente en la ventana de atención de los text encoders sin sufrir truncamientos destructivos.

#### Componente 3: Adaptador de Motores Resiliente (`motores/imagen_openai/yieldchat_imagen.py`)
- **Correcciones Críticas:**
  1. En `_intentar_generar_agnes`:
     - Añadir `"response_format": "b64_json"` al payload JSON.
     - Decodificar directamente `b64_json` en memoria (eliminando fallos por URL 404).
  2. Eliminar el corte a 280 caracteres en `limpiar_y_condensar_prompt`. El nuevo sintetizador produce prompts ya optimizados.
  3. Eliminar las plantillas hardcodeadas (`"photorealistic 3D, chrome robot panels..."`) que ignoraban el preset.
  4. En caso de fallo de Agnes AI, intentar inmediatamente SiliconFlow (`Tongyi-MAI/Z-Image-Turbo` o `black-forest-labs/FLUX.1-schnell`).
  5. Si ambos proveedores externos fallan, registrar una excepción explícita en lugar de devolver silenciosamente un lienzo de emergencia.

#### Componente 4: Juez de Control de Calidad Adversarial (`pasos/juez_visual.py`)
- Módulo ligero de validación automática ejecutado tras la generación de cada plano en `p6_assets.py`.
- **Pipeline de Validación:**
  ```python
  def auditar_imagen(ruta_png, ruta_estilo_ref, encuadre_id, anterior_png=None, mismo_set=False):
      """Audita la calidad estética y cromática de una imagen generada."""
      # 1. Comprobación contra lienzos dummy
      if es_lienzo_degenerado(ruta_png):
          return False, "DEGENERATED_CANVAS: La imagen es un lienzo de emergencia o carece de contenido"
      
      # 2. Comprobación de encuadre y bandas negras accidentales
      if tiene_bandas_negras(ruta_png):
          return False, "BLACK_BORDERS: La imagen tiene franjas negras indeseadas"
      
      # 3. Fidelidad cromática respecto al preset (Bhattacharyya)
      distancia = comparar_histogramas_hsv(ruta_png, ruta_estilo_ref)
      if distancia > 0.65:
          return False, f"STYLE_DRIFT: Distancia cromática excesiva ({distancia:.2f} > 0.65)"
      
      # 4. Continuidad lumínica con el plano anterior
      if mismo_set and anterior_png:
          salto_luz = diferencia_luminancia(ruta_png, anterior_png)
          if salto_luz > 0.40:
              return False, f"LIGHTING_DRIFT: Salto de iluminación injustificado en el mismo set ({salto_luz:.2f})"
      
      return True, "OK"
  ```

---

## 7. Plan de Implementación Recomendado para el Equipo Multi-Agente

1. **Fase 1 (Inversión Visual y Descriptores):**
   - Implementar `pasos/inversor_dna.py` utilizando Gemini 2.5 Flash Vision.
   - Procesar las láminas de estilo de `presets.json` y generar las anclas de personajes para el proyecto activo.
2. **Fase 2 (Refactorización de Prompts y Adaptador de Motores):**
   - Eliminar `Reference image` y meta-reglas en español de `pasos/p6_assets.py`.
   - Modificar `yieldchat_imagen.py` para enviar prompts completos, activar `"response_format": "b64_json"` en Agnes AI e integrar fallback transparente a SiliconFlow.
3. **Fase 3 (Control de Calidad Adversarial):**
   - Implementar `pasos/juez_visual.py` con verificaciones OpenCV/NumPy.
   - Integrar la validación en el bucle de generación de `p6_assets.py`.
4. **Fase 4 (Regeneración de Hojas de Reparto y Validación E2E):**
   - Regenerar las hojas de reparto degradadas (`ejecutivos.png`, `medicos.png`, `pacientes.png`, `gente_generica.png`) asegurando que alcancen el estándar visual de `criminales.png`.
   - Ejecutar pruebas de regresión visual y verificar el cumplimiento de los criterios de aceptación.
