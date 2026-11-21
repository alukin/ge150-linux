# GE150 Linux — Plan maestro del proyecto

> Documento de traspaso. Cualquier agente (humano o IA) debe poder retomar el proyecto
> leyendo **solo este archivo**. Mantenerlo actualizado: al cerrar cada tarea, marcar
> checkboxes, mover hallazgos de "Desconocido" a "Verificado" y anotar la fecha.

- **Objetivo:** port nativo para Linux del editor oficial *Mooer Studio for GE150* (Windows, v1.3.8),
  que permita **administrar por completo** la pedalera Mooer GE150 por USB: presets, edición en vivo,
  ajustes de sistema, pedal de expresión, rhythm, carga de IR (cabinas) y NR (capturas de amplificador),
  backup/restore, importar/exportar presets y, en la última fase, actualizar el firmware.
- **Fecha de inicio del análisis:** 2026-11-21.
- **Estado:** fase 0 (ingeniería inversa estática) completada. Aún no hay código de la app.
  Casi todo lo de abajo sale de análisis estático y debe confirmarse con hardware (fase 2).
  Los descriptores USB/HID sí están verificados con el equipo real (2026-11-21, ver 2.1).

---

## 0. Reglas del proyecto (obligatorias para todo agente)

1. **Límite de tamaño:** ningún archivo de código supera **1000 líneas**. Objetivo: ≤ 600.
   Si un archivo pasa de 800 líneas, se divide antes de seguir.
   *Excepciones permitidas:* archivos `.md`, datos generados (`effects.json`), fixtures de tests
   (capturas USB, binarios de ejemplo), hojas de estilo `.qss`, `pyproject.toml`, lockfiles.
2. **Leyenda de evidencia.** Todo dato del protocolo lleva su nivel:
   - **[V]** Verificado: decompilación inequívoca o comprobado con cálculo o hardware.
   - **[I]** Inferido: deducción razonable del código, pendiente de confirmar con hardware.
   - **[?]** Desconocido: hay que investigarlo.
   No se promueve nada a [V] sin evidencia (captura USB, test contra hardware o cita de la decompilación).
3. **No redistribuir material del fabricante.** `reference/` (instalador, binarios, decompilación,
   imágenes y recursos Qt extraídos) **no se versiona** (`.gitignore`). Al repo solo van código propio
   y datos funcionales derivados (nombres de efectos y rangos de parámetros, en formato propio).
4. **Nunca enviar al dispositivo comandos destructivos** (reset de fábrica `0x8B`, restore `0xBA`,
   firmware `0xAA`, borrado de IR/NR) sin confirmación explícita del usuario en la UI o la CLI,
   y nunca desde tests automáticos contra hardware real.
5. Toda capa por debajo de la UI debe poder probarse **sin hardware** usando el simulador (`sim/`).
6. Idioma: código, identificadores y docstrings en inglés. Documentación y textos al usuario en
   español, con la UI internacionalizable (Qt `tr()`).

---

## 1. Inventario del software original

### 1.1 Cómo se obtuvo (reproducible)

El instalador es *Smart Install Maker 5.04*: 7z, innoextract y REA no lo abren. Se instaló en
silencio con wine dentro de un prefijo aislado:

```bash
export WINEPREFIX=/tmp/ge150-wine WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
wine GE150_V1.3.8_Win/Mooer_GE150_WIN_Setup_V1.3.8.exe /S
cp -r "$WINEPREFIX/drive_c/Program Files (x86)/Mooer Audio Corp/Mooer Studio for GE150" reference/win_install
# Recursos Qt embebidos (argumentos de qRegisterResourceData en 0x446cb0: v2, tree, names, data)
python3 -I tools/extract_qrc.py reference/win_install/MOOER_GE150/MOOER_GE150.exe \
        0x4503e0 0x450d80 0x451960 2 reference/qrc
```

### 1.2 Componentes

| Archivo | Qué es |
|---|---|
| `GE150.exe` (MSVC, ATL, **libusb estático**) | **Lanzador y actualizador de firmware.** Busca el USB, identifica el equipo (opcode `0x00`), compara la versión del firmware con `config.ini → [Device] AppVersion=V1.3.8`. Si coincide, lanza `MOOER_GE150\MOOER_GE150.exe <dirección_usb>`; si no, ofrece actualizar con `Firmware\*.mr`. Su PDB se llama "Mooer Studio For GE250": el código es compartido con otros modelos. |
| `MOOER_GE150/MOOER_GE150.exe` (MinGW, **Qt 5**, `libusb-1.0.dll`) | **Editor.** `argv[1]` = dirección USB del dispositivo (`libusb_get_device_address`). Toda la gestión de la pedalera ocurre aquí. |
| `Firmware/MOOER_GE150.mr` (1 123 968 B) | Imagen de firmware. Cabecera: `"Mooer_TAG"` + `"MOOER_GE150"` (rellenado con ceros) + bytes de versión en 0x29. |
| `config.ini` | `[Device] Name='MOOER_GE150'`, `AppVersion=V1.3.8`. |
| Recurso Qt `:/preset/preset/preset.xml` | **Catálogo de efectos** (módulos, modelos, parámetros y rangos). Copia local: `reference/qrc/preset/preset/preset.xml`. |
| Recursos Qt `:/img/...`, `:/qss/...`, `Helvetica.ttf` | Imágenes y estilos de la UI original: solo como referencia visual, no se reutilizan. |
| `MOOER_GE150/presetfile/` | Carpeta (vacía) donde la app guarda presets exportados `.mo`. |

### 1.3 Material de referencia local (no versionado)

| Ruta | Contenido |
|---|---|
| `reference/win_install/` | Instalación completa extraída. |
| `reference/qrc/` | Recursos Qt extraídos (incluye `preset.xml` y los `.qss`). |
| `reference/decompiled_MOOER_GE150/functions/0x<addr>.c` | Pseudocódigo Ghidra 12.2 (vía REA) de las 479 funciones del editor. |
| `reference/decompiled_GE150_launcher/functions/` | Pseudocódigo de las 905 funciones del lanzador/updater. |
| `reference/rea_evidence_bundle.json` | Bundle de evidencia REA (se restaura con `import_evidence_bundle`). |
| `tools/extract_qrc.py` | Extractor de recursos rcc de Qt (v1/v2) embebidos en un PE (ya escrito). |

