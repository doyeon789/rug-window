# Third-party notices

Rug Window itself is released under the MIT License (see `LICENSE`).
The Windows release bundles the following third-party software and assets.

| Component | License | Source |
|---|---|---|
| Python runtime | PSF License 2.0 | <https://www.python.org/> |
| Qt 6 (via PySide6-Essentials) | LGPL-3.0 | <https://www.qt.io/> |
| PySide6-Essentials, Shiboken6 | LGPL-3.0 | <https://pypi.org/project/PySide6-Essentials/> |
| NumPy | BSD-3-Clause | <https://numpy.org/> |
| SciPy | BSD-3-Clause | <https://scipy.org/> |
| PyOpenGL | BSD-style (PyOpenGL license) | <https://pyopengl.sourceforge.net/> |
| pywin32 | PSF License | <https://github.com/mhammond/pywin32> |
| PyInstaller bootloader | GPL-2.0 with a bootloader exception (allows distributing bundled apps under any license) | <https://pyinstaller.org/> |
| "Carpet 006" texture (ambientCG) | CC0 1.0 | <https://ambientcg.com/view?id=Carpet006> |

## Qt / PySide6 (LGPL-3.0)

Qt and PySide6 are used as separate dynamic libraries (`.dll` / `.pyd` files in
the `_internal` folder of the release). You may replace them with your own
compatible builds. The full license text is at
<https://www.gnu.org/licenses/lgpl-3.0.html>, and the corresponding source code
is available from <https://download.qt.io/> and
<https://code.qt.io/cgit/pyside/pyside-setup.git/>.

Each bundled package also ships its own license file inside the release's
`_internal` folder (`*.dist-info/` directories).
