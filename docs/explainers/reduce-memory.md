# Reduce memory

> Status: **implemented** (step 1 of the memory work; a rug-sized window is
> the bigger, later step)

## 1. Overview

Rug Window used about 770 MB of working set ("Memory" in Task Manager) and
reserved 1.5 GB of private memory while showing one rug. Two settings cause
most of it, and neither needs a code redesign:

- numpy/scipy's OpenBLAS starts one worker thread per CPU core and reserves a
  buffer for each.
- 4x multisampling (MSAA) on a window as big as the screen.

## 2. Background

- **Working set vs. private (committed) memory.** Working set is the RAM the
  process is using right now (what Task Manager shows). Private memory is
  what it has reserved from Windows; it counts against the system's commit
  limit even if it is never touched.
- **OpenBLAS threads.** numpy and scipy do matrix math through OpenBLAS, which
  on import starts a thread pool sized to the CPU (20 threads here) and
  reserves a work buffer per thread. The rug's matrices are tiny (the
  Catmull-Rom subdivision multiplies 37 x 60 grids), so the extra threads
  never help. `OPENBLAS_NUM_THREADS` must be set **before numpy is first
  imported**; afterwards it is ignored.
- **MSAA.** Multisampling stores several samples per pixel and averages them
  to smooth edges. The buffers are as large as the window times the sample
  count, and the window covers the screen (2880 x 1704 device pixels at 200%
  scaling). On integrated graphics those buffers live in system RAM and show
  up in the working set.

## 3. Structure

- `src/rug_window/__init__.py`: `os.environ.setdefault("OPENBLAS_NUM_THREADS",
  "1")`. The package `__init__` runs before any submodule (`__main__`,
  `rug_widget`, `cloth`), so it runs before numpy is imported, both for
  `python -m rug_window` and for the PyInstaller exe (its entry script
  imports `rug_window.__main__`). `setdefault` keeps a value the user set.
- `src/rug_window/__main__.py`: `default_surface_format()` asks for 2 samples
  instead of 4.

## 4. Design decisions

Measured on the app itself (started from source, 10 s after launch, rug
settled):

| | Working set | Private | Threads |
|---|---|---|---|
| Before | 767 MB | 1,507 MB | 59 |
| After | 552 MB | 281 MB | 21 |
| After, PyInstaller exe | 544 MB | 266 MB | 21 |

The exe row confirms the environment variable is set early enough in the
frozen app too.

Per-frame numpy work with one OpenBLAS thread: subdivision 0.69 → 0.68 ms,
cloth step 3.8 → 3.7 ms (no slowdown).

Earlier probe of the MSAA options (same machine, working set): 4x 777 MB,
2x about 570 MB, off about 390 MB. The maintainer compared 0x, 2x, and 4x on
screen and chose 2x.

Alternatives:

- **MSAA off**: about 180 MB less again, but the maintainer preferred 2x
  after comparing them on screen.
- **Post-process smoothing (FXAA)**: needs an extra shader pass; not worth it
  while 2x looks fine.
- **A rug-sized window that follows the rug**: the largest saving (the
  buffers shrink with the window) and likely smoother drags, but a big
  structural change. Planned separately.
- **`threadpoolctl` to limit threads at run time**: an extra dependency for
  what one environment variable already does.

## 5. Caveats

- The OpenBLAS setting only works because nothing imports numpy before the
  `rug_window` package. A future entry point that imports numpy first would
  silently get the old thread pool back.
- Users who set `OPENBLAS_NUM_THREADS` themselves keep their value.
- Which GPU the app renders on (integrated or NVIDIA) is still unknown; it
  decides whether MSAA buffers count as system RAM. Logging the GPU at start
  is a separate, later change.
- Measured on one machine (20 logical cores, 200% scaling). Machines with
  fewer cores reserve less for OpenBLAS to begin with.
