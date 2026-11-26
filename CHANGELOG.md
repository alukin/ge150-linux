# Changelog

Todos los cambios importantes de **ge150-linux**. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y las versiones usan [SemVer](https://semver.org/lang/es/): mientras sea `0.x`, una versión menor puede traer cambios
grandes. Cómo publicar una versión: [`PUBLISH.md`](PUBLISH.md).

## [Sin publicar]

### Corregido

- Pedal de expresión: al pasar a volumen (o a nada) un preset que ya venía con el pedal moviendo un parámetro,
  ese parámetro se quedaba donde lo dejó el pedal (por ejemplo, el MIX del chorus en 100). Ahora vuelve al valor
  guardado en el preset.

## [0.5.0] - 2026-11-26

### Añadido

- Ordenar presets arrastrándolos en la lista de la izquierda: el preset toma el lugar donde lo sueltas y los de
  entre medio se corren un puesto. Pide confirmación, hace antes un backup automático completo y el preset cargado
  sigue sonando en su nueva posición. Mientras se escribe, un aviso sobre la lista muestra el avance y no se
  puede cargar otro preset.
- El pedal de expresión aparece en la cadena de efectos, aparte, con lo que controla («DS · GAIN», «VOLUMEN»…);
  el efecto que mueve lleva la etiqueta EXP. Al elegirlo, su página (como la de un efecto) deja escoger qué
  controla: el volumen (con su mínimo y máximo), un parámetro de un efecto de la cadena o de un modelo nuevo, o
  nada, y tiene un atajo para wah. Reemplaza al diálogo de valores crudos de *Herramientas → Pedal de expresión*.
  Muestra el pedal de costado inclinado según su posición en vivo (cuando mueve un parámetro: es lo único por lo que
  la GE150 la informa), avisa si el cambio necesita guardarse, devuelve el parámetro a su valor al dejar de
  moverlo y sigue el interruptor de punta.

### Cambiado

- La cadena de efectos ya no tiene texto de ayuda en la cabecera, e IN y OUT se ven más grandes.
- Al iniciar, los puntos de «Conectando…» y «Leyendo la pedalera…» se mueven mientras se lee la pedalera.

### Corregido

- Asistente: un preset que se escuchaba antes de aplicarlo no se escribía si su copia tenía otros ajustes del pedal
  de expresión. La vista previa no cargaba esos ajustes, así que el preset parecía tener cambios sin guardar y se
  saltaba al aplicar. Ahora la vista previa, la comparación A/B y deshacer una propuesta también restauran el EXP.

## [0.4.0] - 2026-11-23

### Añadido

- La interfaz se adapta a la pantalla: en 4K o 1440p sin escalado del sistema se agranda sola (como 1080p, pero
  nítida), y *Ver → Tamaño de la interfaz* permite elegir 100 %–250 %. También cabe en pantallas de 1366 × 768.

### Cambiado

- Las etiquetas de los pedales (DC IN, nombres de perillas) mantienen su tamaño real en la vista grande.

## [0.3.0] - 2026-11-23

### Añadido

- Disponible en PyPI como [`ge150-linux`](https://pypi.org/p/ge150-linux) (`pip install 'ge150-linux[gui,ai]'`); cada
  release de GitHub se publica sola con *trusted publishing*.

### Cambiado

- Ya no se incluyen fotos: los 131 equipos se dibujan a partir del original, con un estilo uniforme. Los
  amplificadores y gabinetes llevan el logo de su marca con su estilo (cursiva de Marshall y Fender, óvalo de EVH,
  placa de Mesa…), su rejilla (tela, cesta, metal perforado, barras, rombos de VOX, franjas de EVH), manija,
  esquineros y un panel con interruptores y piloto; los pedales MOOER micro tienen su diseño real (perilla grande,
  DC IN, jacks y logo MOOER), los BOSS su placa, y los demás pedales su nombre impreso, su franja de color o su
  forma (Cry Baby, ShredMaster, Direct Drive). Tu propia foto en `~/.local/share/ge150/photos/` sigue
  reemplazando al dibujo.

## [0.2.1] - 2026-11-23

### Cambiado

- Solo se incluyen fotos de equipos con licencia libre (Wikimedia Commons): las 31 fotos de producto de fabricantes
  y tiendas ya no se distribuyen, y esos equipos se dibujan (o usan tu foto en `~/.local/share/ge150/photos/`). Las
  fotos pasaron a WebP: de 3,3 MB a 0,9 MB. En Arch, el paquete ahora depende de `qt6-imageformats` (lee WebP).

## [0.2.0] - 2026-11-23

### Añadido

- Botón **Descartar** junto a «Guardar»: aparece cuando el preset tiene cambios sin guardar y lo devuelve a su
  versión guardada (antes solo estaba en el menú Preset → Descartar cambios).
- El asistente ahora puede **renombrar y reordenar presets** dentro de una propuesta: `propose_preset_edits`
  acepta `name` y `copy_from` (copiar el contenido de otro preset; dos cruzados los intercambian). Los cambios de
  nombre y de contenido se ven en Cambios pendientes antes de aplicar.
- **Permisos del asistente** (botón de engranaje en el chat): un interruptor por tipo de operación (sonido en
  vivo, cambios de efectos, renombrar, mover, guardar, buscar en TONE3000, cargar IR). Se guardan en
  `~/.config/ge150/ai_permissions.json` y también los respeta `ge150-mcp`. Leer siempre está permitido.
- Al reabrir una conversación del Asistente vuelven los **presets marcados** y los **cambios pendientes**; los que se
  aplicaron después desaparecen y los de presets que cambiaron quedan bloqueados.
- Mientras la IA trabaja (en el panel lateral y en el Asistente): un indicador animado con el paso en curso y el
  tiempo, y los pasos repetidos se agrupan («revisa el catálogo ×9»).
- En la galería de modelos de CAB, un separador distingue los modelos de la pedalera de las ranuras de usuario
  (IR de TONE3000 u otras). Al pasar el mouse sobre una IR de usuario, el tooltip lista los presets que la usan.

### Cambiado

- Las conversaciones guardadas antes de esta versión también se ven con Markdown y con los pasos agrupados al
  abrirlas (las sub-listas quedan al mismo nivel: el formato anterior no guardaba la sangría).
- Las respuestas de la IA se muestran con Markdown completo (tablas, listas anidadas, títulos, código) usando
  `markdown-it-py`, nueva dependencia de la interfaz gráfica (`python-markdown-it-py` en Arch).

### Quitado

- Las ranuras de captura NR del AMP (56-65) ya no aparecen en la galería ni en lo que ve la IA, como en el editor
  oficial: la GE150 las procesa, pero no hay archivos `.amp` para ella. `ge150ctl nr-upload` sigue disponible.

### Corregido

- El volumen de la caja de ritmos se puede subir hasta 20, como en la pedalera (el editor lo limitaba a 10), y el
  brillo de la pantalla empieza en 1 (comprobado en la pantalla de la pedalera).
- `ge150ctl current` muestra el nombre de la IR de usuario cargada en el CAB (antes decía «34:EMPTY»).
- El editor a veces no arrancaba al primer intento (`timeout waiting for 0x01 DEVICE_INFO`). Ahora el primer
  contacto hace lo mismo que el lanzador oficial: envía los 8 bytes a cero antes de identificar y reintenta la
  identificación hasta 3 veces.

## [0.1.0] - 2026-11-22

Primera versión de ge150-linux. Las pruebas con una **MOOER GE150 real, firmware V1.3.8**, están documentadas en
[`docs/verificacion-hardware.md`](docs/verificacion-hardware.md).

### Pedalera

- Comunicación USB propia (hidraw o pyusb), obtenida por ingeniería inversa del editor oficial de Windows, con regla
  udev para usarla sin root.
- Lectura de los 200 presets, el preset cargado, los ajustes de sistema, la caja de ritmos, el pedal de expresión y
  los nombres de las IR de usuario.
- Edición en vivo (encender o apagar módulos, cambiar modelos, mover parámetros) y seguimiento de lo que se cambia en
  la propia pedalera (perillas y footswitch).
- Guardar, renombrar, copiar y pegar presets; exportar e importar presets `.mo`.
- IR de usuario (CAB 27-36): cargar WAV (44,1 a 96 kHz), borrarlas y exportarlas a WAV.
- Backup completo y restauración en `.mbf`, y vuelta a valores de fábrica con doble confirmación y backup previo.
- Simulador de la pedalera (`--sim`) para usar y probar todo sin hardware.

### Interfaz gráfica (`ge150`)

- Lista de presets con búsqueda; un clic carga el preset y avisa si hay cambios sin guardar.
- Página de cada módulo con la foto o el dibujo del equipo original en que se basa, galería de modelos y perillas.
- Colocación del micrófono frente al parlante en las cabinas (CENTER y DISTANCE).
- **Cadena de efectos** con entrada y salida, LED de encendido por módulo, efectos apagados atenuados y una
  animación al pasar el mouse; el delay tiene un LED «TAP» que parpadea a su tiempo.
- Ajustes de sistema, caja de ritmos, pedal de expresión e IR de usuario en sus propias ventanas.
- **Mis guitarras**: registra tus guitarras (marca, modelo y número de serie) y la IA completa la ficha de fábrica
  con su foto, indicando qué tan seguro es cada dato.
- Ventana **Acerca de** con el proyecto, el autor, la licencia, la información de tu sistema y los créditos.

### Asistente de tono con IA

- Usa **Claude Code** o **Codex** con tu suscripción de Claude o ChatGPT, sin claves de API; eliges modelo y
  esfuerzo de razonamiento.
- Panel lateral (**✦ IA**, Ctrl+K): pides un sonido y la IA lo ajusta en vivo; Deshacer, Detener y comparar el
  sonido original con el sugerido. Considera el preset actual y la guitarra que estás usando.
- Pestaña **Asistente**: cambiar **varios presets a la vez**, con la IA o con la edición manual (módulo, encendido,
  modelo y un parámetro fijado o sumado). Los cambios quedan en una tabla antes → después hasta que aprietas
  **Aplicar**; la pedalera carga el preset propuesto para que lo escuches (**Antes / Después**) sin escribir nada.
- **Backup automático** completo de la pedalera antes de cada edición masiva y de su Deshacer (se guardan los
  últimos 20); si el backup falla, no se escribe nada.
- **Historial de conversaciones** en ambos chats: buscar, abrir (la IA retoma la conversación y la pedalera carga el
  preset de esa conversación), renombrar y eliminar.
- La IA nunca guarda presets ni restaura, resetea o actualiza la pedalera por su cuenta; lo que escribe en la memoria
  te lo pregunta antes.
- **Servidor MCP** (`ge150-mcp`, `ge150ctl mcp-install`) para usar la pedalera desde Claude Code o Codex en la
  terminal; con el editor abierto, se conecta a él.

### TONE3000

- Pestaña con el catálogo de IR de cabinas de [TONE3000](https://www.tone3000.com) dentro de la app, con autor,
  licencia e imagen de cada IR y **Agregar a la pedalera**.
- **Conectar cuenta** sin tener que elegir una IR.
- Desde el chat (parlante en el panel de IA): la IA busca un gabinete real para cada sonido, lo guarda en una ranura
  libre (o te deja elegir cuál reemplazar, mostrando cuántos presets la usan) y lo pone en el CAB.

### Línea de comandos (`ge150ctl`)

- Lectura, edición en vivo, presets, IR, backup y restauración, ajustes de sistema y ritmos, TONE3000 e IA.
- `ge150ctl hw-check`: verificación automática en la pedalera real (backup, edición masiva, preset que suena,
  escuchar antes de aplicar), que deja todo como estaba.

### Conocido

- El LED «TAP» sigue el tiempo del delay guardado en el preset: en la GE150 no se comprobó ningún tap tempo.
- La subida de capturas NR (`.amp`, AMP 56-65) existe solo en la línea de comandos y no se probó que suenen.
- La interfaz está solo en español.

[Sin publicar]: https://github.com/wh01s17/ge150-linux/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/wh01s17/ge150-linux/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/wh01s17/ge150-linux/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/wh01s17/ge150-linux/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/wh01s17/ge150-linux/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/wh01s17/ge150-linux/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/wh01s17/ge150-linux/commits/v0.1.0
