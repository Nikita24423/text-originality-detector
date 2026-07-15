"""ML worker: обработка задач из очереди PostgreSQL."""
from __future__ import annotations

import json
import os
import sys
import time
import warnings

# Ограничение потоков BLAS/torch — один процесс = одно ядро inference
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

warnings.filterwarnings("ignore")

import torch

from config import get_settings
from database import (
    complete_task,
    fail_task,
    fetch_next_task,
    load_corpus_texts,
    update_task_progress,
)
from detector.pipeline import AnalysisPipeline


def run_worker_loop(worker_id: int, idle_sleep: float = 2.0) -> None:
    settings = get_settings()
    torch.set_num_threads(1)
    print(f"[worker #{worker_id}] загрузка моделей...", flush=True)
    pipeline = AnalysisPipeline(settings=settings, device="cpu")
    print(f"[worker #{worker_id}] готов", flush=True)

    while True:
        task = fetch_next_task()
        if not task:
            time.sleep(idle_sleep)
            continue

        task_id = int(task["id"])
        mode = task["mode"]
        payload = task["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        filename = task.get("filename") or payload.get("filename") or "document"
        extraction_meta = payload.get("extraction_meta")

        def progress(step: str) -> None:
            try:
                update_task_progress(task_id, step)
            except Exception as exc:
                print(f"[worker #{worker_id}] progress skip: {exc}", flush=True)

        try:
            if mode == "analytics":
                from services.analytics_service import analyze_document

                document_id = int(payload["document_id"])
                result = analyze_document(document_id, pipeline=pipeline)
            elif mode == "compare":
                result = pipeline.analyze_compare(
                    payload.get("text", ""),
                    payload.get("reference_text", ""),
                    filename_a=filename,
                    filename_b=payload.get("reference_filename", "reference"),
                    extraction_meta=extraction_meta,
                    on_progress=progress,
                )
            else:
                corpus_texts: list[str] = payload.get("corpus_texts") or []
                corpus_labels: list[str] = payload.get("corpus_labels") or []
                corpus_source_ids = payload.get("corpus_source_ids")

                if corpus_source_ids and not corpus_texts:
                    corpus_texts, corpus_labels = load_corpus_texts(corpus_source_ids)

                if not corpus_texts and payload.get("corpus"):
                    from services.text_helpers import parse_corpus_text

                    corpus_texts, corpus_labels = parse_corpus_text(payload["corpus"])

                if not corpus_texts:
                    fail_task(task_id, "Добавьте хотя бы один источник для сравнения.")
                    continue

                result = pipeline.analyze_corpus(
                    payload.get("text", ""),
                    corpus_texts,
                    corpus_labels,
                    corpus_source_ids=corpus_source_ids,
                    filename=filename,
                    extraction_meta=extraction_meta,
                    on_progress=progress,
                )

            complete_task(task_id, result)
            print(f"[worker #{worker_id}] задача {task_id} выполнена", flush=True)
        except Exception as exc:
            fail_task(task_id, str(exc))
            print(f"[worker #{worker_id}] задача {task_id} ошибка: {exc}", flush=True)


def main() -> None:
    worker_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_worker_loop(worker_id)


if __name__ == "__main__":
    main()