Nota: Ghidra **no creó funciones** en `0x415040–0x4153a0` del editor (el hilo emisor con su switch).
Esa zona se leyó con `objdump -d -M intel --start-address=0x415040 --stop-address=0x4153b0`.

---

## 2. Protocolo USB

### 2.1 Identificación USB

**Equipo real (verificado con `lsusb -v` y sysfs, 2026-11-21) [V]:**

```
ID 0483:5703 STMicroelectronics GE150   bcdDevice 0x00C8   iSerial 00000000001A   Full Speed
1 configuración (bConfigurationValue=1, self powered), 1 sola interfaz:
  Interfaz 0: clase 3 (HID), sin subclase ni protocolo, driver del kernel: hid-generic → /dev/hidrawN
    EP 0x81 IN   Interrupt 64 B  bInterval 2
    EP 0x02 OUT  Interrupt 64 B  bInterval 2
Report descriptor (27 B): 05 01 09 00 a1 01 15 00 25 ff 19 01 29 08 95 40 75 08 81 02 19 01 29 08 91 02 c0
  → SIN Report ID; Input de 64 × 8 bits; Output de 64 × 8 bits.
```

- Por PID/bcdDevice, el lanzador la trata como **modo 5** (layout de identificación estándar, ver 2.10).
- **No hay interfaz de audio USB.** "OTG LEVEL" es otra cosa (probablemente el nivel de salida
  hacia un móvil por el jack/OTG) **[I]**.
- `/dev/hidrawN` es `root:root 0600` por defecto: hace falta una regla udev (5.5).

Detalle del análisis estático:

- **VID `0x0483`** (STMicroelectronics) **[V]**.
- El lanzador clasifica por PID y `bcdDevice` (`GE150.exe` `FUN_004086a0`) **[V]**:

  | PID | bcdDevice | modo interno | Comentario |
  |---|---|---|---|
  | `0x5703` | `0x00CA` | 4 | identificación estándar |
  | `0x5750` | `0x00CA` | 3 | no envía identificación: probablemente **bootloader/DFU** **[I]** |
  | `0x5750` | `0x00C8` | 1 | respuesta de identificación con otro layout |
  | `0x5703` | `0x00C8` | 5 | identificación estándar |
  | `0x1412` | `0x00C8` | 6 | layout desplazado 1 byte |
  | `0x1512` | `0x00C8` | 7 | estándar |
  | `0x1522` | `0x00C8` | 8 | estándar |

  La GE150 real es **`0x5703` / `0x00C8` (modo 5) [V]**. El resto son otros modelos Mooer
  (el código es compartido) o el bootloader. La app debe aceptar `0x5703` y confirmar el modelo
  por el **nombre "MOOER_GE150"** que devuelve la identificación.
- **Interfaz:** se usa siempre la interfaz **0** (`libusb_claim_interface(h, 0)`), después de
  `libusb_set_configuration(cfg.bConfigurationValue)` **[V]**. Es una interfaz HID (ver arriba).
- **Endpoints** (`FUN_00413740`, clasificados por `bmAttributes & 3`) **[V]**:
  - Interrupt OUT (dirección < 0x10): **envío de comandos** → `0x02` en el equipo real.
  - Interrupt IN (dirección ≥ 0x80): **recepción** → `0x81` en el equipo real.
  - Bulk: el editor tiene una función de lectura bulk de 512 B (`FUN_00413230`), pero la GE150
    **no tiene endpoints bulk** [V]: es código de otro modelo y no se implementa.

### 2.2 Capa de transporte: reportes de 64 bytes

- **Envío [V]** (`FUN_00413080`): la trama completa se parte en trozos de **63 bytes**.
  Cada trozo viaja en un reporte interrupt OUT de **64 bytes**: `report[0] = n` (bytes útiles, 1..63),
  `report[1..n] = datos`. Timeout de 500 ms.
- **Recepción [V]** (`FUN_00417080` → `FUN_004135c0` → `FUN_00416960`): bucle de lectura interrupt IN
  de 64 bytes (timeout 500 ms). Los bytes desde `report[1]` se acumulan en un buffer (0x2800 B) y se
  **re-sincroniza buscando `AA 55` y validando el CRC**. Verificado en hardware: `report[0]` es la
  longitud útil también en los reportes IN (`3f …`, `06 …`). El decodificador debe ser robusto: buscar `AA 55`, leer la
  longitud, esperar a tener la trama completa, validar el CRC y, si falla, descartar 1 byte y reintentar.
- `LIBUSB_ERROR_TIMEOUT (-7)` en lectura = no hay datos (normal).
  `LIBUSB_ERROR_NO_DEVICE (-4)` = desconexión: cerrar y emitir el evento "disconnected".
- **En Linux con hidraw** (transporte recomendado, 5.2): como el descriptor no usa Report ID,
  `write()` recibe **65 bytes** (`0x00` + el reporte de 64) y `read()` devuelve los 64 bytes del
  reporte. El contenido de los 64 bytes es el mismo que en libusb **[V]**.
  `ENODEV`/`EIO` = desconexión.

### 2.3 Trama

```
offset  tamaño  campo
0       1       0xAA
1       1       0x55
2       2       LEN  (uint16 little-endian) = número de bytes de PAYLOAD
4       LEN     PAYLOAD = [OPCODE (1 B)] [DATOS (LEN-1 B)]
4+LEN   2       CRC16 (big-endian: byte alto primero)
total = LEN + 6
```

**CRC [V]:** CRC-16/GSM (poly `0x1021`, init `0x0000`, sin reflexión, xorout `0xFFFF`), calculado
sobre `LEN(2 B) + PAYLOAD`, es decir, los bytes `[2 .. 4+LEN)`. Tabla en `0x44dd60` del editor.
Comprobado con la trama de identificación del lanzador: `AA 55 02 00 00 00 12 97`
(CRC de `02 00 00 00` = `0x1297`).

```python
def crc16_gsm(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc ^ 0xFFFF
```

Valores multibyte dentro de los DATOS: **uint16 little-endian [V]**, salvo el CRC.

### 2.4 Convención de opcodes

