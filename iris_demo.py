import cv2
import mediapipe as mp
import numpy as np
import csv
import time
import os
from datetime import datetime

# === NOVOS IMPORTS PARA SERVIDOR HTTP ===
import asyncio
import threading
from aiohttp import web
import aiohttp_cors

mp_face_mesh = mp.solutions.face_mesh

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# === SERVIDOR HTTP EM THREAD SEPARADO ===
class EyeTrackingServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.latest_data = None
        self.server_thread = None
        self.loop = None
        
    def start_server_background(self):
        """Inicia o servidor em uma thread separada"""
        async def create_app():
            app = web.Application()
            
            # Configurar rotas
            app.router.add_get('/data', self.get_data)
            
            # Configurar CORS
            cors = aiohttp_cors.setup(app, defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                )
            })
            
            for route in list(app.router.routes()):
                cors.add(route)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            print(f"🚀 Servidor Eye-Tracking HTTP: http://{self.host}:{self.port}")
            print("✅ Servidor rodando em background...")
            
            # Manter rodando
            while True:
                await asyncio.sleep(1)
        
        # Rodar em loop separado
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(create_app())
        except Exception as e:
            print(f"Erro no servidor: {e}")
    
    def start(self):
        """Inicia o servidor em background"""
        self.server_thread = threading.Thread(target=self.start_server_background)
        self.server_thread.daemon = True
        self.server_thread.start()
        # Dar tempo para o servidor inicializar
        time.sleep(2)
    
    async def get_data(self, request):
        if self.latest_data:
            return web.json_response(self.latest_data)
        else:
            return web.json_response({'status': 'no_data'})
    
    def update_data(self, data):
        """Atualiza os dados mais recentes (thread-safe)"""
        self.latest_data = data

eye_tracking_server = EyeTrackingServer()

# =============================================================================
# CONFIGURAÇÕES - AJUSTE AQUI OS VALORES DA SUA CALIBRAÇÃO
# =============================================================================

# COLE AQUI OS VALORES DA SUA ÚLTIMA CALIBRAÇÃO (do arquivo calibracao_dados.txt)
CALIB_PARAMS = {
    'a': 5828.544403,  # ← COLE O VALOR 'a' AQUI
    'b': -54.281242    # ← COLE O VALOR 'b' AQUI
}

W_real = 6.5  # cm - distância média real entre cantos externos dos olhos

# CAMINHO DO VÍDEO - ALTERE PARA O SEU ARQUIVO .mp4
VIDEO_PATH = "julio_treme.mp4"  # ← ALTERE AQUI

# =============================================================================

# Buffer para salvar dados
buffer = []
frame_number = 0

def calculate_distance(eye_distance_px, calib_params):
    """Calcular distância usando modelo calibrado"""
    if eye_distance_px <= calib_params['b']:
        return float('inf')  # Evitar divisão por zero
    return calib_params['a'] / (eye_distance_px - calib_params['b'])

def calculate_iris_center(mesh_points, iris_indices, img_w, img_h):
    """
    Calcula o centro da área interna do contorno da íris
    Retorna coordenadas (x, y) do centro
    """
    try:
        # Obter pontos da íris
        iris_points = [mesh_points[i] for i in iris_indices]
        
        # Converter para array numpy
        iris_array = np.array(iris_points, dtype=np.int32)
        
        # Calcular centro geométrico (centróide)
        center_x = int(np.mean(iris_array[:, 0]))
        center_y = int(np.mean(iris_array[:, 1]))
        
        # Verificar se o ponto está dentro do contorno
        # Criar máscara para verificar se o centro está dentro do polígono
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cv2.fillPoly(mask, [iris_array], 255)
        
        # Se o centro não estiver dentro do polígono, calcular ponto mais próximo
        if mask[center_y, center_x] == 0:
            # Encontrar o ponto mais próximo que está dentro do contorno
            distances = []
            for y in range(max(0, center_y-10), min(img_h, center_y+10)):
                for x in range(max(0, center_x-10), min(img_w, center_x+10)):
                    if mask[y, x] > 0:
                        dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                        distances.append((dist, x, y))
            
            if distances:
                distances.sort()
                center_x, center_y = distances[0][1], distances[0][2]
        
        return (center_x, center_y)
        
    except Exception as e:
        print(f"Erro ao calcular centro da íris: {e}")
        return (0, 0)

