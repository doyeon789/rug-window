"""Rug Window: sweep your messy desktop under a 3D cloth rug."""

import os

# The OpenBLAS bundled with the numpy and scipy wheels starts one worker
# thread per CPU core and reserves a work buffer for each as soon as numpy is
# imported (measured: about 1.2 GB reserved on a 20-core machine). The rug's
# matrices are tiny, so one thread is just as fast (also measured).
#
# This must run before numpy is first imported, so it lives in the package's
# __init__, which runs before any submodule. It sets a process-wide variable
# (child processes inherit it), which is fine because this package is an
# app, not a library. It has no effect if numpy was imported before
# rug_window (as in tools/cloth_preview.py and the tests); every app entry
# point imports rug_window first. setdefault keeps a value the user set.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
