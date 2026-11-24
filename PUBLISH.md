# Publicar una versión

Pasos para lanzar `vX.Y.Z` de **ge150-linux**: qué archivos editar, cómo probar, crear el tag, la release de GitHub
y el paquete de AUR. Los comandos usan `X.Y.Z` como ejemplo; reemplázalo por la versión real (por ejemplo `0.1.0`).

## Resumen rápido

1. Pruebas en verde y verificación con la pedalera.
2. Subir la versión en **3 archivos** y cerrar el `CHANGELOG.md`.
3. Commit, tag `vX.Y.Z` y push del tag.
4. Release en GitHub con las notas del changelog (publica en PyPI sola).
5. Actualizar el paquete de AUR.
6. Dejar el changelog listo para lo que viene.

## 1. Antes de empezar

- Estar en `main`, sin cambios pendientes y al día: `git switch main && git pull && git status`.
- Pruebas y revisiones:

  ```bash
  .venv/bin/python -m pytest
  .venv/bin/ruff check src tests tools
  .venv/bin/mypy
  ```

- Con la pedalera conectada y **el editor cerrado** (solo un programa puede usarla), la verificación automática con
  tres presets que se puedan escribir (los deja como estaban):

  ```bash
  ge150ctl hw-check --slots 198,199,200
  ```

  El informe queda en `~/.local/share/ge150/hw-check/`. Si algo cambió en la edición de presets, la escucha o los
  backups, revisa también la parte manual de [`docs/verificacion-hardware.md`](docs/verificacion-hardware.md).
- Probar la app de verdad un rato (`ge150`), no solo con `--sim`.

## 2. Elegir el número de versión

[SemVer](https://semver.org/lang/es/) mientras sea `0.x`:

| Cambió… | Sube | Ejemplo |
|---|---|---|
| Solo correcciones | parche | `0.1.0` → `0.1.1` |
| Funciones nuevas, o algo que cambia cómo se usa | menor | `0.1.1` → `0.2.0` |
| Versión estable (`1.0.0`) | mayor | cuando el proyecto se considere terminado |

## 3. Archivos a editar

La versión vive en **tres lugares** y deben coincidir (`tests/test_version.py` falla si no):

| Archivo | Qué cambiar |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/ge150/__init__.py` | `__version__ = "X.Y.Z"` (la muestra *Ayuda → Acerca de*) |
| `packaging/PKGBUILD` | `pkgver=X.Y.Z` y el `printf "X.Y.Z.r%s.%s"` de `pkgver()`; `pkgrel=1` |

Y el **`CHANGELOG.md`**:

1. Cambiar `## [X.Y.Z] - por publicar` por `## [X.Y.Z] - AAAA-MM-DD` (la fecha del lanzamiento).
2. Revisar que estén todos los cambios que le importan al usuario (`git log vANTERIOR..HEAD --oneline` ayuda); se
   escribe para quien usa la app, no la lista de commits.
3. Al final, el enlace de la versión: para la primera
   `[X.Y.Z]: https://github.com/wh01s17/ge150-linux/commits/vX.Y.Z`; para las siguientes
   `[X.Y.Z]: https://github.com/wh01s17/ge150-linux/compare/vANTERIOR...vX.Y.Z`.

Si cambió algo visible, actualizar también el `README.md` (y sus capturas en `docs/img/`).

## 4. Commit y tag

```bash
.venv/bin/python -m pytest tests/test_version.py     # las tres versiones coinciden
```

Commit con `/commit:commit` (mensaje `chore(release): vX.Y.Z`), con push. Después el tag anotado sobre ese commit:

```bash
git tag -a vX.Y.Z -m "ge150-linux X.Y.Z"
git push origin vX.Y.Z
```

Si el tag quedó mal antes de publicar la release: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z` y
repetir. **Nunca** mover un tag que ya se publicó: se saca una versión nueva.

## 5. Release en GitHub

Construir los archivos para adjuntar:

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m build --outdir dist/vX.Y.Z
```

Crear la release con las notas de esa versión del changelog (con [`gh`](https://cli.github.com/)):

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

Al publicar la release de GitHub, el workflow [`publish.yml`](.github/workflows/publish.yml) construye el paquete
y lo sube a PyPI como [`ge150-linux`](https://pypi.org/p/ge150-linux), con *trusted publishing* (sin tokens).
Se puede relanzar a mano desde *Actions → Publish to PyPI → Run workflow*. Revisar que el job termine en verde y
que la versión nueva aparezca en PyPI.

Configuración (una sola vez): en PyPI, *Publishing → Add a new pending publisher → GitHub* con proyecto
`ge150-linux`, propietario `wh01s17`, repositorio `ge150-linux`, workflow `publish.yml` y entorno `pypi`; en
GitHub, el entorno `pypi` (*Settings → Environments*).

## 7. Paquete de AUR

El paquete es `ge150-linux-git`: compila desde el último commit de `main`, así que **no hace falta publicarlo en
cada versión**; solo cuando cambia el `PKGBUILD` (dependencias, archivos instalados) o la primera vez.

Probarlo localmente:

```bash
cd packaging && makepkg -sfi && namcap PKGBUILD *.pkg.tar.zst
```

Publicar (necesita una cuenta de AUR con tu clave SSH):

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
- Commit `docs: start the changelog for the next version`.
