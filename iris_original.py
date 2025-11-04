import cv2
import mediapipe as mp
import numpy as np
import csv
import time
import os
import json
from datetime import datetime

mp_face_mesh = mp.solutions.face_mesh

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

cap = cv2.VideoCapture(0)
buffer = []
frame_number = 0

# Valores reais conhecidos (baseados em média humana)
W_real = 6.5  # cm - distância média real entre cantos externos dos olhos

# --- CONFIGURAÇÃO DA IMAGEM PNG ---
PNG_PATH = "C:/Users/alexa/Documents/Codigos/isis_ai.png"
overlay_image = None
overlay_alpha = 0.5  # 50% de transparência

# Tentar carregar a imagem PNG
try:
    if os.path.exists(PNG_PATH):
        overlay_image = cv2.imread(PNG_PATH, cv2.IMREAD_UNCHANGED)
        print(f"Imagem PNG carregada: {PNG_PATH}")
    else:
        print(f"Arquivo não encontrado: {PNG_PATH}")
except Exception as e:
    print(f"Erro ao carregar imagem: {e}")

def save_calibration_data(calib_params, calib_data):
    """
    Salva os dados de calibração em um arquivo .txt
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "calibracao_dados.txt"
    
    try:
        with open(filename, "w", encoding='utf-8') as f:
            f.write("=== DADOS DE CALIBRACAO ===\n")
            f.write(f"Data/Hora: {timestamp}\n")
            f.write("\n")
            
            f.write("PARAMETROS CALIBRADOS:\n")
            f.write(f"a = {calib_params['a']:.6f}\n")
            f.write(f"b = {calib_params['b']:.6f}\n")
            f.write("\n")
            
            f.write("DADOS BRUTOS DE CALIBRACAO:\n")
            for distance, pixels in calib_data.items():
                f.write(f"Distancia {distance}cm: {pixels:.2f} pixels\n")
            f.write("\n")
            
            f.write("FORMULA DE CALCULO:\n")
            f.write("distancia_cm = a / (eye_distance_px - b)\n")
            f.write("\n")
            
            f.write("VALORES DE REFERENCIA:\n")
            f.write(f"W_real = {W_real} cm\n")
            f.write("\n")
            
            f.write("EXEMPLOS:\n")
            f.write(f"150.0 px -> {calib_params['a']/(150.0 - calib_params['b']):.1f} cm\n")
            f.write(f"200.0 px -> {calib_params['a']/(200.0 - calib_params['b']):.1f} cm\n")
            f.write(f"100.0 px -> {calib_params['a']/(100.0 - calib_params['b']):.1f} cm\n")
        
        print(f"Dados de calibracao salvos em: {filename}")
        return filename
        
    except Exception as e:
        print(f"Erro ao salvar arquivo de calibracao: {e}")
        return None

def add_image_overlay(frame, overlay_img, alpha=0.5):
    """
    Adiciona imagem PNG transparente no canto superior direito
    """
    if overlay_img is None:
        return frame
    
    frame_h, frame_w = frame.shape[:2]
    overlay_h, overlay_w = overlay_img.shape[:2]
    
    # Definir posição no canto superior direito
    x_offset = frame_w - overlay_w - 10  # 10px de margem
    y_offset = 10  # 10px do topo
    
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
        # Separar canal alpha
        overlay_rgb = overlay_img[:, :, :3]
        overlay_alpha = overlay_img[:, :, 3] / 255.0
        
        # Região de interesse no frame
        roi = frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w]
        
        # Blend com alpha channel
        for c in range(3):
            roi[:, :, c] = (overlay_alpha * overlay_rgb[:, :, c] + 
                           (1 - overlay_alpha) * roi[:, :, c])
        
        frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w] = roi
    else:
        # Imagem sem alpha - usar blend simples
        roi = frame[y_offset:y_offset+overlay_h, x_offset:x_offset+overlay_w]
        cv2.addWeighted(overlay_img, alpha, roi, 1 - alpha, 0, roi)
    
    return frame

# --- CALIBRAÇÃO MULTI-DISTÂNCIA COM OVAIS VISUAIS ---
def calibrar_multiponto():
    """
    Calibração em duas distâncias conhecidas com ovais visuais
    """
    print("=== CALIBRAÇÃO PRECISA ===")
    print("Siga as ovais na tela e pressione ESPAÇO quando estiver posicionado")
    print("Pressione ESC para cancelar")
    
    calib_data = {}
    
    # Distâncias de calibração com tamanhos de oval correspondentes
    calibration_steps = [
        {'distance': 50, 'oval_size': (120, 160), 'color': (0, 255, 0)},   # Mais longe - oval menor
        {'distance': 30, 'oval_size': (180, 240), 'color': (0, 255, 255)}  # Mais perto - oval maior
    ]
    
    current_step = 0
    
    while current_step < len(calibration_steps):
        step = calibration_steps[current_step]
        target_distance = step['distance']
        oval_size = step['oval_size']
        oval_color = step['color']
        samples = []
        
        while True:
            success, frame = cap.read()
            if not success:
                print("Erro ao capturar frame da câmera")
                continue
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            img_h, img_w = frame.shape[:2]
            
            # Centro da tela
            center = (img_w // 2, img_h // 2)
            
            # Criar máscara para área fora da oval (preta)
            mask = np.zeros_like(frame)
            cv2.ellipse(mask, center, oval_size, 0, 0, 360, (255, 255, 255), -1)
            
            # Aplicar máscara - área fora da oval fica preta
            calib_frame = cv2.bitwise_and(frame, mask)
            
            # Desenhar borda da oval
            cv2.ellipse(calib_frame, center, oval_size, 0, 0, 360, oval_color, 3)
            cv2.ellipse(calib_frame, center, oval_size, 0, 0, 360, (255, 255, 255), 1)
            
            # Desenhar instruções
            cv2.putText(calib_frame, f"POSICIONE-SE A {target_distance}cm", (50, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(calib_frame, "Ajuste seu rosto dentro da oval", (50, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(calib_frame, f"Passo {current_step + 1}/2 - Amostras: {len(samples)}/30", (50, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(calib_frame, "Pressione ESPACO quando estiver pronto", (50, 160),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            positioning_quality = 0
            eye_distance_px = 0
            
            if results.multi_face_landmarks:
                mesh_points = [
                    (int(p.x * img_w), int(p.y * img_h))
                    for p in results.multi_face_landmarks[0].landmark
                ]
                
                # Pontos-chave para verificar posicionamento
                left_eye = mesh_points[33]
                right_eye = mesh_points[263]
                nose_tip = mesh_points[1]
                chin = mesh_points[152]
                forehead = mesh_points[10]
                
                # Calcular distância entre olhos
                eye_distance_px = np.linalg.norm(np.array(left_eye) - np.array(right_eye))
                
                # Verificar qualidade do posicionamento
                points_to_check = [left_eye, right_eye, nose_tip, chin, forehead]
                points_inside = 0
                
                for point in points_to_check:
                    ellipse_value = ((point[0] - center[0]) ** 2 / oval_size[0]**2 + 
                                   (point[1] - center[1]) ** 2 / oval_size[1]**2)
                    if ellipse_value <= 1:
                        points_inside += 1
                
                positioning_quality = points_inside / len(points_to_check)
                
                # Coletar amostras apenas se bem posicionado
                if positioning_quality >= 0.8:  # Pelo menos 80% dos pontos dentro
                    if len(samples) < 30:
                        samples.append(eye_distance_px)
                        cv2.putText(calib_frame, "COLETANDO DADOS...", (50, 200),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    else:
                        cv2.putText(calib_frame, "PRONTO! Pressione ESPACO", (50, 200),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(calib_frame, "AJUSTE SUA POSICAO", (50, 200),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    samples = []  # Reiniciar se saiu da posição
                
                # Mostrar métricas
                cv2.putText(calib_frame, f"Qualidade: {positioning_quality*100:.0f}%", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(calib_frame, f"Dist. olhos: {eye_distance_px:.1f}px", (50, 270),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Feedback visual da oval
            if positioning_quality >= 0.8:
                cv2.ellipse(calib_frame, center, oval_size, 0, 0, 360, (0, 255, 0), 4)  # Verde = pronto
            else:
                cv2.ellipse(calib_frame, center, oval_size, 0, 0, 360, (0, 0, 255), 4)  # Vermelho = ajuste
            
            cv2.imshow('Calibracao', calib_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 32 and len(samples) >= 30 and positioning_quality >= 0.8:  # ESPAÇO + posicionado
                median_px = np.median(samples)
                calib_data[target_distance] = median_px
                print(f"Calibrado {target_distance}cm: {median_px:.2f}px")
                current_step += 1
                time.sleep(1)  # Pequena pausa entre os passos
                break
            elif key == 27:  # ESC
                cv2.destroyWindow('Calibracao')
                return None
    
    cv2.destroyWindow('Calibracao')
    
    # Calcular parâmetros usando regressão
    if len(calib_data) == 2:
        distances_cm = list(calib_data.keys())
        pixels = list(calib_data.values())
        
        # Modelo: distance_cm = a / (eye_pixels - b)
        d1, p1 = distances_cm[0], pixels[0]
        d2, p2 = distances_cm[1], pixels[1]
        
        # Calcular parâmetros a e b
        b = (d2 * p2 - d1 * p1) / (d2 - d1)
        a = d1 * (p1 - b)
        
        print(f"=== CALIBRAÇÃO CONCLUÍDA ===")
        print(f"Parametros: a={a:.2f}, b={b:.2f}")
        print(f"Referência 50cm: {p1:.1f}px")
        print(f"Referência 30cm: {p2:.1f}px")
        
        # SALVAR DADOS DE CALIBRAÇÃO
        calib_params = {'a': a, 'b': b}
        save_calibration_data(calib_params, calib_data)
        
        return calib_params
    else:
        return None

def calculate_distance(eye_distance_px, calib_params):
    """Calcular distância usando modelo calibrado"""
    if eye_distance_px <= calib_params['b']:
        return float('inf')  # Evitar divisão por zero
    return calib_params['a'] / (eye_distance_px - calib_params['b'])

# Inicia MediaPipe FaceMesh
with mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as face_mesh:

    # Calibração multi-ponto
    print("Iniciando calibração...")
    calib_params = calibrar_multiponto()
    
    if calib_params is None:
        print("Calibracao cancelada ou falhou")
        cap.release()
        cv2.destroyAllWindows()
        exit()

    print("Calibração concluída! Iniciando medição em tempo real...")
    print("Pressione ESC para sair")

    # Loop principal
    while True:
        success, frame = cap.read()
        if not success:
            print("Erro ao capturar frame - tentando reconectar...")
            cap.release()
            cap = cv2.VideoCapture(0)
            time.sleep(1)
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        img_h, img_w = frame.shape[:2]

        distance_cm = None

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
            distance_cm = calculate_distance(eye_distance_px, calib_params)

            # Adicionar ao buffer
            buffer.append([frame_number, distance_cm])

            # Mostrar distância no frame
            cv2.putText(frame, f"Distancia: {distance_cm:.1f} cm",
                        (30, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
            cv2.putText(frame, f"Olhos: {eye_distance_px:.1f}px",
                        (30, 70), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 0), 2)

        # Adicionar imagem PNG overlay (após todo o processamento)
        frame = add_image_overlay(frame, overlay_image, overlay_alpha)

        cv2.imshow('Iris tracking', frame)
        frame_number += 1

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("Saindo...")
            break
        if cv2.getWindowProperty('Iris tracking', cv2.WND_PROP_VISIBLE) < 1:
            print("Janela fechada - saindo...")
            break

# Salvar CSV
if buffer:
    with open("distancia_face.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "distance_cm"])
        writer.writerows(buffer)
    print(f"Dados salvos em distancia_face.csv ({len(buffer)} amostras)")

cap.release()
cv2.destroyAllWindows()
print("Programa finalizado")