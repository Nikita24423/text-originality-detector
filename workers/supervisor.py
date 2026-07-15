"""Запуск пула ML worker-процессов."""
from __future__ import annotations

import multiprocessing as mp
import signal
import sys
import time

from config import get_settings
from workers.ml_worker import run_worker_loop


def _worker_entry(worker_id: int) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    run_worker_loop(worker_id)


def main() -> None:
    settings = get_settings()
    count = max(1, settings.ml_workers)
    print(f"Запуск {count} ML worker-процессов...", flush=True)

    ctx = mp.get_context("spawn")
    processes = []
    for i in range(1, count + 1):
        p = ctx.Process(target=_worker_entry, args=(i,), daemon=False)
        p.start()
        processes.append(p)
        print(f"  worker #{i} pid={p.pid}", flush=True)

    try:
        while True:
            time.sleep(5)
            for p in processes:
                if not p.is_alive():
                    print(f"Worker pid={p.pid} завершился, перезапуск...", flush=True)
                    idx = processes.index(p) + 1
                    new_p = ctx.Process(target=_worker_entry, args=(idx,), daemon=False)
                    new_p.start()
                    processes[processes.index(p)] = new_p
    except KeyboardInterrupt:
        print("\nОстановка workers...", flush=True)
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=10)


if __name__ == "__main__":
    main()