- Lectura/escritura desde el host: opcode con el bit 7 activo (`0x80 | x`).
  La respuesta o notificación del dispositivo usa el mismo opcode **sin** ese bit (`x`) **[I]**,
  con pares confirmados: `0xA4↔0x24`, `0x98↔0x18`, `0xB3↔0x33`, `0xA0→0x20`, `0xB0→0x30`, `0xC1→0x41`,
  `0x8C→0x0C`, `0xC4→0x44`, `0x82..0x8A↔0x02..0x0A`.
- Las peticiones de lectura llevan 1 byte de datos con valor `0x01`.
- El editor encola opcodes en una cola circular de 256 B (`0x497360`) y un hilo emisor
  (`0x415040`) los saca, arma el payload desde el estado global y llama a `send_frame`.
  Tras cada envío espera 5 ms; tras los envíos multiparte, 100 ms.

### 2.5 Host → dispositivo

| Opcode | Datos | Función | Evidencia |
|---|---|---|---|
| `0x00` | `00` | **Identificar** (lanzador). Antes se envían 8 bytes a cero. | [V] `GE150.exe FUN_00408a30` |
| `0x31` | `01` | Lo envía el editor al arrancar. **En hardware no tiene respuesta [V]**; quizá "editor conectado" [?] | [V] `FUN_00416190` |
| `0xA0` | `01` | Leer los **200 presets** → 200 × `0x20` | [V] `FUN_00416110` |
| `0xB0` | `01` | Leer el preset/buffer de edición actual → `0x30` | [V] `FUN_00416150` |
| `0xC1` | `01` | Leer los nombres de IR/NR de usuario → `0x41` | [V] `FUN_004161d0` |
| `0x8C` | `01` | Leer la configuración de Rhythm → `0x0C` | [V] `FUN_00416210` |
| `0x82..0x8A` | bloque del módulo (u16[]) | **Escribir módulo** en vivo. `0x82`+índice (ver 2.7) | [V] tablas `0x44d880`, `0x44e360`, `FUN_0041a9c0` |
| `0x96` | `slot` (1..200) | **Seleccionar preset** | [V] `0x4152e0` |
| `0x97` | `slot(1..200)` + nombre 15 B (ASCII, relleno con 0; se recorta a 15) | **Renombrar** preset | [V] `FUN_00414ed0` |
| `0x98` | 3 × u16 (EXP bloque A) | Escribir EXP: `MODULE_CTRL, PARA_CTRL, FUN_SWITCH` | [V] envío / [I] orden |
| `0xB3` | 3 × u16 (EXP bloque B) | Escribir EXP: `VOL_SWITCH, VOL_MIN, VOL_MAX` | [V] envío / [I] orden |
| `0x8D` | 6 B | Escribir Rhythm (BPM, etc.) | [V] envío / [?] campos |
| `0xA4` | 2 B | Ajuste de sistema #1 | [V] envío / [?] cuál |
| `0xA5` | 2 B | Ajuste de sistema #2 | [V] envío / [?] |
| `0xA6` | 4 B | Ajuste de sistema #3 (p. ej. CAB-L/CAB-R THRU) | [V] envío / [?] |
| `0xA7` | 2 B | Ajuste de sistema #4 | [V] envío / [?] |
| `0xB4` | u16 `page` | Sincronizar página o modo de la UI con la pantalla del equipo (antes de cada ajuste de sistema se envía la página; `5` antes de guardar un preset) | [V] envío / [I] semántica |
| `0xC3` | `slot(1..200)` + nombre 14 B + 72 × u16 (LEN = 0xA0) | **Escribir preset completo** en un slot. El editor envía antes `0xB4 page=5` | [V] `FUN_00414d50`, `0x415160` |
| `0xC4` | `01` | Pedir **volcado de backup** → stream `0x44` | [V] `FUN_004389d0` |
| `0xBA` | `01` | Inicio de **restore** de backup | [V] `FUN_00437a00` |
| `0xBB` | `01` | Fin de restore | [V] |
| `0x8B` | `01` | **Reset de fábrica** ("The device will be reset. Please make a data backup."); después la app se cierra | [V] |
| `0xB5` | multiparte | **Subir o borrar IR** (cabina de usuario) | [V] `FUN_004153b0`, `FUN_004149b0` |
| `0xB7` | multiparte | **Subir o borrar NR** (captura de amplificador) | [V] |
| `0xAA` | `00` | Entrar en **modo actualización de firmware** (lanzador) | [V] `GE150.exe FUN_004026b0` |

### 2.6 Dispositivo → host (despachador `FUN_00416250`)

| Opcode | Datos | Significado | Evidencia |
|---|---|---|---|
| **`0x01`** | 62 B, ver 2.10 | Respuesta a `0x00` (nombre, versiones). **Opcode `0x01`, no `0x00`** | [V] hardware |
| `0x02..0x0A` | bloque del módulo | Cambio de un módulo (al girar un knob en la pedalera o como respuesta) | [V] |
| `0x0C` | 6 B | Configuración de Rhythm | [V] |
| `0x16` | `slot` | El equipo cambió de preset (footswitch) | [V] |
| `0x17` | `slot` + nombre 14 B | Nombre de preset actualizado | [V] |
| `0x18` | 3 × u16 | EXP bloque A | [V] |
| `0x20` | `slot` + nombre 14 B + parámetros (la app copia 0x94 B; usar 72 × u16) | **Volcado de un preset** (uno por slot, del 1 al 200) | [V] |
| `0x24`/`0x25`/`0x26`/`0x27` | 2/2/4/2 B | Ajustes de sistema individuales | [V] |
| `0x30` | `slot` + `page`(1 B) + parámetros | Buffer de edición actual | [V] |
| `0x32` | 10 B (= bloques 0x24..0x27 concatenados) | Todos los ajustes de sistema. **Llega sola justo después del preset 200 del volcado `0xA0`** | [V] hardware |
| `0x33` | 3 × u16 | EXP bloque B | [V] |
| `0x34` | `page` | Página o modo actual del equipo | [V] |
| `0x41` | 10 nombres × 16 B + 10 nombres × 16 B (offset +0xA0) | Nombres de IR y NR de usuario (los bytes ≥ 0x80 se convierten en espacio) **[?]** cuál lista es cuál | [V] |
| `0x43` | 1 B | **[?]** desconocido (se guarda en `0x49f3bc`) | [V] |
| `0x44` | `idx`, … | Trozo de backup. `idx=0`: `data[1]` = total de trozos. `idx>0`: `data[1]` = ?, y 0x610 B de datos. Termina cuando `idx == total`. | [V] |
| `0xB5` | 1 B estado | ACK o estado de una subida de IR/NR **[I]** | [V] |

