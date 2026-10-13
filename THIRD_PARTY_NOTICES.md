# Third-party notices

Rug Window itself is released under the MIT License (see `LICENSE`).
The Windows release bundles the following third-party software and assets.
Their license texts are in the release's `licenses/` folder.

| Component | Version | License | Source |
|---|---|---|---|
| Python runtime | 3.13 | PSF License 2.0 | <https://www.python.org/> |
| libffi (`libffi-8.dll`, used by Python's ctypes) | 3.4 | MIT (`licenses/libffi-MIT.txt`) | <https://github.com/libffi/libffi> |
| OpenSSL 3 (`libssl`, `libcrypto`; loaded by Qt's TLS plugin and Python) | 3.x | Apache-2.0 (`licenses/Apache-2.0.txt`) | <https://www.openssl.org/> |
| Qt 6 (via PySide6-Essentials) | 6.12.0 | LGPL-3.0 | <https://download.qt.io/official_releases/qt/6.12/> |
| PySide6-Essentials, Shiboken6 | 6.12.0 | LGPL-3.0 (used under the LGPL option of their LGPL/GPL/commercial licensing) | <https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0> |
| NumPy | 2.5.4 | BSD-3-Clause (plus the bundled components listed in its license files) | <https://numpy.org/> |
| SciPy | 1.18.1 | BSD-3-Clause (plus the bundled components listed in its license files) | <https://scipy.org/> |
| OpenBLAS (bundled in NumPy and SciPy) | — | BSD-3-Clause (text included in the NumPy and SciPy license files) | <https://www.openblas.net/> |
| PyOpenGL | 3.1.10 | BSD-style (PyOpenGL license) | <https://pyopengl.sourceforge.net/> |
| pywin32 | 312 | PSF-style (its own license texts included) | <https://github.com/mhammond/pywin32> |
| Microsoft Visual C++ runtimes (`vcruntime140*.dll`, `msvcp140*.dll`, `MSVCR100.dll`) | — | Microsoft Visual C++ Redistributable license (redistributable with applications) | <https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files> |
| PyInstaller bootloader | 6.22 | GPL-2.0 with a bootloader exception (allows distributing bundled apps under any license) | <https://pyinstaller.org/> |
| "Carpet 006" texture (ambientCG) | — | CC0 1.0 | <https://ambientcg.com/view?id=Carpet006> |

## Qt / PySide6 (LGPL-3.0)

Qt 6.12.0 and PySide6/Shiboken6 6.12.0 are shipped **unmodified**, as the
official PyPI wheels, and are used as separate dynamic libraries (`.dll` /
`.pyd` files in the release's `_internal` folder). You may replace them with
your own compatible builds; the application loads them from that folder.

- License texts: `licenses/LGPL-3.0.txt` and `licenses/GPL-3.0.txt` (LGPL-3.0
  builds on GPL-3.0).
- Source code for these exact versions: Qt at
  <https://download.qt.io/official_releases/qt/6.12/>, PySide6/Shiboken6 at
  <https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0>.
