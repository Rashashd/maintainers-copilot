FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit==1.40.0 httpx==0.28.0
COPY chatbot/ .
EXPOSE 8501
HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
