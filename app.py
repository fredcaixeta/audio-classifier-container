import os
import torch
import torchaudio
import numpy as np
import joblib
import subprocess
import shutil
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL

# --- 1. CONFIGURAÇÃO ---
NUM_DIMENSOES_PARA_MODELO = 6
NOME_ARQUIVO_MODELO = 'modelo_random_forest.joblib'
NOME_ARQUIVO_SCALER = 'scaler.joblib'
DEMUCS_TEMP_DIR = 'demucs_temp'
DOWNLOAD_TEMP_DIR = 'download_temp'

# --- 2. SETUP DO FLASK ---
app = Flask(__name__)
CORS(app)

# --- 3. FUNÇÃO AUXILIAR PARA EXTRAIR EMBEDDINGS (COMPLETOS) ---
def criar_embedding_mfcc(caminho_do_audio):
    """
    Carrega um arquivo de áudio e cria um embedding com 40 MFCCs.
    """
    try:
        waveform, sample_rate = torchaudio.load(caminho_do_audio)
        if waveform.shape == (0,):
            return None
        if waveform.shape[-1] < 1000:
            return None
        if waveform.shape[-2] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        mfcc_transform = torchaudio.transforms.MFCC(
            sample_rate=sample_rate,
            n_mfcc=40,
            melkwargs={"n_fft": 2048, "hop_length": 512, "n_mels": 128}
        )
        mfcc_tensor = mfcc_transform(waveform)
        embedding = torch.mean(mfcc_tensor, dim=2)
        return embedding.squeeze().numpy()
    except Exception as e:
        print(f"Erro ao criar embedding para {caminho_do_audio}: {e}")
        return None

# --- 4. FUNÇÃO PARA SEPARAR VOCAIS ---
def separar_vocal_demucs(caminho_audio_entrada, output_dir):
    """Usa Demucs para separar o vocal de um arquivo de áudio."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"Separando vocais do arquivo: {caminho_audio_entrada}...")
        
        comando = [
            "demucs", "--two-stems=vocals", "-o", output_dir, caminho_audio_entrada
        ]
        subprocess.run(comando, check=True, capture_output=True, text=True)
        
        nome_base = os.path.splitext(os.path.basename(caminho_audio_entrada))[0]
        # Demucs cria uma estrutura de pastas como output_dir/htdemucs/nome_base/
        demucs_path = os.path.join(output_dir, 'htdemucs', nome_base)
        
        caminho_vocal = os.path.join(demucs_path, 'vocals.wav')

        if os.path.exists(caminho_vocal):
            print("Vocal separado com sucesso.")
            return caminho_vocal
        else:
            print("Aviso: O Demucs não encontrou vocais no arquivo.")
            return None
    except subprocess.CalledProcessError as e:
        print(f"Erro ao rodar Demucs: {e.stderr}")
        return None
    except Exception as e:
        print(f"Erro inesperado durante a separação do vocal: {e}")
        return None

# --- 5. ROTA DE CLASSIFICAÇÃO ---
@app.route('/api/classify', methods=['POST'])
def classify_audio():
    try:
        # Carrega o modelo e o scaler
        modelo = joblib.load(NOME_ARQUIVO_MODELO)
        scaler = joblib.load(NOME_ARQUIVO_SCALER)
        
        # Obtém a URL do corpo da requisição
        data = request.get_json()
        url = data.get('url')
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400

        # Cria diretórios temporários
        os.makedirs(DOWNLOAD_TEMP_DIR, exist_ok=True)
        
        # 5.1. Baixa o áudio da URL usando uma configuração mais robusta
        print(f"Baixando áudio da URL: {url}...")
        try:
            # Opções do yt-dlp para um download mais confiável
            # O 'outtmpl' agora usa o 'id' do vídeo para evitar problemas com nomes longos
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_TEMP_DIR, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
            }
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                # O yt-dlp retorna o ID do vídeo, que é usado para encontrar o arquivo
                video_id = info_dict.get('id', 'video') 
                caminho_audio_original = os.path.join(DOWNLOAD_TEMP_DIR, f"{video_id}.wav")
                
                if not os.path.exists(caminho_audio_original):
                    raise Exception("Erro ao baixar ou converter o arquivo de áudio.")

        except Exception as e:
            return jsonify({'error': f'Erro ao baixar o áudio: {e}'}), 500
        
        # 5.2. Separa o vocal
        caminho_vocal_separado = separar_vocal_demucs(caminho_audio_original, DEMUCS_TEMP_DIR)
        
        if not caminho_vocal_separado:
            return jsonify({'error': 'Erro ao separar o vocal do áudio.'}), 500

        # 5.3. Cria os embeddings e faz a inferência
        embedding_original = criar_embedding_mfcc(caminho_audio_original)
        embedding_demucs = criar_embedding_mfcc(caminho_vocal_separado)
        
        if embedding_original is None or embedding_demucs is None:
            return jsonify({'error': 'Erro ao extrair embeddings do áudio.'}), 500
            
        features_orig = embedding_original[:NUM_DIMENSOES_PARA_MODELO]
        features_demucs = embedding_demucs[:NUM_DIMENSOES_PARA_MODELO]
        
        final_feature = np.concatenate((features_orig, features_demucs))
        final_feature_reshaped = final_feature.reshape(1, -1)
        final_feature_scaled = scaler.transform(final_feature_reshaped)
        
        probabilidade = modelo.predict_proba(final_feature_scaled)
        predicao = modelo.predict(final_feature_scaled)
        
        label_predito = 'IA' if predicao[0] == 1 else 'REAL'
        probabilidade_predita = probabilidade[0][1] if predicao[0] == 1 else probabilidade[0][0]

        print(f"label {label_predito}")
        print(f"prob {str(probabilidade_predita)}")
        # 5.4. Limpa os arquivos temporários
        shutil.rmtree(DEMUCS_TEMP_DIR)
        shutil.rmtree(DOWNLOAD_TEMP_DIR)
        
        # 5.5. Retorna o resultado
        return jsonify({
            'label': label_predito,
            'probability': probabilidade_predita
        }), 200

    except Exception as e:
        print(f"Erro geral no servidor: {e}")
        return jsonify({'error': 'Erro interno do servidor.'}), 500

# --- 6. EXECUÇÃO DO FLASK ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

