FROM python:3.14-slim
WORKDIR /app
COPY mvp_lc/requirements.txt mvp_lc/requirements.txt
RUN pip install --no-cache-dir -r mvp_lc/requirements.txt
COPY mvp_common mvp_common
COPY mvp_lc mvp_lc
CMD ["sh", "-c", "python -m uvicorn mvp_lc.web.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
