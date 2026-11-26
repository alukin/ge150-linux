# Publicar una versión

Todo lo necesario para lanzar `vX.Y.Z` de **ge150-linux**: qué revisar, qué archivos actualizar, cómo crear el tag y
la release de GitHub, cómo comprobar que llegó a PyPI y qué hacer si algo falla. Los comandos usan `X.Y.Z` como
ejemplo (y `A.B.C` para la versión anterior); reemplázalos por las versiones reales.

## Resumen rápido

1. Pruebas en verde y verificación con la pedalera.
2. Actualizar la versión en **3 archivos**, el `CHANGELOG.md` y lo que corresponda según lo que cambió.
3. Commit `chore(release): vX.Y.Z`, push, tag `vX.Y.Z` y push del tag.
4. Release en GitHub con las notas del changelog → **PyPI se publica solo**.
5. Comprobar PyPI.
6. Reabrir el changelog para lo que viene.

## Lista de verificación

Copia esta lista en un borrador y márcala a medida que avanzas:

```markdown
- [ ] main al día y sin cambios pendientes
- [ ] pytest, ruff y mypy en verde
- [ ] hw-check con la pedalera (si cambió algo que toca la pedalera)
- [ ] probada la app un rato con la pedalera real
- [ ] versión X.Y.Z en pyproject.toml, src/ge150/__init__.py y packaging/PKGBUILD
- [ ] CHANGELOG.md cerrado con fecha y enlace de comparación
- [ ] README / capturas / plan.md / docs actualizados si hace falta (ver tabla)
- [ ] commit chore(release): vX.Y.Z + push
- [ ] tag vX.Y.Z + push del tag
- [ ] release de GitHub con wheel y tar.gz
- [ ] workflow «Publish to PyPI» en verde y X.Y.Z visible en pypi.org/p/ge150-linux
- [ ] CHANGELOG.md reabierto con [Sin publicar]
```

## 1. Antes de empezar

- Estar en `main`, sin cambios pendientes y al día:

  ```bash
  git switch main && git pull && git status
  ```

- Pruebas y revisiones:

  ```bash
  .venv/bin/python -m pytest
  .venv/bin/ruff check src tests tools
  .venv/bin/mypy
  ```

- Si cambió algo que habla con la pedalera (protocolo, edición de presets, escucha, backups, restore), con la
  pedalera conectada y **el editor cerrado** (solo un programa puede usarla) correr la verificación automática con
  tres presets que se puedan escribir (los deja byte a byte como estaban):

  ```bash
  ge150ctl hw-check --slots 198,199,200
  ```

  Si se niega porque el preset cargado tiene cambios sin guardar, guárdalos o descártalos en la pedalera y repite.
  El informe queda en `~/.local/share/ge150/hw-check/`. Revisa también la parte manual de
  [`docs/verificacion-hardware.md`](docs/verificacion-hardware.md) para lo que el script no cubre.
- Probar la app de verdad un rato (`ge150`), no solo con `--sim`.

## 2. Elegir el número de versión

