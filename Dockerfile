FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
COPY streamlit_app.py ./streamlit_app.py
COPY assets ./assets
COPY .streamlit ./.streamlit
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir . && chown -R app:app /app
USER app
EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