def draw_iris_center(frame, center, iris_side):
    """
    Desenha o ponto central da íris no frame
    """
    if center != (0, 0):
        color = (255, 0, 0) if iris_side == "left" else (0, 0, 255)  # Vermelho para esquerda, Azul para direita
        cv2.circle(frame, center, 3, color, -1)  # Ponto central
        cv2.circle(frame, center, 6, color, 1)   # Círculo externo
        
        # Texto indicando qual íris
        text_offset = -15 if iris_side == "left" else 15
        cv2.putText(frame, f"{iris_side[0].upper()}",
                   (center[0] + text_offset, center[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

def add_image_overlay(frame, overlay_img, alpha=0.5):
    """
    Adiciona imagem PNG transparente no canto superior direito
    """
    if overlay_img is None:
        return frame
    
    frame_h, frame_w = frame.shape[:2]
    overlay_h, overlay_w = overlay_img.shape[:2]
    
    # Definir posição no canto superior direito
    x_offset = frame_w - overlay_w - 10
    y_offset = 10
    
    # Redimensionar se a imagem for muito grande
    max_width = frame_w // 3
    if overlay_w > max_width:
        scale_factor = max_width / overlay_w
        new_width = int(overlay_w * scale_factor)
        new_height = int(overlay_h * scale_factor)
        overlay_img = cv2.resize(overlay_img, (new_width, new_height))
        overlay_h, overlay_w = overlay_img.shape[:2]
        x_offset = frame_w - overlay_w - 10
    
    # Garantir que a imagem cabe no frame
    if x_offset < 0:
        x_offset = 0
    if y_offset < 0:
        y_offset = 0
    
    # Se a imagem tem canal alpha (transparência)
    if overlay_img.shape[2] == 4:
        overlay_rgb = overlay_img[:, :, :3]
        overlay_alpha = overlay_img[:, :, 3] / 255.0
        
        roi = frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w]
        
        for c in range(3):
            roi[:, :, c] = (overlay_alpha * overlay_rgb[:, :, c] + 
                           (1 - overlay_alpha) * roi[:, :, c])
        
        frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w] = roi
    else:
        roi = frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w]
        cv2.addWeighted(overlay_img, alpha, roi, 1 - alpha, 0, roi)
    
    return frame

# Verificar se os parâmetros de calibração foram definidos
if CALIB_PARAMS['a'] == 5828.54 or CALIB_PARAMS['b'] == -54.28:
    print("AVISO: Você precisa colocar seus próprios valores de calibração!")
    print("Abra o arquivo calibracao_dados.txt e copie os valores de 'a' e 'b'")
    print("Cole esses valores nas variáveis CALIB_PARAMS no código")
    exit()

print("=== EYE TRACKING EM VÍDEO COM SERVIDOR HTTP ===")
print(f"Parâmetros de calibração: a={CALIB_PARAMS['a']:.2f}, b={CALIB_PARAMS['b']:.2f}")
print(f"Vídeo: {VIDEO_PATH}")
print("Pressione ESC para sair, ESPAÇO para pausar")

