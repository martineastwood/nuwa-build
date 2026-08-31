# Releasing Nuwa

Cut the public pieces in this order so PyPI, GitHub, the Action, and the docs tell the same story.

Documentation: [https://martineastwood.github.io/nuwa-docs/](https://martineastwood.github.io/nuwa-docs/)

## Support matrix (do not overclaim)

| Item | Status |
| --- | --- |
| CPython 3.10–3.14 | Tested |
| Linux, macOS, Windows | Native runner architecture |
| Linux wheels | manylinux x86_64 (official `linux_x64` Nim archive) |
| Free-threaded (`cp314t`) | Not tested |
| PyPy | Not tested |
| musllinux | Skipped (glibc Nim binaries) |
| Linux aarch64 | Not tested (Action installs x86_64 Nim on Linux) |

## Version alignment for this line-up

| Piece | Version to ship |
| --- | --- |
| nuwa-build (PyPI) | `0.5.2` (`v0.5.2`) |
| nuwa-sdk (Nimble / GitHub) | `0.4.4` (`v0.4.4`) |
| nuwa-build-action | `v1` on current `main` |
| nuwa-docs | deploy `main` to GitHub Pages |
| nuwa-example | match template pins (`nuwa_sdk@0.4.4`, Python `>=3.10`) |

## Checklist

1. **Docs** — Merge nuwa-docs, confirm GitHub Pages is enabled (branch `gh-pages` or the workflow target), open the live site, spot-check the support matrix.
2. **SDK** — Tag and push `v0.4.4` after merging Nim source changes. Confirm CI is green.
3. **Action** — Merge CI and README updates. Move the `v1` tag to the new `main` commit:
   `git tag -f v1 && git push origin v1 --force`
   (consumers pin `@v1`; warn if anyone needs an immutable digest).
4. **nuwa-build** — Confirm tests/lint on `main`. Changelog date is correct. Tag and push:
   `git tag v0.5.2 && git push origin v0.5.2`
   PyPI publish is tag-triggered. Confirm the GitHub Release exists for `v0.5.2` (create one if the workflow does not).
5. **Example** — Merge pin and workflow updates. Do not commit `.nimble/` caches.
6. **Sanity** — On a clean machine: install Nim, `pip install nuwa-build==0.5.2`, `nuwa new demo`, `nuwa develop`, `python example.py`.

Do not announce the release until step 6 works and the docs page matches the version on PyPI.
