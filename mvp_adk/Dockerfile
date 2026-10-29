FROM python:3.14-slim
WORKDIR /app
COPY mvp_adk/requirements.txt mvp_adk/requirements.txt
RUN pip install --no-cache-dir -r mvp_adk/requirements.txt
COPY mvp_common mvp_common
COPY mvp_adk mvp_adk
CMD ["sh", "-c", "python -m uvicorn mvp_adk.web.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
