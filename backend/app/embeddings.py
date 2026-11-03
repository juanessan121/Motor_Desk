"""Embeddings semánticos locales con ONNX Runtime.

Sin torch ni transformers: solo `onnxruntime` + `numpy` y, para el modelo
multilingüe, `tokenizers` (necesario para SentencePiece).

El catálogo es mayoritariamente inglés (`gor3a`) mientras que el taller busca en
español, así que el modelo por defecto es multilingüe. El english-only
MiniLM-L6-v2 se mantiene como alternativa ligera; medirlo dio 4/6 aciertos
top-1 contra 6/6 del multilingüe en consultas de taller en español.

Los modelos se hornean en la imagen y todo funciona sin red.
"""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import numpy as np

MODELS = {
    "all-MiniLM-L6-v2": {
        "repo": "sentence-transformers/all-MiniLM-L6-v2",
        "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        "dimensions": 384,
        "max_length": 256,
        "tokenizer": "wordpiece",
        "files": {"model": "onnx/model.onnx", "tokenizer": "vocab.txt"},
    },
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "repo": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "revision": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
        "dimensions": 384,
        "max_length": 128,
        "tokenizer": "sentencepiece",
        "files": {"model": "onnx/model.onnx", "tokenizer": "tokenizer.json"},
    },
}

DEFAULT_MODEL = os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
DEFAULT_ROOT = Path(
    os.environ.get("EMBEDDING_MODEL_DIR")
    or Path(__file__).resolve().parent / "models"
)

# Dimensión del modelo por defecto; el esquema la usa para fijar vector(N).
EMBEDDING_DIMENSIONS = MODELS[DEFAULT_MODEL]["dimensions"]

_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_CJK = ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF), (0x2A700, 0x2B73F),
        (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF), (0xF900, 0xFAFF), (0x2F800, 0x2FA1F))


def embedding_model_key(name: str | None = None) -> str:
    name = name or DEFAULT_MODEL
    spec = MODELS.get(name)
    if spec is None:
        raise ValueError(f"Modelo de embeddings desconocido: {name}")
    return f"{name}@{spec['revision'][:7]}"


def embedding_dimensions(name: str | None = None) -> int:
    return MODELS[name or DEFAULT_MODEL]["dimensions"]


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK)


def _is_control(char: str) -> bool:
    if char in ("\t", "\n", "\r"):
        return False
    return unicodedata.category(char).startswith("C")


def _is_punctuation(char: str) -> bool:
    code = ord(char)
    if (33 <= code <= 47) or (58 <= code <= 64) or (91 <= code <= 96) or (123 <= code <= 126):
        return True
    return unicodedata.category(char).startswith("P")


def _is_whitespace(char: str) -> bool:
    if char in (" ", "\t", "\n", "\r"):
        return True
    return unicodedata.category(char) == "Zs"


class WordPieceTokenizer:
    """BasicTokenizer + Wordpiece de BERT, para los modelos con vocab.txt."""

    def __init__(self, vocab_path: Path):
        self.vocab: dict[str, int] = {}
        with vocab_path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                self.vocab[line.rstrip("\n")] = index
        for special in ("[PAD]", "[UNK]", "[CLS]", "[SEP]"):
            if special not in self.vocab:
                raise ValueError(f"El vocabulario no define {special}")
        self.unk, self.cls = self.vocab["[UNK]"], self.vocab["[CLS]"]
        self.sep, self.pad = self.vocab["[SEP]"], self.vocab["[PAD]"]

    def basic(self, text: str) -> list[str]:
        text = "".join(" " if _is_control(c) else c for c in text)
        text = "".join((" " + c + " ") if _is_cjk(c) else c for c in text)
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        pieces: list[str] = []
        for chunk in text.split():
            current = ""
            for char in chunk:
                if _is_punctuation(char):
                    if current:
                        pieces.append(current)
                        current = ""
                    pieces.append(char)
                elif _is_whitespace(char):
                    if current:
                        pieces.append(current)
                        current = ""
                else:
                    current += char
            if current:
                pieces.append(current)
        return pieces

    def wordpiece(self, word: str) -> list[int]:
        if len(word) > 100:
            return [self.unk]
        pieces: list[int] = []
        start = 0
        while start < len(word):
            end, found = len(word), None
            while start < end:
                piece = word[start:end]
                if start > 0:
                    piece = "##" + piece
                index = self.vocab.get(piece)
                if index is not None:
                    found = index
                    break
                end -= 1
            if found is None:
                return [self.unk]
            pieces.append(found)
            start = end
        return pieces

    def encode(self, text: str, max_length: int) -> list[int]:
        budget = max_length - 2
        ids: list[int] = []
        for word in self.basic(text):
            if len(ids) >= budget:
                break
            ids.extend(self.wordpiece(word))
        return [self.cls] + ids[:budget] + [self.sep]

    def batch(self, texts: list[str], max_length: int):
        encoded = [self.encode(text, max_length) for text in texts]
        width = max(len(row) for row in encoded)
        input_ids = np.full((len(encoded), width), self.pad, dtype=np.int64)
        attention = np.zeros((len(encoded), width), dtype=np.int64)
        for row, ids in enumerate(encoded):
            input_ids[row, : len(ids)] = ids
            attention[row, : len(ids)] = 1
        return input_ids, attention, np.zeros_like(input_ids)