### 2.7 Estructura del preset (72 × u16 = 144 B)

Un preset ocupa 0xA0 B en la tabla interna: nombre 14 B (ASCII, se permite `a-z A-Z 0-9 - espacio`),
2 B de relleno y 72 palabras u16. Hay **200 slots** (1..200 en el cable) **[V]**.

| Índice del módulo | Opcode escr./notif. | Palabras u16 | Offset en palabras | Módulo (orden de la cadena) |
|---|---|---|---|---|
| 0 | `0x82`/`0x02` | 6 | 0 | FX/COMP |
| 1 | `0x83`/`0x03` | 5 | 6 | DS/OD |
| 2 | `0x84`/`0x04` | 8 | 11 | AMP |
| 3 | `0x85`/`0x05` | 7 | 19 | CAB |
| 4 | `0x86`/`0x06` | 5 | 26 | NS GATE |
| 5 | `0x87`/`0x07` | 11 | 31 | EQ |
| 6 | `0x88`/`0x08` | 9 | 42 | MOD |
| 7 | `0x89`/`0x09` | 9 | 51 | DELAY |
| 8 | `0x8A`/`0x0A` | 6 | 60 | REVERB |
| — | `0x98`/`0x18` | 3 | 66 | EXP A: `MODULE_CTRL`, `PARA_CTRL`, `FUN_SWITCH` |
| — | `0xB3`/`0x33` | 3 | 69 | EXP B: `VOL_SWITCH`, `VOL_MIN`, `VOL_MAX` |

- Tamaños en bytes **[V]** (`FUN_0041a9c0`: 12,10,16,14,10,22,18,18,12). Orden de módulos y límites
  de bloque **[V]**, comprobados con los máximos por palabra de los 200 presets reales.
- Dentro de cada bloque: `word[0] = SWITCH` (solo 0/1 en los 200 presets) **[V]** y `word[1] = TYPE`
  = **índice del modelo en base 0** (`NN − 1`) **[V]**: en FX, NS, EQ, DELAY y REVERB va exactamente de
  0 a número de modelos − 1. (Una única anomalía: el preset 84 tiene DS `TYPE=54`.)
- **Palabras de parámetros (deducido de 200 presets reales, [I] fuerte):** no siempre siguen el orden del XML.
  Cada módulo tiene posiciones fijas y cada modelo usa las suyas (`tools/build_catalog.py` → `word`):
  | Módulo | Palabras 2.. |
  |---|---|
  | FX, DS, AMP, NS, REVERB | parámetros en orden del XML |
  | CAB | TUBE, MIC, CENTER, DISTANCE; palabra 6 = **siempre 18** [?] |
  | EQ | 2–7 = ganancias de banda 1–6 (16 = 0 dB); 8–10 = FREQ1–3 del CUSTOM EQ (Hz tal cual; por defecto 100/600/1250) |
  | MOD | 2–5 = genéricos en orden del XML; 6 = PITCH de DETUNE (200 = 0,0); 7 = PITCH de PITCH SHIFT (120 = 0,0); 8 = ? (≈50) |
  | DELAY | LEVEL, FEEDBACK, TIME(A), SUB(A), TIME B, SUB B, THRES (DYNAMIC) |
- **Codificación de valores [I] fuerte:** `raw = round((valor − min(mín, 0)) / paso)`. Los rangos
  negativos se desplazan (EQ, PITCH, DETUNE) y los positivos se guardan tal cual (TIME 40..2500 se guarda en ms;
  el mínimo observado es 40). Enumerados = índice de la opción (SUB-D=1 → "1/4" [?] por confirmar en pantalla).
- El orden EXP `MODULE_CTRL, PARA_CTRL, FUN_SWITCH, VOL_SWITCH, VOL_MIN, VOL_MAX` es el del escritor
  `.mo` (`FUN_00422e00`, palabras 66..71) **[V]**. Su reparto entre 0x98 y 0xB3 es **[I]**.

### 2.8 Subida y borrado de IR (`0xB5`) y NR (`0xB7`) [V]

Ranuras: **IR** = CAB 27..36 → `slot` `0x1A..0x23`. **NR** = AMP 56..65 → `slot` `0x37..0x40`
(índice de modelo en base 0). Secuencia de tramas, con 100 ms de pausa entre ellas:

```
parte 0: LEN=5     OP 00 slot 00 01         (cabecera)
parte 1: LEN=0x12  OP 01 nombre[16]         (nombre del archivo sin extensión, máx. 16)
parte 2..k: LEN=0x202  OP n datos[512]     IR: n=2,3,4 (1536 B)   NR: n=2..5 (2048 B)
```

- **IR**: WAV (RIFF/WAVE/fmt/data), con soporte para 44100, 48000, 88200 y 96000 Hz. Se convierte a
  **512 muestras de 24 bits con signo** (float × 8388608, saturado a ±0x7FFFF7) = 1536 B
  (`FUN_0041e770`) **[V]** formato / **[I]** remuestreo a 44.1 kHz (revisar `FUN_0041e5b0`/`FUN_0041e500`).
- **NR**: archivo `*.amp` (`FUN_0041f700`): se valida un bloque de 0x200 palabras y se toman 2048 B **[I]**.
  **[?]** Formato exacto de `.amp`.
- **Borrar** = subir con el nombre `"Empty"` y datos a cero (`FUN_004149b0`) **[V]**.
- Tras la subida, refrescar los nombres con `0xC1`.

### 2.9 Secuencia de arranque

Verificado en hardware (2026-11-21, `ge150ctl send` y `snapshot`) **[V]**:

| Petición | Respuesta |
|---|---|
| `0x00 00` | `0x01` (62 B) |
| `0x31 01` | ninguna |
| `0xA0 01` | 200 × `0x20` (payload de 160 B = op + slot + nombre 14 B + 72 palabras exactas) y después `0x32` (10 B) |
| `0xC1 01` | `0x41` (320 B: 2 × 10 nombres de 16 B; en blanco = `"EMPTY"`) |
| `0x8C 01` | `0x0C` (6 B, p. ej. `00 00 00 0a 04 01`) |
| `0xB0 01` | `0x30` (146 B: slot, page y 72 palabras) |

