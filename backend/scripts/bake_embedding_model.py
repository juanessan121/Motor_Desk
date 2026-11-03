"""Descarga y verifica el modelo de embeddings que se hornea en la imagen.

Se ejecuta durante `docker build`. No forma parte de la API: solo prepara los
archivos que `app.embeddings` lee desde `EMBEDDING_MODEL_DIR`.

Los tres fallos que producia la versión de una línea en el Dockerfile eran:
`urlretrieve` no crea directorios (fallaba en `onnx/model.onnx`), no se
verificaba que la descarga estuviera completa, y un corte de red dejaba un ONNX
truncado que el runtime no detectaba hasta la primera consulta.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# (ruta remota, ruta local, tamaño mínimo en bytes)
FILES = (
    ("onnx/model.onnx", "onnx/model.onnx", 10_000_000),
    ("tokenizer.json", "tokenizer.json", 100_000),
)
ATTEMPTS = 3


def download(base: str, remote: str, target: Path, minimum: int) -> None:
    if target.exists() and target.stat().st_size >= minimum:
        print(f"  ya en cache: {target} ({target.stat().st_size:,} B)")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(f"{base}/{remote}", timeout=600) as response:
                with partial.open("wb") as handle:
                    while chunk := response.read(1 << 20):
                        handle.write(chunk)
            if partial.stat().st_size < minimum:
                raise OSError(f"{remote} incompleto: {partial.stat().st_size:,} B")
            partial.replace(target)
            print(f"  descargado: {target} ({target.stat().st_size:,} B)")
            return
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last = exc
            partial.unlink(missing_ok=True)
            print(f"  intento {attempt}/{ATTEMPTS} fallido ({exc}); reintentando", flush=True)
    raise SystemExit(f"No se pudo descargar {remote}: {last}")


def main() -> int:
    base = os.environ["EMBEDDING_BASE_URL"]
    root = Path(os.environ.get("EMBEDDING_MODEL_DIR", "models")) / os.environ["EMBEDDING_MODEL_NAME"]
    for remote, local, minimum in FILES:
        download(base, remote, root / local, minimum)
    print(f"  modelo listo en {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())