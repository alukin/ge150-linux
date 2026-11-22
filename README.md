<p align="center"><img src="docs/logo.svg" alt="GE150 Editor" width="560"></p>

# ge150-linux

Editor libre para Linux de la pedalera **Mooer GE150**: interfaz gráfica (`ge150`) y línea de comandos
(`ge150ctl`). El protocolo USB se obtuvo por ingeniería inversa del software oficial *Mooer Studio for GE150*
(Windows). El protocolo, la arquitectura y la hoja de ruta están en [`plan.md`](plan.md).

> **Estado:** todo lo de abajo está verificado con una pedalera real (lectura, edición en vivo, guardar,
> renombrar, IR, NR, backup y restore). Aun así, haz un `ge150ctl backup` antes de cambios grandes.
> Tras un restore la pedalera se reinicia sola; el editor espera a que vuelva.

## Qué puede hacer

- Leer los 200 presets, el preset actual decodificado (modelos y parámetros), los IR de usuario y el
  estado del pedal de expresión.
- Editar en vivo: encender/apagar módulos, cambiar el modelo y mover parámetros.
- Guardar, renombrar y copiar presets.
- Ver y cambiar los ajustes de sistema (INPUT LEVEL, SCREEN, CAB SIM THRU, OTG LEVEL) y la caja de ritmos.
- Importar y exportar presets `.mo`, compatibles con la app oficial.
- Cargar IR desde WAV a las ranuras de usuario (CAB 27-36), borrarlas y exportarlas a WAV.
- Cargar capturas NR (`.amp`) a las ranuras de amplificador de usuario (AMP 56-65).
- Backup completo y restauración en formato `.mbf`, compatible con la app oficial.
- Seguir los cambios hechos en la propia pedalera (footswitch, knobs).

## Instalación en Arch Linux

```bash
cd packaging && makepkg -si     # instala ge150, ge150ctl, la regla udev, el .desktop y el icono
```

## Instalación (desarrollo)

```bash
python3 -m venv --system-site-packages .venv   # reutiliza PySide6 y pyusb del sistema
.venv/bin/pip install -e '.[dev]'              # '.[gui]' instala PySide6 si no lo tienes
```

Acceso a la pedalera sin root (una sola vez):

```bash
sudo cp udev/70-mooer-ge150.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

## Interfaz gráfica

```bash
ge150            # con la pedalera conectada
ge150 --sim      # con el simulador, sin hardware
```

- Abajo, siempre visible, la cadena de efectos: cada módulo con la imagen de su equipo, el modelo y su
  botón de encendido. Un clic abre su página.
- Un clic en la lista de la izquierda carga el preset (si hay cambios sin guardar, pregunta antes).
- La página del módulo muestra el equipo original en grande (foto o dibujo), una galería con todos los
  modelos para elegir y perillas: se giran arrastrando, con la rueda o con las flechas, y con doble clic se
  escribe el valor.
- En las cabinas, el micrófono se arrastra frente al parlante para cambiar CENTER y DISTANCE.
- Fotos propias: pon `<id>.jpg` o `.png` en `~/.local/share/ge150/photos/` (el `id` de cada equipo está en
  `src/ge150/data/gear.json`). Tienen prioridad sobre las incluidas; si no hay foto, se dibuja el equipo.

## Línea de comandos

```bash
ge150ctl probe                         # nombre y versión del firmware
ge150ctl presets                       # los 200 nombres
ge150ctl current                       # preset actual decodificado
ge150ctl snapshot --out ge150.json     # copia de todo lo legible: hazla antes de escribir
ge150ctl models delay                  # modelos de un módulo (sin pedalera)

ge150ctl set reverb level 40           # en vivo (no se guarda)
ge150ctl off mod / on mod
ge150ctl type amp "65 US TW"           # o por número: type amp 2
ge150ctl select 12

ge150ctl system                        # INPUT LEVEL, SCREEN, CAB SIM THRU, OTG LEVEL
ge150ctl system-set input 0.5          # input|otg: dB (- = silencio); screen 0-20; cab-left|cab-right on/thru
ge150ctl rhythm                        # caja de ritmos: estado, modo, estilo, BPM, volumen
ge150ctl rhythm-set bpm 120            # state on/off, mode rhythm/metronome, style N, bpm, vol