Secuencia del editor oficial (estática, [I]): `0x31`, `0xA0` → 200 × `0x20` + `0x32`; con los flags
activados tras el preset 200, envía `0xC1` y `0x8C` al recibir `0x32`, y `0xB0` al recibir `0x41`.
Nuestra implementación es **guiada por respuestas** (cada petición con timeout) y no depende de flags.
Los nombres de preset vienen rellenados con **espacios** (0x20), no con NUL.

### 2.10 Identificación y firmware (lanzador `GE150.exe`)

- **Respuesta real a `0x00` [V]** (opcode `0x01`, 62 B de datos, capturada y usada como test):
  ```
  AA 55 3F 00 01 | "MOOER_GE150"[32] | "V1.0.0"[7] | "V1.3.8"[7] | "V1.3.1"[7] | "A"[2] | "V1.1.0"[7] | CRC 8F D9
  ```
  `V1.3.8` = firmware (el campo que el lanzador compara con `AppVersion`). `V1.0.0`, `V1.3.1`, `A` y
  `V1.1.0` están sin identificar [?] (¿bootloader, DSP, revisión de hardware?). Los offsets del lanzador
  (`frame+6`, `+0x2D`…) son relativos al **reporte**, que incluye el byte de longitud, por eso están desplazados en 1.
- El lanzador **solo abre el editor si la versión del firmware coincide** con `AppVersion`. Nuestra app
  solo avisará (no bloqueará) y mostrará la versión.
- **Firmware (`FUN_004026b0`, `FUN_00403de0`) [I]:** `0xAA 00` (entrar en modo update) → `0x00`
  (re-identificar) → espera → trama de 5 B con opcode variable + parámetros de la imagen → por cada
  sección: cabecera en una tabla de bloques de 512 B (tamaño en +0x11, dirección en +0x17,
  CRC16 en +0x1B, tipo en +0x15) y datos → final `0xFF`. La imagen `.mr` tiene una cabecera de
  0x80 B (`Mooer_TAG`, nombre, versión) seguida de `N × 512 B` de tabla de secciones y los datos.
  **Necesita un análisis dedicado antes de implementarlo (fase 9). Riesgo de dejar el equipo inservible.**

---

## 3. Formatos de archivo

| Formato | Uso | Estructura |
|---|---|---|
| `.mo` | Preset exportado | **JSON** (`QJsonDocument`, `FUN_00423300`) **[V]** claves: `fileInfo{device:"MOOER GE150", device_version:"V1.3.0", app:"GE150 Edit", app_version:"V1.3.0", schema:"GE150 Preset"}`, `preset_name`, `effectModule{<módulo>:{SWITCH, TYPE, Data[...]}}`, `Exp{MODULE_CTRL, PARA_CTRL, FUN_SWITCH, VOL_SWITCH, VOL_MIN, VOL_MAX}`. **[?]** Nombres exactos de las claves de módulo y de la jerarquía: obtener un `.mo` real exportado por la app oficial y guardarlo como fixture. |
| `.mbf` | Backup completo (`"GE150 Backup File"`, por defecto `./GE150.mbf`) | Contenedor con secciones `GE150_PRESET` (200), `GE150_RHYTHM`, `GE150_SYSTEM` y `GE150_IR` (10), con entradas de 0x22 B de cabecera. Progreso = 212 unidades. Lector `FUN_00437a00`, escritor `FUN_00436a40`/`FUN_00436920`. El restore reenvía `0xC3` × 200, `0x8D`, `0xA4..0xA7` e IR (`0xB5`) entre `0xBA` y `0xBB`. **[I]** Layout exacto pendiente: decompilar en detalle `0x436a40` y `0x437a00`. |
| `.wav` | IR | Ver 2.8. |
| `.amp` | NR | **[?]** ver 2.8. |
| `.mr` | Firmware | Ver 2.10. |

---

## 4. Catálogo de efectos (de `preset.xml`)

Formato del XML: `<chain name="..."> <MOD name="NN:NOMBRE" paraPos="P" [import="1"]> <para name type>RANGO</para>`.

- Un modelo sin `<para>` **hereda los parámetros** del modelo anterior con el mismo `paraPos`.
- `type="0"`: numérico. `RANGO` = `min_max_step_decimales_[unidad]`
  (ej. `40_2500_1_0_ ms`, `-12_12_0.1_1_`).
- `type="1"`: enumerado. `RANGO` = opciones separadas por `_` (ej. `OFF_EL34_EL84_6L6_6V6`).
- `type="2"`: compuesto (solo en bloques comentados, ignorar).
- `import="1"`: ranura de usuario (IR/NR).

| Cadena | Modelos |
|---|---|
| FX/COMP | 8: CRY WAH, 535 WAH, AUTO WAH, TALK WAH AH/OH, TOUCH WAH, YELLOW COMP, BLUE COMP |
| DS/OD | 20 (TUBE DR … GOLD CLON). Parámetros VOLUME, TONE, GAIN |
| AMP | 55 de fábrica (GAIN, BASS, MID, TREBLE, PRES, MST) + 56..65 NR de usuario (comentados en el XML: la versión 1.3.8 podría no exponerlos en la UI **[?]**) |
| CAB | 26 de fábrica (TUBE, MIC, CENTER, DISTANCE) + 27..36 IR de usuario (`import="1"`, solo TUBE) |
| NS GATE | 3: NOISE KILLER, INTEL REDUCER, NOISE GATE |
| EQ | 4: MOOER G, MOOER HM, MOOER G-6, CUSTOM EQ |
| MOD | 19: PHASER … LOFI |
| DELAY | 9: DIGITAL, ANALOG, REAL, TAPE, MOD, REVERSE, PINGPONG, DYNAMIC, DUAL DELAY |
| REVERB | 7: ROOM, HALL, CHURCH, PLATE, SPRING, MOD, CAVE |

En la fase 1, `tools/build_catalog.py` convierte el XML a `src/ge150/data/effects.json` (formato
propio, con la herencia de `paraPos` ya resuelta y el `TYPE` explícito).

Otras funciones de la UI original (sacadas de los textos `tr()`): lista de presets (Copy, Paste,
Rename, Import, Export, Refresh, Open This Directory), ajustes de sistema (INPUT LEVEL, CAB SIM THRU
con CAB-L/CAB-R, LEFT/RIGHT OUT CAB, OTG LEVEL, SCREEN/BRIGHTNESS, BACKUP/RECALL/RESTORE, RESET,
ABOUT), EXP (EXP VOL PEDAL, VOL MIN/MAX, asignación módulo-parámetro), Rhythm (BPM), gestión de IR/NR
(Select IR File, Select NR File, Delete).

