"""Rug Window: sweep your messy desktop under a 3D cloth rug."""

import os

# OpenBLAS (inside numpy and scipy) starts one worker thread per CPU core and
# reserves a work buffer for each as soon as numpy is imported: about 1.2 GB
# of reserved memory on a 20-core machine. The rug's matrices are tiny, so
# one thread is just as fast (measured). This must run before numpy is first
# imported, which is why it lives in the package's __init__ (it runs before
# any submodule). setdefault keeps a value the user set on purpose.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
