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
RUN python -m spacy download en_core_web_sm

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