---

## 5. Arquitectura de la app Linux

### 5.1 Stack

| Elección | Por qué |
|---|---|
| **Python ≥ 3.11** | Desarrollo rápido, fácil de retomar por agentes y adecuado para un protocolo de baja tasa. |
| **PySide6 (Qt 6)** | Equivale a la UI Qt original, es LGPL y ya está instalado (6.12). |
| **hidraw** (`/dev/hidrawN`, solo `os`) | Transporte principal: la GE150 es HID sin Report ID, el kernel ya la enlaza con `hid-generic`, no hace falta desenganchar el driver ni tener dependencias extra. |
| **pyusb ≥ 1.2 + libusb-1.0** (fallback) | Es la misma librería que usa el original. Ya está instalado (1.3.1). Requiere `detach_kernel_driver(0)`. |
| `numpy` (opcional) | Remuestreo de IR; con fallback en Python puro. |
| `pytest`, `ruff`, `mypy` | Calidad. |

Alternativa descartada por ahora: C++/Qt6 + libusb. Más trabajo y sin ventajas reales para este
volumen de datos. La separación por capas permite reescribir el núcleo en otro lenguaje si hiciera falta.

### 5.2 Capas

```
UI (PySide6)  ──señales Qt──►  AppController  ──►  Services  ──►  DeviceSession  ──►  Transport
   ▲                              │                    │              │  (hilos)          (pyusb)
   └──────── DeviceState (modelo observable) ◄─────────┴── mensajes decodificados ◄──┘
                                                       Formats (.mo/.mbf/.wav/.amp/.mr)
                                                       Catalog (effects.json)
```

- **Transport:** abrir, cerrar, leer y escribir reportes de 64 B. Sin lógica de protocolo.
  Interfaz abstracta `Transport` con tres implementaciones: `HidrawTransport` (principal; busca el
  `hidrawN` cuyo `HID_ID` sea `0003:00000483:00005703` en `/sys/class/hidraw/*/device/uevent`),
  `UsbTransport` (pyusb, fallback) y `SimTransport`.
- **Protocol:** funciones puras: CRC, `encode_frame`, `split_reports`, `FrameDecoder`
  (stream → tramas válidas), `Opcode` (IntEnum), y codificadores y decodificadores tipados por mensaje.
- **DeviceSession:** hilo lector, cola de envío con hilo emisor (ritmo de 5/100 ms),
  `request(op, data, expect=op&0x7F, timeout)` con futures, y suscripción a notificaciones.
  Emite eventos (`connected`, `disconnected`, `message`).
- **Model:** dataclasses `Preset`, `ModuleBlock`, `ExpSettings`, `SystemSettings`, `RhythmSettings`,
  `UserSlots`, y `DeviceState`, que es la única fuente de verdad (200 presets, buffer actual,
  sistema, nombres de IR/NR) y emite cambios.
- **Services:** casos de uso. `PresetService` (sincronizar, seleccionar, editar módulo, guardar,
  renombrar, copiar/pegar, importar/exportar `.mo`), `SystemService`, `ExpService`, `RhythmService`,
  `UserCabAmpService` (IR/NR), `BackupService`, `FirmwareService` (fase 9).
- **Formats:** lectura y escritura de archivos, sin USB.
- **UI:** solo presentación. Se genera dinámicamente desde `effects.json`: no se escriben widgets por efecto.
- **CLI `ge150ctl`:** usa Services sin la UI. Es imprescindible para depurar y verificar el protocolo.

### 5.3 Árbol de directorios objetivo

```
ge150-linux/
├── plan.md                      # este documento (fuente de verdad)
├── README.md                    # instalación y uso
├── pyproject.toml               # paquete "ge150", entry points: ge150 (GUI), ge150ctl (CLI)
├── .gitignore                   # reference/, GE150_V1.3.8_Win/, __pycache__, .venv
├── udev/70-mooer-ge150.rules    # acceso sin root a hidraw y usb (VID 0483 PID 5703), TAG+="uaccess"
├── packaging/                   # .desktop, icono propio, PKGBUILD (Arch) en el futuro
├── src/ge150/
│   ├── __init__.py, __main__.py, cli.py
│   ├── usb/      transport.py, hidraw_transport.py, usb_transport.py, device_ids.py, hotplug.py
│   ├── protocol/ crc.py, framing.py, opcodes.py, messages.py, session.py
│   ├── model/    catalog.py, preset.py, settings.py, device_state.py
│   ├── services/ reader.py (solo lectura, hecho), presets.py, settings.py, user_slots.py,
│   │             backup.py, firmware.py
│   ├── formats/  mo_json.py, mbf.py, wav_ir.py, amp_nr.py, mr_firmware.py
│   ├── sim/      fake_device.py (emulador con estado), sim_transport.py
│   ├── data/     effects.json (generado), translations/
│   └── ui/       app.py, main_window.py, preset_list.py, chain_view.py, module_editor.py,
│                 param_widgets.py, settings_dialog.py, exp_dialog.py, rhythm_dialog.py,
│                 user_slots_dialog.py, backup_dialog.py, theme.qss
├── tests/        test_crc.py, test_framing.py, test_messages.py, test_session_sim.py,
│                 test_formats_*.py, fixtures/ (capturas .pcapng, .mo/.mbf/.wav de ejemplo)
├── tools/        extract_qrc.py (hecho), build_catalog.py, decode_usbmon.py
└── reference/    (no versionado) ver 1.3
```

### 5.4 Concurrencia

- Un hilo lector bloqueante (`read(ep_in, 64, timeout=500)`) que alimenta el `FrameDecoder`.
- Un hilo emisor que consume una `queue.Queue` de tramas. Respeta las pausas del original:
  ≥ 5 ms entre comandos y 100 ms entre partes multiparte.
- Hacia la UI, solo con señales Qt (`QObject` puente en `ui/app.py`). Nunca tocar widgets desde los hilos USB.
- Edición en vivo: agrupar los cambios de un slider (debounce de ~30 ms) y enviar **el bloque completo
  del módulo** (`0x82+i`), como hace el original.

