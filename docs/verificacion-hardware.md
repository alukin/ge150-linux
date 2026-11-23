# Verificación con la pedalera real

Funciones que hasta ahora solo se probaron contra el simulador (`FakeGE150`). El simulador hace lo que creemos
que hace la pedalera: esta lista confirma que es así. Marca cada casilla y anota lo que veas en **Notas**; si algo
falla, anota qué hiciste, qué esperabas y qué pasó (y la pantalla de la pedalera si muestra algo distinto al editor).

Fecha: ____________ · Firmware: ____________ · Versión del editor (`git log -1 --oneline`): ____________

## Verificación automática (`ge150ctl hw-check`)

Con el editor **cerrado** (la pedalera admite un solo programa) y tres presets que se puedan escribir:

```
ge150ctl hw-check --slots 198,199,200          # pasos 1-4: escribe, le pregunta a la pedalera y compara
ge150ctl hw-check --slots 198,199,200 --only-tap --tap 45   # paso 9: pisa TAP mientras corre
```

Hace un backup completo antes, deja los tres presets y el preset cargado byte a byte como estaban y lo comprueba.
El informe queda en `~/.local/share/ge150/hw-check/`.

**Resultado 2026-11-22, MOOER_GE150 V1.3.8, presets 198-200: TODO OK.**

| Paso | Comprobado en la pedalera real |
|---|---|
| 1 | Backup automático completo (200 presets, 10 IR) en **3,4 s**, coincide con la pedalera. |
| 2 | Escribir dos presets que no están cargados: guardados con el valor nuevo, los otros 198 intactos, la pedalera no cambia de preset; Deshacer los devuelve. |
| 3 | **La pedalera recarga sola el preset que está sonando cuando se escribe**; Aplicar deja sonando y guardada la versión nueva; Deshacer vuelve a la original. |
| 4 | Escuchar: cambia al preset propuesto con la propuesta; «Antes» y «Después» cargan lo que corresponde; Descartar vuelve a lo guardado y la escucha nunca escribe en la memoria. |
| 6 | Sesión de TONE3000 iniciada y búsqueda real de IR desde las herramientas de la IA (10 resultados). |
| 9 | **Pendiente:** en la primera prueba no llegó ningún aviso de TAP ni cambió el TIME (falta confirmar si se pisó TAP durante la prueba). |

Queda **manual**: escuchar y mirar la pantalla en los pasos 3 y 4 (los datos ya están comprobados), la IA (pasos
5 y 7), «Conectar cuenta» en el navegador (6), el historial (8) y el TAP (9).

## 0. Preparación (obligatoria)

- [ ] **Backup manual completo**: *Archivo → Backup completo (.mbf)…*, guardarlo fuera de la carpeta del editor.
      Es la red de seguridad de toda la sesión (el restore completo ya está verificado en hardware).
- [ ] Elegir 3 presets de prueba que no importe tocar (o copiar ahí unos Av83). En esta lista: **A**, **B** y **C**.
      A = ______ · B = ______ · C = ______
- [ ] Guitarra y salida conectadas para **escuchar** cada paso, no solo mirar la pantalla.
- [ ] Editor abierto con la pedalera (no `--sim`), barra de estado con `hidraw`.

## 1. Backup automático

1. Pestaña **Asistente** → Edición manual → marcar **A** → apagar o encender un módulo → *Agregar a cambios* →
   *Aplicar*.

- [ ] La línea de estado dice «Backup previo: ~/.local/share/ge150/backups/auto-…-aplicar.mbf».
- [ ] Tiempo desde *Aplicar* hasta «Listo»: ______ s (si pasa de ~10 s, anotarlo: habría que mostrar progreso).
- [ ] *Archivo → Abrir carpeta de backups automáticos* abre esa carpeta y el archivo está.
- [ ] *Archivo → Restaurar backup* con ese archivo **carga sin error** (cancelar en la confirmación: no restaurar).

Notas:

## 2. Edición masiva de presets que no están cargados

Con la pedalera en **C**:

1. Marcar **A** y **B** → Edición manual → un parámetro numérico (p. ej. REVERB → MIX) → *Fijar* en un valor
   distinto al actual → *Agregar a cambios*.
2. Revisar la tabla (antes → después) y *Aplicar a 2 presets*.

- [ ] Al agregar, la pedalera pasa sola a **A** para que escuches la propuesta (punto 4); después de aplicar
      queda en **A** con la versión nueva. **B** no se carga salvo que lo toques en la tabla.
- [ ] En la pedalera, ir a **A** y a **B** con el pie: la pantalla muestra el valor nuevo y suena distinto.
- [ ] *F5 (Volver a leer la pedalera)*: el editor muestra los valores nuevos (quedaron guardados de verdad).
- [ ] *Deshacer la última edición aplicada*: **A** y **B** vuelven al valor anterior (pantalla y sonido), y se creó
      otro backup `auto-…-deshacer.mbf`.
- [ ] Repetir con *Sumar* (p. ej. −5): cada preset baja desde **su** valor, no todos al mismo.

Notas:

## 3. Reescribir el preset que está sonando  ⚠ el punto más dudoso

Es el caso normal al aplicar: la escucha automática deja cargado el preset que se va a escribir. Con la pedalera en
**A**, sin cambios sin guardar (sin el aviso «MODIFICADO»):

1. Marcar solo **A** → un cambio que se oiga claro (p. ej. apagar el DS) → *Agregar* → *Aplicar*.

