# Usa uma imagem base do Python 3.10
FROM python:3.10-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala as dependências do sistema necessárias para as bibliotecas de áudio
# O ffmpeg é crucial para o yt-dlp e o demucs
RUN apt-get update && apt-get install -y ffmpeg

# Copia o arquivo requirements.txt para o container
COPY requirements.txt .

# Instala o torch e o torchaudio usando a versão de CPU explicitamente
# Isso evita o conflito de dependências e o aviso da NVIDIA
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Instala as demais dependências do projeto
# O pip irá notar que torch e torchaudio já estão instalados
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto da aplicação, incluindo o app.py e os modelos
COPY . .

# Expõe a porta que o aplicativo vai usar (geralmente 8000 para Gunicorn)
EXPOSE 8000

# Comando para iniciar a aplicação com o Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