### 5.5 Linux: permisos y drivers

- Regla udev (`/etc/udev/rules.d/70-mooer-ge150.rules`; recargar con
  `udevadm control --reload && udevadm trigger`):
  ```
  KERNEL=="hidraw*", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5703", TAG+="uaccess", MODE="0660"
  SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5703", TAG+="uaccess", MODE="0660"
  # Bootloader para la fase 9 (PID por confirmar): ATTRS{idProduct}=="5750"
  ```
- Con hidraw no hay que desenganchar nada. Con el fallback pyusb: si `is_kernel_driver_active(0)`,
  hacer `detach_kernel_driver(0)` y volver a enganchar al cerrar.
- Detección de conexión y desconexión: sondeo de `/sys/class/hidraw` cada 1 s, o `pyudev`
  (opcional) para eventos.

---

## 6. Fases, tareas y criterios de aceptación

### Fase 0 — Ingeniería inversa estática ✅ (2026-11-21)
- [x] Extraer el instalador (wine en modo silencioso) y los recursos Qt.
- [x] Decompilar el editor y el lanzador con REA/Ghidra.
- [x] Documentar la trama, el CRC, los opcodes, la estructura del preset, IR/NR, los formatos y el catálogo.

### Fase 1 — Esqueleto y núcleo sin hardware ✅ (2026-11-21)
- [x] `pyproject.toml`, `.gitignore`, `README.md`, configuración de ruff/mypy (strict)/pytest.
      Entorno: `python3 -m venv --system-site-packages .venv` + `pip install -e '.[dev]'`.
- [x] `protocol/crc.py` y `framing.py` con tests (vectores `AA 55 02 00 00 00 12 97` y `AA 55 02 00 A0 01 1F C8`).
- [x] `FrameDecoder` robusto (tramas partidas, basura previa, CRC inválido, cabecera partida).
- [x] `opcodes.py` y `messages.py` con encode/decode de lo descrito en 2.5–2.8.
- [x] `tools/build_catalog.py` → `data/effects.json` (una línea por modelo, `paraPos` resuelto, NR 56–65 añadidos) y `model/catalog.py`.
- [x] `model/preset.py`: layout de 72 u16, `ModuleBlock`, EXP y codificación de nombres. La conversión valor↔raw está en `catalog.Param`.
- [x] `sim/fake_device.py` + `sim/sim_transport.py` (pasa por la misma fragmentación en 64 B que el hardware).
- [x] `protocol/session.py` (hilos lector y emisor, `request`/`collect`, listeners, desconexión) probado contra el simulador.
- [x] `usb/hidraw_transport.py` (principal) y `usb/usb_transport.py` (pyusb), `services/reader.py`, CLI `ge150ctl`.
- **Aceptación cumplida:** 41 tests en verde, ruff y mypy limpios; `ge150ctl --sim presets` lista los 200.

### Fase 2 — Verificación con hardware (requiere la pedalera)
- [x] `lsusb -v` y el descriptor HID de sysfs → anotados en 2.1 (2026-11-21).
- [x] Regla udev instalada (`70-mooer-ge150.rules`: con el prefijo 99 `uaccess` no se aplica) y acceso sin root confirmado.
- [x] `ge150ctl --raw probe`: identificación OK, `report[0]` = longitud confirmado, CRC confirmado con una trama real.
- [x] Lecturas `0xA0`, `0xB0`, `0xC1`, `0x8C` OK; `0x31` sin respuesta; `0x32` tras `0xA0` (ver 2.9).
      Snapshot de la pedalera del usuario en `reference/captures/` (no versionado).
- [x] `TYPE` en base 0, y mapeo de palabras y codificación de valores deducidos de los 200 presets (ver 2.7).
- [ ] Confirmar en pantalla el preset 19 "Burden Clean" (`ge150ctl current`): YELLOW COMP, PURE BOOST,
      65 US TW, CAB 33 (IR de usuario), INTEL REDUCER, HALL; y el valor de SUB-D del DELAY.
- [ ] `ge150ctl sniff`: volcar en hex todas las tramas recibidas durante 30 s mientras se tocan knobs y footswitches.
- [ ] Captura de referencia de la app oficial: Windows en una VM (QEMU/VirtualBox) con USB passthrough y
      `usbmon` + Wireshark en el host Linux (`modprobe usbmon`, capturar en `usbmonN`).
      `tools/decode_usbmon.py` decodifica el `.pcapng` a tramas y opcodes. Capturar: arranque, cambio de
      preset, mover cada tipo de parámetro (incluidos los negativos y fraccionarios), guardar, renombrar, EXP,
      ajustes de sistema, rhythm, subir y borrar un IR, backup. Guardar en `tests/fixtures/`.
- [ ] Resolver los [?] de 2.1, 2.6, 2.7 y 3, y actualizar este documento.
- **Aceptación:** la secuencia de arranque completa funciona contra el equipo real y los 200 nombres coinciden con la pantalla.

### Fase 3 — Lectura completa y CLI
- [ ] `ge150ctl list | show <slot> | select <slot> | get-system | get-exp | get-rhythm | user-slots`.
- **Aceptación:** `show` muestra los módulos con los nombres de modelos y parámetros correctos.

### Fase 4 — Edición en vivo y guardado
- [ ] `set-param <módulo> <param> <valor>`, `toggle <módulo>`, `set-type <módulo> <modelo>`.
- [ ] `save <slot>` (`0xB4 5` + `0xC3`), `rename <slot> <nombre>` (`0x97`), copiar/pegar entre slots.
- **Aceptación:** el cambio se oye y se ve en la pedalera; persiste tras apagar y encender.

### Fase 5 — GUI principal
- [ ] Ventana: lista de 200 presets (con búsqueda), cadena de 9 módulos (on/off y selección), editor
      de parámetros generado desde el catálogo, barra de estado (conexión y versión de firmware).
- [ ] Sincronización bidireccional: los cambios en la pedalera (`0x02..0x0A`, `0x16`, `0x17`) actualizan la UI.
- [ ] Aviso de "preset modificado sin guardar" (como el original).
- **Aceptación:** paridad funcional con la vista principal del editor oficial.

### Fase 6 — Ajustes de sistema, EXP y Rhythm
- [ ] Diálogos de sistema (`0xA4..0xA7`, con `0xB4 page` previo), EXP (`0x98`, `0xB3`) y Rhythm (`0x8D`).
- [ ] Reset de fábrica (`0x8B`) con doble confirmación.

