import cv2
import numpy as np
import requests
from urllib.parse import urlparse
from pathlib import Path
import time
import json
from PIL import Image
from io import BytesIO
import os

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
        else:  # 이미지가 3:4보 가로로 길 경우
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
        data = json.load(f)  # JSON 데이터 로드
        
        print(data)  # JSON 구조 출력 (디버깅용)
        
        if isinstance(data, dict) and '_id' in data and 'images' in data and isinstance(data['images'], dict):
            image_id = data['_id']  # _id 값 저장
            urls = []
            # thumbnail, description, product URL 추가
            urls.append(('thumbnail', data['images']['thumbnail']))
            urls.extend(('description', desc) for desc in data['images']['description'])
            urls.extend(('product', prod) for prod in data['images']['product'])
            
            thumbnail_count = 0
            product_count = 0
            description_count = 0

            for img_type, url in urls:
                # 이미지 다운로드
                response = requests.get(url)
                image_data = np.array(bytearray(response.content), dtype=np.uint8)
                image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
                original_name = os.path.basename(urlparse(url).path)  # 원래 파일 이름 추출
                
                if img_type == 'description':
                    # 얼굴 감지 생략
                    width, height = image.shape[1], image.shape[0]
                    
                    if height > 8192:  # 세로가 8192px 이상일 때
                        total_parts = (height // 8192) + (1 if height % 8192 > 0 else 0)
                        for d in range(total_parts):
                            part_height = min(8192, height - d * 8192)
                            crop_part = image[d * 8192: d * 8192 + part_height, :]
                            webp_file_name_desc = f"{output_dir}/{original_name}-w{width}-h{height}-d{d+1}-{total_parts}.webp"
                            cv2.imwrite(webp_file_name_desc, crop_part)  # 분할된 이미지 저장
                            print(f"변환 완료: {webp_file_name_desc}")  # 저장 완료 메시지 출력
                    else:
                        webp_file_name_desc = f"{output_dir}/{original_name}-w{width}-h{height}.webp"
                        cv2.imwrite(webp_file_name_desc, image)  # 설명 이미지 저장
                        print(f"변환 완료: {webp_file_name_desc}")  # 저장 완료 메시지 출력
                    continue  # 다음 이미지로 넘어감
                
                faces = detect_faces(image, cascade_file)
                
                if len(faces) == 0:
                    # 얼굴 인식 실패 시 중앙 기준으로 자르기
                    print(f"얼굴 인식 실패 {url}. 중앙 편집.")
                    crop_3_4 = crop_face(image, (0, 0, image.shape[1], image.shape[0]), '3:4')  # 전체 이미지 자르기
                    webp_file_name_3_4 = f"{output_dir}/{original_name}_3_4.webp"  # 파일 이름 수정
                    cv2.imwrite(webp_file_name_3_4, crop_3_4)  # 크기 조정 후 저장
                    print(f"변환 완료: {webp_file_name_3_4}")  # 저장 완료 메시지 출력
                    
                    crop_1_1 = crop_face(image, (0, 0, image.shape[1], image.shape[0]), '1:1')  # 전체 이미지 자르기
                    webp_file_name_1_1 = f"{output_dir}/{original_name}_1_1.webp"  # 파일 이름 수정
                    cv2.imwrite(webp_file_name_1_1, crop_1_1)  # 크기 조정 후 저장
                    print(f"변환 완료: {webp_file_name_1_1}")  # 저장 완료 메시지 출력
                    
                    # 이미지 분할 처리
                    if (image.shape[1] + image.shape[0]) > 8192:  # 가로세로 합이 8192px 이상일 때
                        height, width = image.shape[:2]
                        total_parts = (height // 8192) + (width // 8192) + 1
                        for d in range(total_parts):
                            # 분할 로직 구현
                            part_height = min(8192, height - d * 8192)
                            part_width = min(8192, width - d * 8192)
                            crop_part = image[d * 8192: d * 8192 + part_height, d * 8192: d * 8192 + part_width]
                            webp_file_name_face = f"{output_dir}/{original_name}_3_4-d{d+1}-{total_parts}.webp"
                            cv2.imwrite(webp_file_name_face, crop_part)  # 분할된 이미지 저장
                            print(f"변환 완료: {webp_file_name_face}")  # 저장 완료 메시지 출력
                
                else:
                    for j, face in enumerate(faces):
                        # 3:4 비율로 자르기
                        crop_3_4 = crop_face(image, face, '3:4')
                        webp_file_name_3_4 = f"{output_dir}/{original_name}-3_4.webp"  # 원래 이름 기반으로 수정
                        cv2.imwrite(webp_file_name_3_4, crop_3_4)  # 크기 조정 후 저장
                        print(f"변환 완료: {webp_file_name_3_4}")  # 저장 완료 메시지 출력
                        
                        # 1:1 비율로 자르기
                        crop_1_1 = crop_face(image, face, '1:1')
                        webp_file_name_1_1 = f"{output_dir}/{original_name}-1_1.webp"  # 원래 이름 기반으로 수정
                        cv2.imwrite(webp_file_name_1_1, crop_1_1)  # 크기 조정 후 저장
                        print(f"변환 완료: {webp_file_name_1_1}")  # 저장 완료 메시지 출력
                        
                        # 이미지 분할 처리
                        if (image.shape[1] + image.shape[0]) > 8192:  # 가로세로 합이 8192px 이상일 때
                            height, width = image.shape[:2]
                            total_parts = (height // 8192) + (width // 8192) + 1
                            for d in range(total_parts):
                                # 분할 로직 구현
                                part_height = min(8192, height - d * 8192)
                                part_width = min(8192, width - d * 8192)
                                crop_part = image[d * 8192: d * 8192 + part_height, d * 8192: d * 8192 + part_width]
                                webp_file_name_face = f"{output_dir}/{original_name}_3_4-d{d+1}-{total_parts}.webp"
                                cv2.imwrite(webp_file_name_face, crop_part)  # 분할된 이미지 저장
                                print(f"변환 완료: {webp_file_name_face}")  # 저장 완료 메시지 출력
                
                print(f"Processed {url}: Found {len(faces)} faces")
                
                if img_type == 'thumbnail':
                    thumbnail_count += 1
                    # 섭네일 처리 완료 알림
                    if thumbnail_count == 1:  # 섭네일이 하나이므로 1로 설정
                        print("모든 섭네일 이미지 처리 완료.")
                elif img_type == 'description':
                    description_count += 1
                    # 설명 이미지 처리 완료 알림
                    
                    if description_count == len(data['images']['description']):  # 모든 설명 처리 후
                        print("모든 설명 이미지 처리 완료.")
                elif img_type == 'product':
                    product_count += 1
                    # 상품 이미지 처리 완료 알림
                    
                    if product_count == len(data['images']['product']):  # 모든 상품 처리 후
                        print("모든 상품 이미지 처리 완료.")

            # 모든 이미지 처리 후 알림 출력
            print(f"모든 섭네일 이미지 처리 완료: {thumbnail_count}개")
            print(f"모든 상품 이미지 처리 완료: {product_count}개")
            print(f"모든 설명 이미지 처리 완료: {description_count}개")
        else:
            raise ValueError("Invalid JSON structure: 'images' should be a dictionary.")
    
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
    # 현재 스크립트의 디렉토 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, 'source.json')  # 상대 경로로 수정
    output_dir = "output_faces"
    cascade_file = "lbpcascade_animeface.xml"
    process_urls(input_file, output_dir, cascade_file)