class SentencePieceTokenizer:
    """Adaptador sobre `tokenizers` para XLM-R / SentencePiece."""

    def __init__(self, tokenizer_path: Path):
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=128)

    def batch(self, texts: list[str], max_length: int):
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding()
        encoded = self.tokenizer.encode_batch(texts)
        input_ids = np.array([row.ids for row in encoded], dtype=np.int64)
        attention = np.array([row.attention_mask for row in encoded], dtype=np.int64)
        return input_ids, attention, np.zeros_like(input_ids)


class Embedder:
    """Codifica texto a vectores normalizados L2."""

    def __init__(self, model_name: str | None = None, model_dir: Path | None = None):
        self.model_name = model_name or DEFAULT_MODEL
        spec = MODELS[self.model_name]
        self.spec = spec
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_ROOT / self.model_name
        self._session = None
        self._tokenizer = None
        self._error = None

    @property
    def model_key(self) -> str:
        return embedding_model_key(self.model_name)

    @property
    def dimensions(self) -> int:
        return self.spec["dimensions"]

    def _ready(self) -> str | None:
        if self._session is not None:
            return None
        if self._error:
            return self._error
        model = self.model_dir / self.spec["files"]["model"]
        tokenizer = self.model_dir / self.spec["files"]["tokenizer"]
        if not model.exists() or not tokenizer.exists():
            self._error = f"Modelo de embeddings ausente en {self.model_dir}"
            return self._error
        try:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 2))
            options.log_severity_level = 3
            self._session = ort.InferenceSession(
                str(model), options, providers=["CPUExecutionProvider"]
            )
            if self.spec["tokenizer"] == "wordpiece":
                self._tokenizer = WordPieceTokenizer(tokenizer)
            else:
                self._tokenizer = SentencePieceTokenizer(tokenizer)
        except Exception as exc:  # noqa: BLE001 - el catálogo sigue funcionando sin vectores
            self._error = f"No se pudo cargar el modelo de embeddings: {exc}"
            return self._error
        return None

    def available(self) -> bool:
        return self._ready() is None

    def status(self) -> dict:
        error = self._ready()
        return {
            "model": self.model_key,
            "dimensions": self.dimensions,
            "available": error is None,
            "reason": error,
        }

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        error = self._ready()
        if error:
            raise RuntimeError(error)
        if not texts:
            return []
        names = {item.name for item in self._session.get_inputs()}
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            input_ids, attention, token_type = self._tokenizer.batch(
                chunk, self.spec["max_length"]
            )
            feed = {"input_ids": input_ids, "attention_mask": attention}
            if "token_type_ids" in names:
                feed["token_type_ids"] = token_type
            hidden = self._session.run(None, feed)[0]
            mask = attention.astype(np.float32)[..., None]
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            pooled = pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)
            vectors.extend(pooled.astype(np.float32).tolist())
        return vectors

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


_embedder: Embedder | None = None


def embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def pack(vector) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def unpack(blob) -> list[float]:
    return np.frombuffer(blob, dtype=np.float32).tolist()