import json
import time
import os
import requests
from PIL import Image
import io
import logging
import gc
import face_recognition
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

output_dir = "output_faces"

def update_status(item_id, status):
    logging.info(f"상태 업데이트: {item_id} - {status}")

def detect_and_crop_face(image):
    # PIL Image를 numpy array로 변환
    np_image = np.array(image)

    # RGB to BGR 변환 (face_recognition은 BGR 형식을 사용)
    np_image = np_image[:, :, ::-1]

    # 얼굴 위치 찾기
    face_locations = face_recognition.face_locations(np_image)

    if len(face_locations) == 0:
        logging.warning(f"{image}에서 얼굴을 찾을 수 없습니다.")
        return image  # 원본 이미지를 반환

    # 첫 번째 얼굴만 사용
    top, right, bottom, left = face_locations[0]

    # 얼굴 주변의 여유 공간 계산 (20% 추가)
    height, width = np_image.shape[:2]
    margin_y = int((bottom - top) * 0.2)
    margin_x = int((right - left) * 0.2)

    # 크롭 영역 계산
    crop_top = max(top - margin_y, 0)
    crop_bottom = min(bottom + margin_y, height)
    crop_left = max(left - margin_x, 0)
    crop_right = min(right + margin_x, width)

    # 이미지 크롭
    cropped_image = np_image[crop_top:crop_bottom, crop_left:crop_right]

    # BGR to RGB 변환 및 PIL Image로 변환
    cropped_image = Image.fromarray(cropped_image[:, :, ::-1])

    return cropped_image

def process_image(image_url, item_id, image_type):
    logging.info(f"이미지 처리 시작: {item_id}_{image_type}")
    
    try:
        # 이미지 다운로드 및 열기
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        
        logging.info(f"원본 이미지 모드: {img.mode}")
        
        # 얼굴 감지 및 크롭
        cropped_img = detect_and_crop_face(img)
        
        # ���력 디렉토리 확인 및 생성
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # WEBP 형식으로 저장
        output_filename = f"{item_id}_{image_type}.webp"
        output_path = os.path.join(output_dir, output_filename)
        
        # WEBP로 저장 (품질 설정 가능, 0-100)
        cropped_img.save(output_path, 'WEBP', quality=90)
        
        logging.info(f"이미지 저장됨: {output_path} (모드: {cropped_img.mode})")
        update_status(item_id, f"{image_type}_완료")
    except requests.RequestException as e:
        logging.error(f"이미지 다운로드 오류: {e}")
    except Image.UnidentifiedImageError:
        logging.error(f"이미지를 식별할 수 없음: {image_url}")
    except Exception as e:
        logging.error(f"이미지 처리 중 예상치 못한 오류 발생: {e}")
    finally:
        if 'img' in locals():
            img.close()
        gc.collect()
        logging.info(f"{item_id}_{image_type} 처리 완료")

def process_message(data):
    item_id = data['_id']
    images = data['images']
    
    # 썸네일 이미지 처리
    if 'thumbnail' in images:
        process_image(images['thumbnail'], item_id, '썸네일')
    
    # 설명 이미지 처리
    for i, img_url in enumerate(images.get('description', []), 1):
        process_image(img_url, item_id, f'설명_{i}')
        logging.info(f"설명 이미지 {i} 처리 완료")
    update_status(item_id, '설명_모두_완료')
    
    # 제품 이미지 처리
    for i, img_url in enumerate(images.get('product', []), 1):
        process_image(img_url, item_id, f'제품_{i}')
        logging.info(f"제품 이미지 {i} 처리 완료")
    update_status(item_id, '제품_모두_완료')
    
    # 워터마크 이미지 처리 (필요한 경우)
    if 'watermark' in images:
        process_image(images['watermark'], item_id, '워터마크')
    
    # 모든 처리 완료
    update_status(item_id, '모든_처리_완료')

def main():
    # JSON 파일에서 테스트 데이터 읽기
    with open('test_data.json', 'r') as file:
        test_data = json.load(file)
    
    # 테스트 데이터 처리
    process_message(test_data)

if __name__ == "__main__":
    main()