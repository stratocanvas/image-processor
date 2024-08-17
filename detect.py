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
import boto3

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
    
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    return faces

def crop_face(image, face, ratio):
    img_h, img_w = image.shape[:2]
    x, y, w, h = face
    center_x, center_y = x + w // 2, y + h // 2

    new_w, new_h = 0, 0  # 초기화

    if ratio == '4:3':
        new_h = h  # 얼굴 높이를 기준으로
        new_w = int(new_h * 4 / 3)
    
    elif ratio == '1:1':
        new_h = new_w = min(h, w)

    # 크롭 영역 계산
    left = max(center_x - new_w // 2, 0)
    top = max(center_y - new_h // 2, 0)
    right = min(left + new_w, img_w)
    bottom = min(top + new_h, img_h)

    # 크롭 영역이 유효한지 확인
    if right <= left or bottom <= top:
        print("크롭 영��이 유효하지 않습니다.")
        return None  # 빈 이미지 반환

    return image[top:bottom, left:right]

def process_urls(urls, output_dir, cascade_file):
    thumbnail_count = 0
    product_count = 0
    description_count = 0

    for url in urls:
        try:
            # 이미지 다운로드
            response = requests.get(url)
            response.raise_for_status()
            image_data = np.array(bytearray(response.content), dtype=np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            
            if image is None:
                print(f"이미지를 로드할 수 없습니다: {url}")
                continue
            
            original_name = os.path.basename(urlparse(url).path)  # 원래 파일 이름 추출
            original_name_no_ext = os.path.splitext(original_name)[0]  # 확장자 제거

            # 얼굴 감지
            faces = detect_faces(image, cascade_file)
            
            # 인식된 얼굴 수 출력
            print(f"인식된 얼굴 수: {len(faces)}")
            
            if len(faces) > 0:
                # 모든 얼굴을 포함하는 영역 계산
                min_x = min(face[0] for face in faces)
                min_y = min(face[1] for face in faces)
                max_x = max(face[0] + face[2] for face in faces)
                max_y = max(face[1] + face[3] for face in faces)
                # 영역의 중심점 계산
                center_x = (min_x + max_x) // 2
                center_y = (min_y + max_y) // 2

                # 3:4 비율로 크롭할 영역 계산
                height, width = image.shape[:2]
                if width / height > 3 / 4:
                    new_height = height
                    new_width = int(new_height * 3 / 4)
                else:
                    new_width = width
                    new_height = int(new_width * 4 / 3)

                # 크롭 영역 계산 (얼굴 중심으로)
                left = max(center_x - new_width // 2, 0)
                top = max(center_y - new_height // 2, 0)
                right = min(left + new_width, width)
                bottom = min(top + new_height, height)

                # 이미지 경계를 벗어나지 않도록 조정
                if right == width:
                    left = max(width - new_width, 0)
                if bottom == height:
                    top = max(height - new_height, 0)

                # 크롭
                crop_3_4 = image[top:bottom, left:right]

                # 저장
                webp_file_name_thumb = f"{output_dir}/{original_name_no_ext}"
                cv2.imwrite(webp_file_name_thumb + ".webp", crop_3_4)
                print(f"변환 완료: {webp_file_name_thumb}.webp")
            else:
                # 얼굴 인식 실패 시 중앙 기준으로 3:4 비율로 자르기
                print(f"얼굴 인식 실패 {url}. 중앙 편집.")
                height, width = image.shape[:2]
                if width / height > 3 / 4:
                    new_height = height
                    new_width = int(new_height * 3 / 4)
                else:
                    new_width = width
                    new_height = int(new_width * 4 / 3)

                left = (width - new_width) // 2
                top = (height - new_height) // 2
                crop_center = image[top:top+new_height, left:left+new_width]
                
                webp_file_name_thumb = f"{output_dir}/{original_name_no_ext}"
                cv2.imwrite(webp_file_name_thumb + ".webp", crop_center)
                print(f"변환 완료: {webp_file_name_thumb}.webp")
            
            print(f"Processed {url}: Found {len(faces)} faces")
            
            thumbnail_count += 1
            # 섭네일 처리 완료 알림
            if thumbnail_count == 1:  # 섭네일이 하나이므로 1로 설정
                print("모든 섭네일 이미지 처리 완료.")

        except requests.RequestException as e:
            print(f"Error downloading {url}: {str(e)}")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

    # 모든 이미지 처리 후 알림 출력
    print(f"모든 섭네일 이미지 처리 완료: {thumbnail_count}개")

def get_urls_from_sqs(queue_url):
    sqs = boto3.client('sqs')
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=10
    )
    
    urls = []
    if 'Messages' in response:
        for message in response['Messages']:
            body = json.loads(message['Body'])
            urls.append(body['url'])  # 메시지에서 URL 추출
            # 메시지 삭제 (선택 사항)
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
    return urls

if __name__ == "__main__":
    # SQS 큐 URL
    queue_url = 'YOUR_SQS_QUEUE_URL'  # 여기에 SQS 큐 URL을 입력하세요
    urls = get_urls_from_sqs(queue_url)
    
    output_dir = "output_faces"
    cascade_file = "lbpcascade_animeface.xml"
    process_urls(urls, output_dir, cascade_file)