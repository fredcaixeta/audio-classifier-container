# Usa uma imagem base do Python 3.10
FROM python:3.10-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y ffmpeg

# Copia os arquivos de dependências
COPY requirements.txt .

# Instala o torch e o torchaudio otimizado para CPU, evitando conflitos
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Instala o resto das dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto da aplicação, incluindo o app.py e os modelos
COPY . .

# Comando para iniciar a aplicação com o Gunicorn, usando a porta 7860
CMD gunicorn -w 1 --bind 0.0.0.0:7860 app:app
