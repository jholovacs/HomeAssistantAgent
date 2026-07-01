FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir aiohttp==3.11.12

COPY mock_server.py .

EXPOSE 8000
CMD ["python", "mock_server.py"]
