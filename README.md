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

ge150ctl --sim <comando>               # cualquier comando contra el simulador
ge150ctl --raw <comando>               # muestra cada reporte USB de 64 bytes
```

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
