FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN apt-get update && apt-get install -y dos2unix && dos2unix run.sh && chmod +x run.sh
CMD ["./run.sh"]
