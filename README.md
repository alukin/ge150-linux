# ge150-linux

Editor libre para Linux de la pedalera **Mooer GE150**: interfaz gráfica (`ge150`) y línea de comandos
(`ge150ctl`). El protocolo USB se obtuvo por ingeniería inversa del software oficial *Mooer Studio for GE150*
(Windows). El protocolo, la arquitectura y la hoja de ruta están en [`plan.md`](plan.md).

> **Estado:** lectura completa y edición en vivo verificadas con una pedalera real. Guardar, renombrar y
> cargar IR solo se han probado con el simulador integrado. Haz un `ge150ctl snapshot` antes de escribir.

## Qué puede hacer

- Leer los 200 presets, el preset actual decodificado (modelos y parámetros), los IR de usuario y el
  estado del pedal de expresión.
- Editar en vivo: encender/apagar módulos, cambiar el modelo y mover parámetros.
- Guardar, renombrar y copiar presets.
- Importar y exportar presets `.mo`, compatibles con la app oficial.
- Cargar IR desde WAV a las ranuras de usuario (CAB 27-36), borrarlas y exportarlas a WAV.
- Seguir los cambios hechos en la propia pedalera (footswitch, knobs).

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

ge150ctl save [--slot N] [--name X]    # persistentes: piden confirmación (o -y)
ge150ctl rename 12 "Mi Preset"
ge150ctl copy 12 150
ge150ctl export 12 mi.mo | export all carpeta/
ge150ctl import mi.mo 150
ge150ctl ir-export carpeta/            # IR de usuario → WAV
ge150ctl ir-upload 8 cab.wav           # WAV → ranura IR 8 (CAB 34)
ge150ctl ir-delete 8

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
