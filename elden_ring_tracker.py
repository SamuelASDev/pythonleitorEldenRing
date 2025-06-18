import mss
import cv2
import numpy as np
import time
import pytesseract
import tkinter as tk
from tkinter import font

# --- Configurações do Tesseract (obrigatório se o Python não o encontrar automaticamente) ---
# Caminho real para o seu tesseract.exe.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# --- Configurações Essenciais ---
# REGIÃO DE CAPTURA OTIMIZADA!
monitor = {
    "top": 500,
    "left": 600,
    "width": 720,
    "height": 100
}

# Lista de textos que indicam morte.
possible_death_texts = ["VOCE MORREU", "VOCÊ MORREU", "YOU DIED", "YOU DIED!"]

# Cooldown para evitar múltiplas contagens da mesma tela de morte (em segundos)
detection_cooldown = 1.5

# --- Configurações da GUI (Tkinter) ---
gui_location_x = 10
gui_location_y = 10
gui_font_family = "Helvetica"
gui_font_size = 24
gui_font_weight = "bold"
gui_text_color = "red"
gui_background_color = "black"

# --- Inicialização da Captura de Tela ---
sct = mss.mss()

# --- Variáveis Globais para o Contador e Controle de Detecção ---
death_count = 0
is_death_screen_active = False
last_detected_time = 0

# --- Função de Detecção da Tela de Morte (VIA OCR com Seleção de Cor) ---
def detect_death_screen_ocr(current_screen_bgr, target_texts_list):
    # --- CORREÇÃO AQUI: Converta para escala de cinza PRIMEIRO ---
    current_screen_gray = cv2.cvtColor(current_screen_bgr, cv2.COLOR_BGR2GRAY)
    # --- FIM CORREÇÃO ---

    # Converte a imagem BGR para HSV (originalmente estava convertendo aqui e não tinha current_screen_gray definida)
    current_screen_hsv = cv2.cvtColor(current_screen_bgr, cv2.COLOR_BGR2HSV)

    # --- Definir o intervalo de cor vermelha em HSV ---
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 100, 100])
    upper_red2 = np.array([179, 255, 255])

    mask1 = cv2.inRange(current_screen_hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(current_screen_hsv, lower_red2, upper_red2)
    red_mask = mask1 + mask2

    # Aplica a máscara para isolar os pixels vermelhos.
    # img_for_ocr agora usa current_screen_gray que está definida.
    img_for_ocr = cv2.bitwise_and(current_screen_gray, current_screen_gray, mask=red_mask)
    
    # Opcional: Para binarizar ainda mais a imagem para o Tesseract,
    _, img_for_ocr = cv2.threshold(img_for_ocr, 30, 255, cv2.THRESH_BINARY)

    try:
        text_extracted = pytesseract.image_to_string(img_for_ocr, lang='por+eng', config='--psm 6 --oem 3')
        processed_extracted_text = text_extracted.strip().upper().replace('\n', ' ').replace(' ', '')
        
        for death_word_phrase in target_texts_list:
            processed_target = death_word_phrase.strip().upper().replace(' ', '')
            if processed_target in processed_extracted_text:
                return True, text_extracted

        return False, text_extracted

    except pytesseract.TesseractNotFoundError:
        print("Erro: Tesseract OCR não encontrado. Verifique se o caminho em pytesseract.pytesseract.tesseract_cmd está correto.")
        return False, ""
    except Exception as e:
        print(f"Erro no OCR: {e}")
        return False, ""

# --- Funções para a GUI do Tkinter ---

def on_key_press(event):
    if event.char == 'q':
        root.destroy()

def update_counter_and_detect():
    global death_count, is_death_screen_active, last_detected_time

    sct_img = sct.grab(monitor)
    img_np = np.array(sct_img)

    if img_np.shape[2] == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

    # --- DEBUG VISUAL: Mostra a imagem que está sendo capturada ---
    cv2.imshow("Regiao de Captura (DEBUG)", img_np)
    
    # Descomente para ver a imagem APÓS o pré-processamento de cor para o OCR
    # current_screen_hsv = cv2.cvtColor(img_np, cv2.COLOR_BGR2HSV)
    # lower_red1 = np.array([0, 100, 100])
    # upper_red1 = np.array([10, 255, 255])
    # lower_red2 = np.array([170, 100, 100])
    # upper_red2 = np.array([179, 255, 255])
    # mask1 = cv2.inRange(current_screen_hsv, lower_red1, upper_red1)
    # mask2 = cv2.inRange(current_screen_hsv, lower_red2, upper_red2)
    # red_mask = mask1 + mask2
    # processed_for_display = cv2.bitwise_and(cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY), cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY), mask=red_mask)
    # _, processed_for_display = cv2.threshold(processed_for_display, 30, 255, cv2.THRESH_BINARY)
    # cv2.imshow("Imagem para OCR apos cor (DEBUG)", processed_for_display)

    cv2.waitKey(1)
    # --- FIM DEBUG VISUAL ---

    detected, ocr_text_raw = detect_death_screen_ocr(img_np, possible_death_texts)

    current_time = time.time()
    if detected and not is_death_screen_active and (current_time - last_detected_time > detection_cooldown):
        death_count += 1
        is_death_screen_active = True
        last_detected_time = current_time
        
        print(f"!!! TELA DE MORTE DETECTADA VIA OCR !!! Mortes: {death_count} (Texto Lido: '{ocr_text_raw.strip()}')")
        counter_label.config(text=f"Mortes: {death_count}")
        
    elif not detected and is_death_screen_active:
        is_death_screen_active = False

    root.after(33, update_counter_and_detect)


# --- Configuração Principal do Tkinter ---
root = tk.Tk()
root.title("Elden Ring Death Counter")

root.overrideredirect(True)
root.wm_attributes("-topmost", True)
root.wm_attributes("-alpha", 0.8)
root.attributes("-transparentcolor", gui_background_color)
root.geometry(f"+{gui_location_x}+{gui_location_y}")

custom_font = font.Font(family=gui_font_family, size=gui_font_size, weight=gui_font_weight)

counter_label = tk.Label(
    root,
    text=f"Mortes: {death_count}",
    font=custom_font,
    fg=gui_text_color,
    bg=gui_background_color,
    highlightthickness=0
)
counter_label.pack(padx=5, pady=5)

button_font = font.Font(family=gui_font_family, size=10, weight="normal")

exit_button = tk.Button(
    root,
    text="Sair",
    command=root.destroy,
    font=button_font,
    fg="white",
    bg="darkgray",
    relief="flat"
)
exit_button.pack(pady=2, padx=5)

root.bind('<Key>', on_key_press)

print(f"Monitorando a região OTIMIZADA: {monitor['left']},{monitor['top']} até {monitor['left']+monitor['width']},{monitor['top']+monitor['height']}")
print(f"Pressione 'q' (com o foco na janela do contador) ou clique em 'Sair' para encerrar. Monitorando a tela para os textos de morte...")

root.after(100, update_counter_and_detect)

try:
    root.mainloop()
except Exception as e:
    print(f"Ocorreu um erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    cv2.destroyAllWindows()
    print("Programa finalizado.")
    print(f"Total de mortes detectadas: {death_count}")