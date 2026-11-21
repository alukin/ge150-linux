# ge150-linux

Editor y CLI para Linux de la pedalera **Mooer GE150**, obtenidos por ingeniería inversa del
software oficial *Mooer Studio for GE150* (Windows). El protocolo, la arquitectura y la hoja de ruta
están en [`plan.md`](plan.md).

> Estado: fase 1 (núcleo del protocolo, simulador y CLI de solo lectura). Todavía no hay interfaz gráfica.

## Instalación (desarrollo)

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'          # opcional: '.[usb]' para el backend pyusb
```

Acceso a la pedalera sin root (una sola vez):

```bash
sudo cp udev/70-mooer-ge150.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
# desconectar y volver a conectar la pedalera
```

## Uso

```bash
ge150ctl devices                  # buscar la pedalera (/dev/hidrawN)
ge150ctl probe                    # identificar: nombre y versión del firmware
ge150ctl presets                  # los 200 nombres
ge150ctl current                  # preset actual decodificado
ge150ctl snapshot --out ge150.json   # volcar todo lo legible (hacerlo antes de cualquier escritura)
ge150ctl sniff --seconds 30       # ver lo que envía la pedalera al tocarla
ge150ctl --raw <comando>          # mostrar cada reporte USB de 64 bytes
ge150ctl --sim <comando>          # usar el simulador integrado (sin hardware)
```

Todos los comandos actuales son **de solo lectura**.

## Desarrollo

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
.venv/bin/mypy
python3 -I tools/build_catalog.py        # regenera src/ge150/data/effects.json desde reference/
```

Regla del proyecto: ningún archivo de código supera 1000 líneas (ver `plan.md` §0).
