FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock README.md LICENSE NOTICE THIRD_PARTY_LICENSES.txt THIRD_PARTY_NOTICES.md ./
COPY src/ src/
COPY --from=web /src/wontology/static/app* src/wontology/static/
RUN python -m pip install --no-cache-dir -c requirements.lock .
ENV WONTOLOGY_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8787
ENTRYPOINT ["wontology", "--container", "--no-browser"]