ge150ctl save [--slot N] [--name X]    # persistentes: piden confirmación (o -y)
ge150ctl rename 12 "Mi Preset"
ge150ctl copy 12 150
ge150ctl export 12 mi.mo | export all carpeta/
ge150ctl import mi.mo 150
ge150ctl ir-export carpeta/            # IR de usuario → WAV
ge150ctl ir-upload 8 cab.wav           # WAV → ranura IR 8 (CAB 34)
ge150ctl ir-delete 8
ge150ctl nr-upload 1 captura.amp       # .amp → ranura NR 1 (AMP 56)
ge150ctl backup GE150.mbf              # backup completo (solo lectura)
ge150ctl restore GE150.mbf             # SOBRESCRIBE toda la pedalera
ge150ctl factory-reset --backup antes.mbf  # BORRA TODO: valores de fábrica (pide «BORRAR TODO»)

ge150ctl ai "tono de Slash en Sweet Child O' Mine"   # asistente IA: aplica el tono en vivo (sin guardar)
ge150ctl ai --dry-run --provider codex "clean con chorus de los 80"

ge150ctl --sim <comando>               # cualquier comando contra el simulador
ge150ctl --raw <comando>               # muestra cada reporte USB de 64 bytes
```

## Asistente de tono con IA

`ge150ctl ai` le pide el tono a **Claude Code** (`claude`) o a **Codex** (`codex`), las herramientas de línea de
comandos de las suscripciones de Claude y ChatGPT: no hace falta clave de API, usa la cuota de tu plan. Recibe el
catálogo exacto de la GE150 (modelos, en qué equipo se basa cada uno y rangos) y tu preset actual, propone el patch
completo y la app lo aplica en vivo; guárdalo con `ge150ctl save` si te gusta. Las herramientas se ejecutan sin
acceso a archivos ni otras herramientas.

### La pedalera como servidor MCP

`ge150-mcp` expone la pedalera a cualquier cliente MCP (Claude Code, Codex…) con herramientas para leer el catálogo,
el preset actual, los presets guardados, las IR de usuario y los ajustes, y para cambiar el sonido en vivo
(`set_module`, `apply_patch`, `undo`, `select_preset`). Con TONE3000 también busca y descarga IR de cabinas
(`tone3000_search`, `tone3000_get`, `load_tone3000_ir`).

```bash
.venv/bin/pip install -e '.[ai]'       # SDK de MCP
ge150ctl mcp-install                   # registra el servidor en Claude Code y/o Codex
claude "ponme el tono de Gilmour en el solo de Comfortably Numb"
codex "un clean funk tipo Nile Rodgers"
```

Con el editor gráfico abierto, `ge150-mcp` se conecta a él (solo un programa puede usar la pedalera): ves cada
cambio de la IA al instante y nada se escribe en la memoria de la pedalera (`save_preset`, `load_tone3000_ir`) sin
que lo confirmes en una ventana del editor. Sin el editor abierto, `ge150-mcp` abre la pedalera directamente y
esas dos herramientas se rechazan. La IA nunca restaura, resetea ni actualiza el firmware.

## Cabinas de TONE3000

Descarga IR de cabinas de [TONE3000](https://www.tone3000.com) y cárgalas en las ranuras de usuario (CAB 27-36).
Una vez: copia la clave publicable (*Publishable Key*, `t3k_pub_…`) de los ajustes de API de tu cuenta de TONE3000.
No hace falta registrar redirects: TONE3000 siempre acepta `http://127.0.0.1`. La *Secret Key* no se usa; no la
compartas.

```bash
ge150ctl t3k-key t3k_pub_…               # guarda tu clave publicable
ge150ctl t3k-login                    # inicia sesión en el navegador
ge150ctl t3k-load 4                   # elige una IR en el catálogo de TONE3000 y la carga en la ranura 4
ge150ctl t3k-load 4 --tone 12345      # o directo por id de tono
ge150ctl t3k-status                   # sesión e IR descargadas (autor y licencia)
```

Se muestran autor y licencia de cada IR; respétala (por ejemplo, `cc-by-nc` = solo uso no comercial). Las IR
descargadas quedan en `~/.cache/ge150/tone3000/` y no se versionan.

## Desarrollo

```bash
.venv/bin/python -m pytest              # incluye tests de la GUI en modo offscreen
.venv/bin/ruff check src tests tools
.venv/bin/mypy
python3 -I tools/build_catalog.py       # regenera src/ge150/data/effects.json desde reference/
```

Regla del proyecto: ningún archivo de código supera 1000 líneas (ver `plan.md` §0).
El material del fabricante (`reference/`) no se versiona.

## Licencia

[MIT](LICENSE). El software oficial de Mooer y su material (`reference/`) no forman parte del proyecto ni se
distribuyen aquí.
