# Plan: asistente de tono con IA (MCP) y cabinas de TONE3000

Estado: **11.1 hecha** (2026-11-21); el resto, planificado. Complementa `plan.md` (fase 11). Las reglas de `plan.md` §0
siguen vigentes: archivos de código ≤ 1000 líneas, nada destructivo sin confirmación, commits con
`/commit:commit`, diseños visuales aprobados por el usuario antes del commit.

## 1. Objetivo

1. Pedir un sonido en lenguaje natural ("el tono de Slash en Sweet Child", "clean con chorus de los 80", "más
   ganancia y menos graves") y que la IA configure la GE150 **en vivo**, sin guardar hasta que el usuario lo pida.
2. Buscar y descargar cabinas (IR) de **TONE3000** y cargarlas en las ranuras de IR de usuario (CAB 27-36).
3. Usar las suscripciones que el usuario ya paga (Claude Pro y ChatGPT Plus), **sin claves de API**.

## 2. Situación actual

- `services/tone_ai.py` + `ge150ctl ai` (en `main`): una sola consulta a `claude -p` o `codex exec` con el catálogo
  completo en el prompt y respuesta JSON validada (`--json-schema` / `--output-schema`). Probado con la pedalera real
  en modo `--dry-run`: Claude 15 s, Codex 30 s, propuestas válidas.
- `ui/ai_dialog.py` (sin commit, pendiente de aprobación): ventana de chat con Deshacer.
- Limitación de este enfoque: la IA no puede **leer** el estado por su cuenta, ni probar y corregir, ni buscar IR; todo
  va en un único prompt grande (~10 K tokens del catálogo en cada pedido).

## 3. Arquitectura propuesta: servidor MCP de la GE150

La pedalera se expone como un **servidor MCP** (Model Context Protocol). Cualquier cliente MCP (Claude Code, Codex,
la propia app) la controla con herramientas tipadas. La IA decide qué leer y qué cambiar, en varios pasos.

```
                ┌───────────────────────── GE150 Editor (GUI) ─────────────────────────┐
                │  DeviceSession ── Editor ── DeviceState ── widgets                   │
 pedalera USB ──┤        ▲                                                             │
                │        │ hilo del runner (escrituras serializadas)                   │
                │  ge150.mcp.server  (HTTP en 127.0.0.1:PUERTO, token de sesión)         │
                └────────▲─────────────────────────────────────────────────────────────┘
                         │ MCP (streamable HTTP)
        ┌────────────────┼──────────────────────────┐
        │                │                          │
  claude -p (chat de   Claude Code / Codex      otro cliente MCP
  la app, modo agente)  en la terminal del usuario
```

### 3.1 Dos modos de transporte

| Modo | Cuándo | Cómo |
|---|---|---|
| **Embebido (HTTP local)** | La GUI está abierta (caso normal) | La app ya tiene la sesión USB abierta; el servidor MCP corre dentro de la app en `127.0.0.1` con un token aleatorio por sesión. Los cambios se ven al instante en la GUI. |
| **Autónomo (stdio)** | Sin GUI (terminal, scripts) | `ge150-mcp` (nuevo ejecutable) abre la pedalera él mismo. No puede convivir con la GUI abierta: detecta el servidor de la app (archivo `$XDG_RUNTIME_DIR/ge150/mcp.json`) y, si existe, actúa como proxy hacia él. |

Motivo: dos procesos leyendo el mismo `hidraw` se roban las respuestas; la pedalera debe tener **un solo dueño**.

### 3.2 Herramientas MCP

Lectura (sin confirmación):

| Herramienta | Devuelve |
|---|---|
| `get_catalog(module?)` | Modelos de un módulo (o el índice de módulos): nombre, "basado en", parámetros con rango/unidad/opciones. La IA pide solo lo que necesita (prompt más chico). |
| `get_current_patch()` | Preset actual decodificado: módulos, encendido, modelo, valores, EXP, nombre y si tiene cambios sin guardar. |
| `list_presets(query?)` | Los 200 nombres (con filtro). |
| `get_preset(slot)` | Un preset guardado, decodificado. |
| `list_user_irs()` | Las 10 ranuras de IR y de NR con sus nombres. |
| `get_settings()` | Sistema y caja de ritmos (`model/settings.py`). |

Escritura **en vivo** (edit buffer; no persiste, reversible con `undo`):

| Herramienta | Efecto |
|---|---|
| `set_module(module, on?, model?, params?)` | Encender o apagar, cambiar el modelo y los valores (validación igual a `tone_ai.parse_proposal`; devuelve los valores reales aplicados y avisos). |
| `apply_patch(modules[], name?)` | Patch completo en una llamada (lo que hoy hace el JSON). |
| `undo()` | Vuelve al estado anterior al último cambio hecho por la IA (pila por sesión MCP). |
| `select_preset(slot)` | Cambia de preset. Si hay cambios sin guardar, **pide confirmación** (ver 3.3). |

Escritura **persistente** (siempre con confirmación del usuario; la IA nunca guarda presets):

| Herramienta | Efecto |
|---|---|
| `load_ir(slot, source)` | Carga un IR en una ranura de usuario: `source` = ruta WAV local o `tone3000:<id>`. |

TONE3000 (sección 5): `tone3000_search(query, gear?)`, `tone3000_get(tone_id)`.

**Nunca expuestos por MCP:** reset de fábrica, restore de backup, firmware, borrar IR/NR ajenos al pedido.

### 3.3 Confirmaciones y seguridad

- Las herramientas persistentes usan **elicitation** de MCP (el servidor pide confirmación al cliente) **y**, en modo
  embebido, un diálogo en la GUI ("Claude quiere guardar en la ranura 30 'SCOM Solo'. ¿Permitir?"). Sin respuesta
  en 60 s = rechazado.
- Token aleatorio por sesión en la cabecera `Authorization`; el servidor escucha solo en `127.0.0.1`; archivo de
  descubrimiento con permisos 0600.
- Límite de escrituras en vivo: ≥ 40 ms entre módulos (como la GUI), para no saturar la pedalera.
- Registro de cada llamada (herramienta, argumentos, resultado) visible en el panel de la IA: el usuario ve qué hizo.
- La IA corre sin herramientas propias de archivos ni shell: `claude -p --tools "" --mcp-config … --allowedTools
  "mcp__ge150__*"`; Codex con `--sandbox read-only` y el servidor MCP en `-c mcp_servers.ge150=…`.

### 3.4 Clientes

1. **Chat de la app (modo agente)**: la ventana del asistente lanza `claude -p` (o `codex exec`) con el servidor MCP
   de la app. La IA puede leer, aplicar, revisar y corregir. Se muestra el progreso (herramientas llamadas) en vivo
   con `--output-format stream-json` / `codex exec --json`.
2. **Claude Code / Codex en la terminal**: `ge150ctl mcp install` registra el servidor (`claude mcp add ge150 …`,
   `codex mcp add ge150 …`). El usuario conversa directo: "ponme un tono de Gilmour en Comfortably Numb".
3. **Modo rápido (actual)**: se conserva `tone_ai` con JSON de una sola consulta como alternativa (más barata y
   sin MCP) y para tests.

## 4. Experiencia en la GUI

- Botón "✦ Asistente IA" (barra superior) y Ctrl+K → panel de chat (ventana aparte o panel lateral: **a decidir**).
- Selector de proveedor (Claude / Codex) y modo (Agente MCP / Rápido).
- Mientras trabaja: "Claude está leyendo el preset…", "aplicando AMP: J800…" (una línea por herramienta llamada).
- Cada respuesta: nombre del tono, explicación, cambios por módulo, botones **Deshacer** y **Guardar en…**.
- Sugerencia de IR: si la IA recomienda una cabina de TONE3000, aparece una tarjeta con autor, licencia y botón
  "Cargar en ranura N".
- Todo el diseño visual se muestra al usuario antes del commit.

## 5. TONE3000

Fuente: API oficial (`https://www.tone3000.com/api`, beta desde 2025-06). Condiciones para desarrolladores
independientes: gratis, respetando sus requisitos de diseño (mostrar autor con nombre y avatar, marca TONE3000 y un
acceso permanente al catálogo) y los flujos OAuth permitidos.

### 5.1 Autenticación

- OAuth 2.0 con PKCE. El usuario crea en su cuenta de TONE3000 una clave de aplicación (`client_id` publicable) y
  registra el redirect `http://127.0.0.1:53682/callback` (puerto fijo a definir).
- La app abre el navegador, recibe el código en un servidor HTTP local de un solo uso y lo canjea por tokens.
- Tokens guardados en el llavero del sistema (Secret Service vía `secretstorage`/`keyring`); si no hay llavero,
  `~/.config/ge150/tone3000.json` con permisos 0600. Renovación automática; `invalid_grant` → volver a iniciar sesión.
- Alternativa sin navegador: flujo de dispositivo (RFC 8628), solo para iniciar sesión.

### 5.2 Flujos

| Flujo | Uso |
|---|---|
| **Select** (`prompt=select_tone`) | Recomendado por TONE3000 para navegar: abre su catálogo en el navegador, el usuario elige una IR y la app recibe el `tone_id`. |
| **Load Tone** (`prompt=load_tone`) | Cuando la IA ya propuso un `tone_id`: verifica acceso y lo carga. |
| **Búsqueda** (`GET /api/v1/tones/search?format=ir&gears=cab&query=…`) | Para la IA (`tone3000_search`). Límite 100 pedidos/min; caché local de resultados 24 h. |

### 5.3 Descarga y carga en la pedalera

1. `GET /api/v1/models?tone_id=…` → `model_url` de cada IR del tono (un tono puede traer varias: distintos
   micrófonos/posiciones; el usuario elige).
2. Descargar el WAV a `~/.cache/ge150/tone3000/<tone_id>/` (verificar que sea WAV; tamaño máximo razonable).
3. `formats/wav_ir.load_ir_file` (ya existe: remuestreo a 44,1 kHz, 512 muestras de 24 bits).
4. `Editor.upload_user_slot(Op.USER_IR, slot, nombre, datos)` → confirmación del usuario (persistente).
5. Guardar metadatos en `~/.local/share/ge150/ir_sources.json`: ranura → tone_id, autor, licencia, URL. La galería
   de CAB muestra autor y licencia de las IR de usuario que vinieron de TONE3000.

### 5.4 Requisitos de diseño de TONE3000

- Autor (nombre y avatar) y licencia junto a cada IR descargada.
- Logo/marca TONE3000 en el panel y enlace permanente "Explorar TONE3000".
- Respetar `license` de cada tono (por ejemplo, `cc-by-nc`): solo uso personal; no redistribuir IR en el repo ni en
  paquetes.

## 6. Fases

| Fase | Contenido | Aceptación |
|---|---|---|
| **11.1 Núcleo MCP ✅** | `ge150/mcp/tools.py` (lógica, sin transporte, reutiliza `tone_ai` y `Editor`), `ge150/mcp/server.py` (FastMCP del SDK `mcp`), ejecutable `ge150-mcp` (stdio) y `ge150ctl mcp install`. Extra opcional `[ai]` en `pyproject.toml`. | Claude Code en la terminal lee el preset y cambia un parámetro en el simulador y en la pedalera; tests con un cliente MCP en memoria. |
| **11.2 Servidor embebido ✅** | Servidor HTTP local dentro de la GUI (hilo propio, token, archivo de descubrimiento), proxy de `ge150-mcp` hacia la app, diálogos de confirmación. | Con la GUI abierta, Claude Code cambia el tono y la GUI se actualiza al instante; `save_preset` pide permiso en la GUI. |
| **11.3 Chat agente en la GUI** | El panel lanza `claude -p` / `codex exec` con el MCP de la app, muestra el progreso, Deshacer y Guardar. Diseño aprobado por el usuario. | Pedido real ("tono de Slash") resuelto en < 60 s con la pedalera; Deshacer vuelve al estado previo exacto. |
| **11.4 TONE3000: cuenta y descarga (CLI ✅, GUI pendiente)** | `services/tone3000.py` (OAuth PKCE, cliente REST, caché), flujo Select, descarga, conversión y carga en ranura, metadatos y atribución. | Iniciar sesión, elegir una IR en TONE3000, cargarla en una ranura y verla con autor/licencia en la galería. |
| **11.5 TONE3000 en la IA ✅ (herramientas)** | Herramientas `tone3000_search` / `tone3000_get` / `load_ir(source="tone3000:…")`; la IA sugiere IR y el usuario confirma. | "Tono de Slash con una IR real de Marshall 1960" termina con una IR descargada en una ranura (tras confirmar). |
| **11.6 Documentación** | README, `plan.md`, guía de configuración de TONE3000 y de los clientes MCP. | Otra persona configura todo siguiendo la guía. |

## 7. Archivos nuevos (estimado, todos < 1000 líneas)

```
src/ge150/mcp/__init__.py
src/ge150/mcp/tools.py         # lógica de herramientas (testeable sin MCP)          ~350
src/ge150/mcp/server.py        # registro FastMCP, transportes stdio/HTTP, token      ~250
src/ge150/mcp/install.py       # registrar en Claude Code / Codex                     ~120
src/ge150/services/tone3000.py # OAuth PKCE, REST, caché, descarga                    ~400
src/ge150/services/ir_sources.py  # metadatos de IR de usuario                        ~100
src/ge150/ui/ai_panel.py       # chat agente (reemplaza ai_dialog.py)                 ~450
src/ge150/ui/tone3000_dialog.py   # cuenta, Select, elegir ranura                     ~350
src/ge150/ui/confirm.py        # confirmaciones de la IA                              ~120
tests/test_mcp_tools.py, tests/test_mcp_server.py, tests/test_tone3000.py (HTTP simulado)
```

Dependencias nuevas (extra opcional `ai`): `mcp` (SDK oficial, 2.x), `keyring`. HTTP a TONE3000 con `urllib` o
`httpx` (el SDK de MCP ya trae `httpx`).

## 8. Pruebas

- **Herramientas MCP**: contra el simulador (`FakeGE150`), sin red ni IA: cada herramienta, validación, avisos,
  undo, confirmaciones rechazadas/aceptadas.
- **Servidor**: cliente MCP del SDK en memoria (stdio) y HTTP local con token correcto/incorrecto.
- **TONE3000**: servidor HTTP falso (OAuth, búsqueda, models, WAV); nunca la API real en tests.
- **Extremo a extremo manual** (con el usuario): Claude y Codex, pedalera real, IR real de TONE3000.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cuota de la suscripción (Claude Pro / ChatGPT Plus) | Catálogo bajo demanda vía `get_catalog`; modo rápido como alternativa; mostrar duración y pasos. |
| La IA hace cambios no deseados | Solo edit buffer en vivo; Deshacer; persistentes con confirmación; lista negra de operaciones destructivas. |
| Dos dueños del USB | Un solo dueño (la app); `ge150-mcp` hace de proxy si la app está abierta. |
| Cambios en la API de TONE3000 (beta) | Cliente aislado en `services/tone3000.py`, tests con servidor falso, errores claros. |
| Licencias de IR | Mostrar licencia, guardar origen, no versionar IR descargadas. |
| Flags de las CLI cambian entre versiones | Detectar versión (`claude --version`, `codex --version`) y probar flags al iniciar; mensaje claro si faltan. |

## 10. Decisiones del usuario (2026-11-21)

1. Asistente en un **panel lateral** fijo (no ventana aparte); `ui/ai_dialog.py` (prototipo) se convierte en
   `ui/ai_panel.py`.
2. **La IA no guarda presets**: solo cambia en vivo; guardar es siempre del usuario desde la GUI. `save_preset` no se
   expone por MCP. Cargar una IR (TONE3000 o WAV) sí, con confirmación, porque ocupa una ranura.
3. Se mantiene el **modo rápido** (JSON de una consulta) junto al modo agente.
4. Logo en la barra superior aprobado.
5. Orden: **11.1** (MCP para la terminal) → **11.4** (TONE3000 sin IA) → **11.2/11.3** (servidor embebido y chat
   agente) → **11.5** → **11.6**. Pendiente: puerto del redirect de TONE3000.

## 11. Registro

- **11.1 (2026-11-21):** `ge150/mcp_server/` (`tools.py`, `server.py` con `MCPServer` del SDK `mcp` 2.3 —
  `FastMCP` se renombró en 2.x y los campos usan snake_case—, `install.py`), ejecutable `ge150-mcp`,
  `ge150ctl mcp-install`, extra `[ai]`. Probado de punta a punta con el simulador: Claude Code (`claude -p
  --mcp-config … --allowedTools "mcp__ge150__*"`, 10 llamadas, 20 s, tono de Gilmour) y Codex (`codex exec -c
  mcp_servers.ge150…`, clean funk). Ojo: `--allowedTools` es variádico; el pedido va por stdin.
- **11.4 CLI (2026-11-21):** `services/tone3000.py` (OAuth PKCE con redirect loopback
  `http://127.0.0.1:53682/callback`, `prompt=select_tone` con `format=ir`, tokens en `~/.config/ge150/tone3000.json`
  0600 con refresco, `GET /tones/{id}`, `GET /models?tone_id=` → `model_url` con Bearer, verificación RIFF, caché en
  `~/.cache/ge150/tone3000/`, atribución en `~/.local/share/ge150/ir_sources.json`) y `ge150ctl t3k-key|login|logout|
  status|load`. Probado contra un servidor TONE3000 falso; **falta probar con la API real** (requiere la clave del
  usuario y confirmar que TONE3000 acepta un redirect `http://127.0.0.1`). Endpoints tomados de la documentación
  oficial (www.tone3000.com/api).
- **11.2 (2026-11-21):** en vez de servir MCP por HTTP, el editor sirve las mismas herramientas como JSON simple
  en `127.0.0.1` (puerto y token aleatorios, `mcp_server/bridge.py`, solo biblioteca estándar) y escribe
  `$XDG_RUNTIME_DIR/ge150/mcp.json` (0600). `ge150-mcp` lo encuentra y reenvía cada llamada (`RemoteTools`): una sola
  configuración en Claude Code/Codex sirve con o sin el editor abierto (`--standalone` fuerza abrir la pedalera).
  Las llamadas comparten el candado del `TaskRunner` de la GUI; la barra de estado muestra la actividad de la IA.
  `save_preset` y `load_tone3000_ir` piden confirmación en un diálogo del editor (sin editor se rechazan).
  Probado con la GUI en el simulador y `ge150-mcp` por stdio.
- **11.5:** herramientas `tone3000_search` (con aviso de límite de búsquedas), `tone3000_get` y
  `load_tone3000_ir(slot, tone_id=0 → catálogo en el navegador)`; el diálogo muestra autor y licencia.
