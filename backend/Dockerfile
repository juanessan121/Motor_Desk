FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/api
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home workshop

# Los embeddings son opcionales. La imagen estándar arranca y busca por
# texto sin descargar modelos; habilite INCLUDE_EMBEDDINGS para búsqueda semántica.
# paraphrase-multilingual-MiniLM-L12-v2 · Apache-2.0 · 384 dims
ARG INCLUDE_EMBEDDINGS=false
ARG EMBEDDING_REPO=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ARG EMBEDDING_REVISION=e8f8c211226b894fcb81acc59f3b34ba3efd5f42
ENV EMBEDDING_BASE_URL=https://huggingface.co/${EMBEDDING_REPO}/resolve/${EMBEDDING_REVISION} \
    EMBEDDING_MODEL_DIR=/srv/api/models \
    EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
COPY scripts/bake_embedding_model.py ./scripts/bake_embedding_model.py
RUN mkdir -p models \
 && if [ "$INCLUDE_EMBEDDINGS" = "true" ]; then python scripts/bake_embedding_model.py; fi \
 && chown -R workshop:workshop models

COPY . .
# El volumen `catalog_cache` se monta aqui en compose.yaml. Docker copia
# contenido y propietario desde la imagen al volumen vacio, por lo que crear
# el directorio con el usuario correcto evita el PermissionError del importador.
RUN mkdir -p /var/cache/motordesk/catalog && chown -R workshop:workshop /var/cache/motordesk
USER workshop
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]