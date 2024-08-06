import cv2
import numpy as np
import requests
from urllib.parse import urlparse
from pathlib import Path
import time

def download_image(url):
    start_time = time.time()
    response = requests.get(url)
    response.raise_for_status()
    download_time = time.time() - start_time
    return np.array(bytearray(response.content), dtype=np.uint8), download_time

def detect_faces(image, cascade_file):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cascade_file)
    if face_cascade.empty():
        raise IOError('Unable to load the face cascade classifier xml file')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return faces

def crop_face(image, face, ratio):
    img_h, img_w = image.shape[:2]
    x, y, w, h = face
    center_x, center_y = x + w // 2, y + h // 2

    if ratio == '3:4':
        if img_w / img_h > 3 / 4:  # 이미지가 3:4보다 가로로 길 경우
            new_h = img_h
            new_w = int(new_h * 3 / 4)
        else:  # 이미지가 3:4보다 세로로 길 경우
            new_w = img_w
            new_h = int(new_w * 4 / 3)
    elif ratio == '1:1':
        new_h = new_w = min(img_h, img_w)
    
    left = max(center_x - new_w // 2, 0)
    top = max(center_y - new_h // 2, 0)
    right = min(left + new_w, img_w)
    bottom = min(top + new_h, img_h)
    
    # 이미지 경계를 벗어나지 않도록 조정
    if right - left < new_w:
        left = max(right - new_w, 0)
    if bottom - top < new_h:
        top = max(bottom - new_h, 0)
    
    return image[top:bottom, left:right]

def process_urls(input_file, output_dir, cascade_file):
    with open(input_file, 'r') as f:
        urls = f.read().splitlines()
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_download_time = 0
    total_processing_time = 0
    start_time = time.time()

    for i, url in enumerate(urls):
        try:
            image_data, download_time = download_image(url)
            total_download_time += download_time

            start_processing = time.time()
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            faces = detect_faces(image, cascade_file)
            
            for j, face in enumerate(faces):
                # 3:4 ratio crop
                crop_3_4 = crop_face(image, face, '3:4')
                cv2.imwrite(str(output_dir / f"face_{i}_{j}_3_4.jpg"), crop_3_4)
                
                # 1:1 ratio crop
                crop_1_1 = crop_face(image, face, '1:1')
                cv2.imwrite(str(output_dir / f"face_{i}_{j}_1_1.jpg"), crop_1_1)
            
            total_processing_time += time.time() - start_processing
            
            print(f"Processed {url}: Found {len(faces)} faces")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

    total_time = time.time() - start_time
    other_time = total_time - (total_download_time + total_processing_time)

    # 결과를 텍스트 파일에 저장
    log_file = output_dir / "processing_time.txt"
    with open(log_file, "w") as f:
        f.write(f"파일 다운로드 시간 (네트워크 지연): {total_download_time:.2f} 초\n")
        f.write(f"이미지 처리 시간: {total_processing_time:.2f} 초\n")
        f.write(f"기타 처리 시간 (라이브러리 로딩 등): {other_time:.2f} 초\n")
        f.write(f"총 처리 시간: {total_time:.2f} 초\n")

if __name__ == "__main__":
    input_file = "source.txt"
    output_dir = "output_faces"
    cascade_file = "lbpcascade_animeface.xml"
    process_urls(input_file, output_dir, cascade_file)