def main():
    # Iniciar servidor HTTP em thread separada
    print("Iniciando servidor HTTP...")
    eye_tracking_server.start()
    
    # Carregar o vídeo
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print(f"Erro: Não foi possível abrir o vídeo {VIDEO_PATH}")
        return

    # Obter informações do vídeo
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    print(f"Informações do vídeo: {total_frames} frames, {fps:.1f} FPS, {duration:.1f} segundos")
    print("Vídeo rodando em loop - Pressione ESC para parar")

    # Inicia MediaPipe FaceMesh
    with mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:

        paused = False
        frame_number = 0
        loop_count = 0

        while True:
            if not paused:
                success, frame = cap.read()
                if not success:
                    # Fim do vídeo - reiniciar do início
                    print("Fim do vídeo - reiniciando...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame_number = 0
                    loop_count += 1
                    success, frame = cap.read()
                    if not success:
                        print("Erro ao reiniciar vídeo")
                        break

                frame_number += 1
                
                # Mostrar progresso (considerando loop)
                current_frame = frame_number
                progress = (current_frame / total_frames) * 100
                loop_info = f"Loop {loop_count + 1}" if loop_count > 0 else "Primeira execução"
                print(f"Processando: {current_frame}/{total_frames} ({progress:.1f}%) - {loop_info}", end='\r')

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            img_h, img_w = frame.shape[:2]

            distance_cm = None
            eye_distance_px = 0
            left_iris_center = (0, 0)
            right_iris_center = (0, 0)

            if results.multi_face_landmarks:
                mesh_points = [
                    (int(p.x * img_w), int(p.y * img_h))
                    for p in results.multi_face_landmarks[0].landmark
                ]

                # Desenhar contornos da íris
                cv2.polylines(frame, [np.array([mesh_points[i] for i in LEFT_IRIS])],
                              True, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.polylines(frame, [np.array([mesh_points[i] for i in RIGHT_IRIS])],
                              True, (0, 255, 0), 1, cv2.LINE_AA)

                # Calcular distância entre cantos dos olhos
                left_eye = mesh_points[33]
                right_eye = mesh_points[263]
                eye_distance_px = np.linalg.norm(np.array(left_eye) - np.array(right_eye))

                # Calcular distância usando modelo calibrado
                distance_cm = calculate_distance(eye_distance_px, CALIB_PARAMS)

                # Calcular centros das íris
                left_iris_center = calculate_iris_center(mesh_points, LEFT_IRIS, img_w, img_h)
                right_iris_center = calculate_iris_center(mesh_points, RIGHT_IRIS, img_w, img_h)

                # Desenhar centros das íris
                draw_iris_center(frame, left_iris_center, "left")
                draw_iris_center(frame, right_iris_center, "right")

                # === ATUALIZAR DADOS NO SERVIDOR HTTP ===
                data = {
                    'timestamp': time.time(),
                    'left_iris': {'x': left_iris_center[0], 'y': left_iris_center[1]},
                    'right_iris': {'x': right_iris_center[0], 'y': right_iris_center[1]},
                    'frame_number': frame_number,
                    'eye_distance_px': eye_distance_px,
                    'distance_cm': distance_cm,
                    'loop_count': loop_count
                }
                eye_tracking_server.update_data(data)

                # Adicionar ao buffer (opcional - cuidado com memória em loops longos)
                buffer.append([
                    frame_number, 
                    distance_cm, 
                    eye_distance_px,
                    left_iris_center[0],  # left_iris_x
                    left_iris_center[1],  # left_iris_y
                    right_iris_center[0], # right_iris_x
                    right_iris_center[1], # right_iris_y
                    loop_count
                ])

                # Mostrar informações no frame
                cv2.putText(frame, f"Distancia: {distance_cm:.1f} cm",
                            (30, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            1, (0, 0, 255), 2)
                cv2.putText(frame, f"Olhos: {eye_distance_px:.1f}px",
                            (30, 70), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (255, 255, 0), 2)
                
                # Mostrar coordenadas das íris
                cv2.putText(frame, f"L: ({left_iris_center[0]},{left_iris_center[1]})",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (255, 0, 0), 1)
                cv2.putText(frame, f"R: ({right_iris_center[0]},{right_iris_center[1]})",
                            (30, 130), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 0, 255), 1)
                
                # Mostrar status
                cv2.putText(frame, f"HTTP: http://localhost:8765/data",
                            (30, 160), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 1)
                cv2.putText(frame, f"Frame: {frame_number} - Loop: {loop_count + 1}",
                            (30, 180), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 1)
            else:
                cv2.putText(frame, "Rosto nao detectado",
                            (30, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            1, (0, 0, 255), 2)

            # Informações do vídeo
            cv2.putText(frame, f"Frame: {frame_number}/{total_frames}",
                        (img_w - 300, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Progresso: {progress:.1f}%",
                        (img_w - 300, 60), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Loop: {loop_count + 1}",
                        (img_w - 300, 90), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
            
            if paused:
                cv2.putText(frame, "PAUSADO", (img_w // 2 - 100, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            cv2.imshow('Eye Tracking - Video + HTTP Server (Loop)', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC - sair
                break
            elif key == 32:  # ESPAÇO - pausar
                paused = not paused
                print("Video pausado" if paused else "Video continuando")
            elif key == ord('q'):  # Q para sair
                break

    # Salvar CSV com dados completos (opcional)
    if buffer:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"eye_tracking_loop_{timestamp}.csv"
        
        with open(csv_filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "frame", 
                "distance_cm", 
                "eye_distance_px",
                "left_iris_x", 
                "left_iris_y", 
                "right_iris_x", 
                "right_iris_y",
                "loop_count"
            ])
            writer.writerows(buffer)
        
        print(f"\nDados salvos em: {csv_filename}")
        print(f"Total de frames processados: {len(buffer)}")
        print(f"Total de loops completos: {loop_count}")

    cap.release()
    cv2.destroyAllWindows()
    print("Processamento concluído!")

if __name__ == "__main__":
    main()