### Fase 7 — IR y NR de usuario
- [ ] `formats/wav_ir.py`: WAV PCM 16/24/32 y float, mono o estéreo (tomar el canal L), remuestreo a
      44.1 kHz, recorte o relleno a 512 muestras y empaquetado a 24 bits. Tests con WAV sintéticos.
- [ ] `formats/amp_nr.py` (requiere un `.amp` de ejemplo).
- [ ] Subir y borrar (`0xB5`, `0xB7`), refrescar nombres (`0xC1`).

### Fase 8 — Archivos: `.mo` y `.mbf`
- [ ] Importar y exportar `.mo`, compatibles con la app oficial (fixtures reales).
- [ ] Backup (`0xC4` → `0x44`) a `.mbf`; restore (`0xBA` … `0xBB`) con barra de progreso de 212 pasos.
- **Aceptación:** un `.mbf` hecho con la app oficial se restaura con la nuestra, y al revés.

### Fase 9 — Actualización de firmware (opcional, alto riesgo)
- [ ] Decompilar en detalle `GE150.exe` `FUN_004026b0`, `FUN_00403de0`, `FUN_00406eb0` y `FUN_00406fd0`.
- [ ] Parser `.mr` con validación de CRC de cada sección; modo `--dry-run` que solo valida.
- [ ] Probar primero con capturas de la app oficial; documentar la recuperación en modo bootloader (PID `0x5750`).

### Fase 10 — Empaquetado
- [ ] `.desktop`, icono propio, instalación de la regla udev, PKGBUILD/AUR, AppImage o Flatpak.

---

## 7. Guía para agentes: cómo continuar

1. Leer este archivo. Ver la próxima casilla sin marcar en la sección 6.
2. Para dudas del protocolo, abrir el pseudocódigo en `reference/decompiled_MOOER_GE150/functions/0x<addr>.c`
   (tabla del apéndice A). Si `reference/` no existe, regenerarlo con 1.1.
3. Para análisis nuevo, usar el MCP **REA** (Ghidra 12.2 instalado): `open_binary` sobre el `.exe`,
   después `procedure_pseudo_code`, `xrefs`, `read_bytes` y `decompile_all`. Para zonas sin función en
   Ghidra, usar `objdump -d -M intel --start-address=… --stop-address=…`.
4. Tras resolver un [?], actualizar la tabla correspondiente, cambiar la etiqueta a [V] y citar la evidencia.
5. Antes de terminar una tarea: `ruff check`, `mypy`, `pytest`, y comprobar que ningún archivo supera 1000 líneas
   (`find src tests tools -name '*.py' | xargs wc -l | sort -n | tail`).

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Semántica de bytes incorrecta (el análisis es estático) | Fase 2 con capturas reales antes de escribir en el equipo; empezar por comandos de lectura. |
| Escritura que corrompe presets | Backup `.mbf` obligatorio antes de la primera prueba de escritura; probar en un slot alto (p. ej. 200). |
| Driver del kernel ocupando la interfaz | Usar hidraw (convive con `hid-generic`); con pyusb, detach solo de la interfaz 0. La GE150 no tiene audio USB, así que no hay riesgo de romperlo. |
| Firmware dejando el equipo inservible | Fase separada, al final, con dry-run y verificación de CRC; nunca automática. |
| Cambios de protocolo en otras versiones de firmware | Guardar la versión en los logs y fixtures; el análisis corresponde al firmware V1.3.8 y la app V1.3.0 (texto interno de About). |

---

## Apéndice A. Funciones clave (MOOER_GE150.exe, imagen base 0x400000)

| Dirección | Rol |
|---|---|
| `0x401780` | `main`: `argv[1]` → dirección USB |
| `0x40af00` | Constructor de la ventana principal; carga `preset.xml` |
| `0x402a00` | Abrir el dispositivo, crear los hilos lector y emisor y conectar señales |
| `0x4031d0` | Peticiones iniciales (`0x31`, `0xA0`) |
| `0x413030` / `0x4135a0` | `libusb_init` / `exit` |
| `0x4139f0` / `0x413900` / `0x413880` / `0x413740` | Abrir por dirección, configurar, reclamar la interfaz 0, clasificar endpoints |
| `0x413080` | Enviar una trama en reportes de 64 B (interrupt OUT) |
| `0x4135c0` | Leer un reporte (interrupt IN) |
| `0x417080` | Bucle del hilo lector |
| `0x416960` | Reensamblado del stream, búsqueda de `AA 55` y validación del CRC |
| `0x416250` | **Despachador de mensajes entrantes** |
| `0x415ff0` | Añadir CRC y enviar |
| `0x414690` / `0x414730` | Armar una trama con payload u16[] / bytes |
| `0x415040` | **Hilo emisor**: switch de opcodes (tabla de saltos `0x44d988`, opcodes `0x8B..0xC4`) |
| `0x414d50` | `0xC3` escribir preset |
| `0x414ed0` | `0x97` renombrar |
| `0x4153b0` | Subir IR/NR desde un archivo |
| `0x4149b0` | Borrar IR/NR |
| `0x414820` | Subir IR desde un backup |
| `0x41e0c0` / `0x41e770` | Lector de WAV y conversión a 24 bits |
| `0x41f700` | Lector de `.amp` (NR) |
| `0x422e00` / `0x423300` | Claves JSON y escritor `.mo` |
| `0x436a40` / `0x437a00` | Escritor y lector (restore) de `.mbf` |
| `0x4389d0` | Backup (`0xC4`) |
| `0x41a9c0` | Tamaños de los bloques de módulo |
| Datos | `0x44dd60` tabla CRC; `0x44d880` opcodes de módulo; `0x44e360` opcode → índice; `0x44e420` punteros a bloques; `0x4974a2` tabla de 200 presets (paso 0xA0); `0x49f1b2` buffer actual |

**GE150.exe:** `0x40cc70` WinMain (comprobación de versión); `0x4086a0` VID/PID → modo;
`0x408a30` identificación `0x00`; `0x408d80` parseo de la identificación; `0x407d80` envío en reportes
de 64 B; `0x403b40` envío con CRC; `0x4026b0` flujo de actualización de firmware; `0x40d3a0` lanza el editor.
