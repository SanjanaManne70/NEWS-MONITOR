# -----------------------------
# 1️⃣ Use a lightweight Python base image
# -----------------------------
FROM python:3.10-slim

# -----------------------------
# 2️⃣ Set working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# 3️⃣ Copy project files
# -----------------------------
COPY . /app

# -----------------------------
# 4️⃣ Install dependencies
# -----------------------------
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
# -----------------------------
# 5️⃣ Expose port for Flask app
# -----------------------------
EXPOSE 5000

# -----------------------------
# 6️⃣ Set environment variable for Flask
# -----------------------------
ENV FLASK_APP=app.py

# -----------------------------
# 7️⃣ Default command: run the app
# -----------------------------
CMD ["python", "app.py"]
