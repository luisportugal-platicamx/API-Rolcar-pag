# Usamos la imagen oficial de Playwright que ya tiene Python y los navegadores
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Directorio de trabajo
WORKDIR /app

# Copiamos los archivos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Exponemos el puerto que usa Render (por defecto 10000)
EXPOSE 10000

# Comando para arrancar la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
