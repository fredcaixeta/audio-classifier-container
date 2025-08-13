# Usa uma imagem base do Python 3.10
FROM python:3.10-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala as dependências do sistema necessárias para as bibliotecas de áudio
# O ffmpeg é crucial para o yt-dlp e o demucs
RUN apt-get update && apt-get install -y ffmpeg

# Copia o arquivo pyproject.toml
COPY pyproject.toml .

# Instala o uv e depois sincroniza as dependências do projeto
RUN pip install uv
RUN uv sync

# Copia o resto da aplicação, incluindo o app.py e os modelos
COPY . .

# Expõe a porta que o aplicativo vai usar (geralmente 8000 para Gunicorn)
EXPOSE 8000

# Comando para iniciar a aplicação com o Gunicorn
# 'app' é o nome do seu arquivo Python (app.py)
# 'app' é a instância do Flask (app = Flask(__name__))
# O bind 0.0.0.0 permite que o Render se conecte à aplicação
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