[SemVer](https://semver.org/lang/es/) mientras sea `0.x`:

| Cambió… | Sube | Ejemplo |
|---|---|---|
| Solo correcciones | parche | `0.4.0` → `0.4.1` |
| Funciones nuevas, o algo que cambia cómo se usa o se ve | menor | `0.4.1` → `0.5.0` |
| Versión estable (`1.0.0`) | mayor | cuando el proyecto se considere terminado |

Un número publicado no se reutiliza nunca (ni en GitHub ni en PyPI): si algo salió mal, se publica el siguiente.

## 3. Qué actualizar

### Siempre

La versión vive en **tres lugares** y deben coincidir (`tests/test_version.py` falla si no):

| Archivo | Qué cambiar |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/ge150/__init__.py` | `__version__ = "X.Y.Z"` (la muestra *Ayuda → Acerca de*) |
| `packaging/PKGBUILD` | `pkgver=X.Y.Z`, el `printf "X.Y.Z.r%s.%s"` de `pkgver()` y `pkgrel=1` |

```bash
sed -i 's/^version = "A.B.C"$/version = "X.Y.Z"/' pyproject.toml
sed -i 's/^__version__ = "A.B.C"$/__version__ = "X.Y.Z"/' src/ge150/__init__.py
sed -i 's/^pkgver=A.B.C$/pkgver=X.Y.Z/; s/printf "A.B.C.r%s.%s"/printf "X.Y.Z.r%s.%s"/; s/^pkgrel=.*/pkgrel=1/' \
  packaging/PKGBUILD
.venv/bin/python -m pytest tests/test_version.py     # las tres coinciden
```

Y el **`CHANGELOG.md`**:

1. Cambiar `## [Sin publicar]` por `## [X.Y.Z] - AAAA-MM-DD` (la fecha del lanzamiento).
2. Revisar que estén todos los cambios que le importan al usuario (`git log vA.B.C..HEAD --oneline` ayuda). Se
   escribe para quien usa la app, en español, agrupado en *Añadido*, *Cambiado*, *Quitado* y *Corregido*, en ese
   orden; no es la lista de commits.
3. Al final, cambiar el enlace `[Sin publicar]: …/compare/vA.B.C...HEAD` por
   `[X.Y.Z]: https://github.com/wh01s17/ge150-linux/compare/vA.B.C...vX.Y.Z`.

### Según lo que cambió

| Si cambió… | Actualizar |
|---|---|
| Algo visible de la interfaz | `README.md` y sus capturas en `docs/img/` (sin datos privados: número de serie de la guitarra, IPs) |
| Instalación, comandos o requisitos | `README.md` (*Instalación*, *Actualizar*, *Desinstalar*, *Línea de comandos*) |
| Dependencias de Python | `pyproject.toml` (`dependencies` o el extra que corresponda) **y** `depends`/`optdepends` del `PKGBUILD` |
| Archivos que se instalan (regla udev, `.desktop`, ícono) | `package()` del `PKGBUILD` y la sección de instalación del README |
| Datos incluidos en el paquete (`src/ge150/data/`) | `[tool.setuptools.package-data]` del `pyproject.toml` |
| Dibujos de los equipos (`tools/build_gear.py`) | regenerar `src/ge150/data/gear.json` con `.venv/bin/python tools/build_gear.py` |
| Protocolo, hallazgos en la pedalera | `plan.md` (tablas, etiquetas `[V]`/`[I]`/`[?]`, checklist de fases) |
| Funciones que tocan la pedalera | `docs/verificacion-hardware.md` (pasos manuales nuevos) |
| Este proceso | este archivo |

## 4. Commit y tag

Commit con `/commit:commit` (mensaje `chore(release): vX.Y.Z`), con push. Después el tag anotado sobre ese commit:

```bash
git tag -a vX.Y.Z -m "ge150-linux X.Y.Z"
git push origin vX.Y.Z
```

Si el tag quedó mal **antes** de publicar la release: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z` y
repetir. **Nunca** mover un tag que ya se publicó: se saca una versión nueva.

## 5. Release en GitHub

Construir los archivos para adjuntar (quedan en `dist/`, que está en `.gitignore`):

```bash
.venv/bin/python -m pip install build
rm -rf dist/vX.Y.Z && .venv/bin/python -m build --outdir dist/vX.Y.Z
```

Crear la release con las notas de esa versión del changelog (con [`gh`](https://cli.github.com/), sesión iniciada
con `gh auth login`):

```bash
awk -v version='X.Y.Z' 'index($0, "## [" version "] - ") == 1 {show=1; next}
    show && (/^## / || /^\[[^]]+\]:/) {exit}
    show {gsub(/\]\(docs\//, "](https://github.com/wh01s17/ge150-linux/blob/v" version "/docs/"); print}' \
    CHANGELOG.md > /tmp/notas-X.Y.Z.md
gh release create vX.Y.Z --verify-tag \
  dist/vX.Y.Z/ge150_linux-X.Y.Z-py3-none-any.whl dist/vX.Y.Z/ge150_linux-X.Y.Z.tar.gz \
  --title "ge150-linux X.Y.Z" --notes-file /tmp/notas-X.Y.Z.md
```

Revisar la página de la release: notas bien formateadas y los dos archivos adjuntos.

## 6. PyPI (automático)

Publicar la release dispara el workflow [`publish.yml`](.github/workflows/publish.yml), que:

1. pasa los enlaces del README a URLs absolutas (PyPI no resuelve rutas del repositorio; el README del repo no
   cambia),
2. construye el wheel y el `.tar.gz` y los revisa con `twine check`,
3. los sube a PyPI como [`ge150-linux`](https://pypi.org/p/ge150-linux) con *trusted publishing* (sin tokens),
   desde el entorno `pypi` de GitHub.

Comprobar:

```bash
gh run list --workflow publish.yml --limit 1          # debe terminar en «completed success»
curl -s https://pypi.org/pypi/ge150-linux/X.Y.Z/json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['info']['version'], [u['filename'] for u in d['urls']])"
```

PyPI puede tardar un minuto en mostrar la versión nueva en `/pypi/ge150-linux/json` (caché); la URL con la versión
(`/pypi/ge150-linux/X.Y.Z/json`) responde antes.

### Si falla

| Síntoma | Causa y solución |
|---|---|
| `invalid-publisher: valid token, but no corresponding publisher` | El publicador de PyPI no coincide con el workflow. Revisar en PyPI *Your projects → ge150-linux → Publishing*: propietario `wh01s17`, repositorio `ge150-linux`, workflow `publish.yml`, entorno `pypi`. Después `gh run rerun <id> --failed`. |
| `File already exists` | Esa versión ya está en PyPI (no se puede reemplazar). Publicar una versión nueva. |
| Falla el build o `twine check` | Corregir en `main`, y relanzar a mano: *Actions → Publish to PyPI → Run workflow* (o `gh workflow run publish.yml`). Ojo: sube el `main` actual, así que el arreglo debe ir en un commit que forme parte de esa versión o en una versión nueva. |
| El job espera aprobación | El entorno `pypi` de GitHub tiene reglas de protección: aprobar en la página del run. |

### Configuración (una sola vez, ya hecha)

- PyPI: *Account → Publishing → Add a new pending publisher → GitHub* con proyecto `ge150-linux`, propietario
  `wh01s17`, repositorio `ge150-linux`, workflow `publish.yml` y entorno `pypi`. Tras la primera publicación pasa a
  ser el publicador del proyecto.
- GitHub: entorno `pypi` (*Settings → Environments*), creado con
  `gh api -X PUT repos/wh01s17/ge150-linux/environments/pypi`.

## 7. Paquete de AUR (en pausa)

El paquete sería `ge150-linux-git`: compila desde el último commit de `main`, así que **no hace falta publicarlo en
cada versión**; solo la primera vez o cuando cambia el `PKGBUILD` (dependencias, archivos instalados). Todavía no
está publicado: necesita una cuenta de AUR con tu clave SSH.

Probarlo localmente:

```bash
cd packaging && makepkg -sfi && namcap PKGBUILD *.pkg.tar.zst
```

Publicar:

```bash
git clone ssh://aur@aur.archlinux.org/ge150-linux-git.git /tmp/aur-ge150
cp packaging/PKGBUILD /tmp/aur-ge150/
cd /tmp/aur-ge150 && makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO && git commit -m "Update to X.Y.Z" && git push
```

Comprobar: `yay -S ge150-linux-git` (o `paru`) en otra máquina o en un usuario limpio, conectar la pedalera y abrir
`ge150`.

## 8. Después de publicar

- Agregar arriba del `CHANGELOG.md` la sección para lo que viene:

  ```markdown
  ## [Sin publicar]
  ```

  con su enlace al final: `[Sin publicar]: https://github.com/wh01s17/ge150-linux/compare/vX.Y.Z...HEAD`.
  Cada cambio que le importe al usuario se anota ahí a medida que se hace.
- Commit `docs: start the changelog for the next version`, con push.
- Opcional: probar la instalación limpia desde PyPI:

  ```bash
  python3 -m venv /tmp/ge150-test && /tmp/ge150-test/bin/pip install ge150-linux
  /tmp/ge150-test/bin/ge150ctl --sim probe        # MOOER_GE150 / V1.3.8
  ```

## Historial

| Versión | Fecha | Notas |
|---|---|---|
| 0.1.0 | 2026-11-22 | Primera versión. |
| 0.2.0 | 2026-11-23 | Adjuntos retirados (incluían fotos con derechos reservados). |
| 0.2.1 | 2026-11-23 | Solo fotos con licencia libre. |
| 0.3.0 | 2026-11-23 | Dibujos de todos los equipos; primera versión en PyPI. |
| 0.4.0 | 2026-11-23 | Interfaz escalada según la pantalla. |
| 0.5.0 | 2026-11-26 | Ordenar presets arrastrándolos y página del pedal de expresión. |
| 0.5.1 | 2026-11-26 | El parámetro que soltaba el pedal vuelve a su valor guardado. |