- [ ] La pedalera suena **al instante** con la versión nueva, sin tocar nada.
- [ ] La pantalla de la pedalera muestra la versión nueva.
- [ ] El editor **no** queda con «MODIFICADO».
- [ ] Cambiar a otro preset y volver a **A** con el pie: sigue la versión nueva.

Si la pedalera sigue sonando la versión vieja hasta cambiar de preset: anotarlo (el editor vuelve a seleccionar el
mismo preset para recargarlo; quizá la pedalera ignora seleccionar el preset en el que ya está).

Notas:

## 4. Escuchar una propuesta en su propio preset (Antes / Después)

Con la pedalera en **C**:

1. Marcar **B** → Edición manual → un cambio audible → *Agregar a cambios*.

- [ ] La pedalera **cambia sola a B** y suena la propuesta.
- [ ] Arriba de *Cambios pendientes* aparece «Escuchando en la pedalera: B» con **Antes / Después**.
- [ ] *Antes* suena como B guardado; *Después* suena con el cambio (alternar varias veces mientras tocas).
- [ ] La pantalla de la pedalera acompaña cada cambio.
- [ ] *Descartar*: B vuelve a su sonido guardado y el editor no queda con «MODIFICADO».
- [ ] Con dos presets pendientes, tocar el otro en la tabla: la pedalera cambia a ese.
- [ ] Mientras suena una propuesta, cambiar de preset **con el pie**: la barra de «Escuchando» desaparece.

Con cambios sin guardar tuyos en **C** (mover una perilla en la pestaña Efectos):

- [ ] Agregar un cambio para **B**: la pedalera **no** cambia sola; al tocar B en la tabla, el editor pregunta antes
      de descartar tus cambios. Responder *No*: sigue en C con tus cambios.

Notas:

## 5. IA en la pestaña Asistente

1. Marcar los Av83 → pedir «baja el reverb a 20 en los presets marcados».

- [ ] La IA lee los presets y la propuesta aparece en la tabla; **nada se escribe** hasta *Aplicar*.
- [ ] La pedalera pasa a escuchar el primer preset propuesto (punto 4).
- [ ] Pedir «otra opción un poco más fuerte»: la propuesta nueva **reemplaza** a la anterior y suena esa.
- [ ] Pedir un cambio para un preset que **no** está cargado: la IA no toca el preset que suena
      (debe proponer con la tabla, no cambiar el sonido actual).
- [ ] El chip «Presets marcados» lista los marcados; al desmarcarlo (tachado) la IA ya no los recibe.

Notas:

## 6. TONE3000: conectar la cuenta

1. Si hay sesión, *Cerrar sesión* en la pestaña TONE3000 (para probar desde cero).
2. *Conectar cuenta* → aceptar en la página de TONE3000.

- [ ] Vuelve sola al editor y dice «Cuenta conectada…» con tu usuario.
- [ ] Sin reiniciar el editor, pedirle a la IA «busca en TONE3000 una IR de Mesa 4x12»: encuentra resultados
      (antes decía que no había sesión).
- [ ] Si *Conectar cuenta* da error o queda cargando, anotar qué muestra y probar con *Select* sobre cualquier IR.

Notas:

## 7. Cabs de TONE3000 desde el chat

1. Encender el parlante del panel de IA (*Cabs de TONE3000*) → pedir un tono («tono de Slash en Sweet Child»).

- [ ] La IA propone una IR con autor y licencia, y pide confirmación antes de guardarla.
- [ ] Queda en una **ranura libre** y el CAB pasa a esa ranura: **suena** la IR nueva.
- [ ] Si la IA vuelve a elegir **la misma IR** (mismo tono y archivo): reusa esa ranura, no ocupa otra.
- [ ] Con las 10 ranuras ocupadas: aparece el selector con «usada en N presets»; elegir una y comprobar que la IR
      nueva suena en un preset que usaba esa ranura (es lo esperado: lo avisa el diálogo).
- [ ] *Deshacer* del chat quita la selección del CAB pero la IR sigue guardada en la ranura.

Notas:

## 8. Historial de conversaciones

1. Con la pedalera en **A**, conversar en el panel lateral («más ganancia»). Cambiar a **B**. *Nueva*.
2. Abrir el historial (reloj) → abrir la conversación anterior.

- [ ] Se ve tal cual y la pedalera **vuelve a A**.
- [ ] Seguir la conversación («un poco menos»): la IA recuerda lo anterior (probar con Claude y con Codex).
- [ ] Con cambios sin guardar en el preset cargado: pregunta *Cambiar y descartar / Abrir sin cambiar / Cancelar*,
      y cada opción hace lo que dice.
- [ ] Renombrar (lápiz, Enter) y eliminar (basurero, segundo clic) funcionan; cerrar y abrir el editor: el
      historial sigue ahí.
- [ ] El historial del panel lateral y el de la pestaña Asistente son distintos.

Notas:

## 9. Cadena de efectos: LED TAP

Con el delay encendido en el preset cargado:

- [ ] El punto rojo «TAP» del DLY parpadea al mismo ritmo que el LED de tap de la pedalera.
- [ ] Marcar un tempo nuevo **con el pie** (tap): el LED del editor sigue el tempo nuevo sin apretar F5
      (si no cambia hasta F5, la pedalera no avisa el TIME al marcar el tap: anotarlo).
- [ ] Apagar el delay: el LED deja de parpadear.

Notas:

## 10. Cierre

- [ ] Restaurar el **backup manual** del paso 0 si los presets de prueba quedaron distintos a como estaban.
- [ ] Copiar aquí los problemas encontrados (o abrir un issue por cada uno):

| # | Paso | Qué pasó | Gravedad |
|---|---|---|---|
|   |   |   |   |
