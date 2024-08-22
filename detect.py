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
    if isinstance(url, tuple):
        url = url[1]  # URL이 튜플인 경우 두 번째 요소를 사용

    response = requests.get(url)
    response.raise_for_status()
    return np.array(bytearray(response.content), dtype=np.uint8)

def detect_faces(image, cascade_file):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cascade_file)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return faces

def process_urls(data, output_dir, cascade_file):
    if isinstance(data, dict) and '_id' in data and 'thumbnail' in data and 'description_urls' in data and 'product_urls' in data:
        image_id = data['_id']
        urls = []
        urls.append(('thumbnail', data['thumbnail']))
        urls.extend(('description', desc) for desc in data['description_urls'])
        urls.extend(('product', prod) for prod in data['product_urls'])
        
        thumbnail_count = 0
        product_count = 0
        description_count = 0

        for img_type, url in urls:
            try:
                image_data = download_image(url)
                image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
                
                if image is None:
                    print(f"이미지를 로드할 수 없습니다: {url}")
                    continue
                
                original_name = os.path.basename(urlparse(url).path)
                original_name_no_ext = os.path.splitext(original_name)[0]

                if img_type == 'description':
                    width, height = image.shape[1], image.shape[0]
                    
                    if height > 8192:
                        total_parts = (height // 8192) + (1 if height % 8192 > 0 else 0)
                        for d in range(total_parts):
                            part_height = min(8192, height - d * 8192)
                            crop_part = image[d * 8192: d * 8192 + part_height, :]
                            webp_file_name_desc = f"{output_dir}/{original_name_no_ext}-w{width}-h{height}-d{d+1}-{total_parts}"
                            cv2.imwrite(webp_file_name_desc + ".webp", crop_part)
                            print(f"변환 완료: {webp_file_name_desc}.webp")
                    else:
                        webp_file_name_desc = f"{output_dir}/{original_name_no_ext}-w{width}-h{height}"
                        cv2.imwrite(webp_file_name_desc + ".webp", image)
                        print(f"변환 완료: {webp_file_name_desc}.webp")
                    continue
                
                if img_type == 'thumbnail':
                    faces = detect_faces(image, cascade_file)
                    
                    print(f"인식된 얼굴 수: {len(faces)}")
                    
                    if len(faces) > 0:
                        min_x = min(face[0] for face in faces)
                        min_y = min(face[1] for face in faces)
                        max_x = max(face[0] + face[2] for face in faces)
                        max_y = max(face[1] + face[3] for face in faces)
                        center_x = (min_x + max_x) // 2
                        center_y = (min_y + max_y) // 2

                        height, width = image.shape[:2]
                        if width / height > 3 / 4:
                            new_height = height
                            new_width = int(new_height * 3 / 4)
                        else:
                            new_width = width
                            new_height = int(new_width * 4 / 3)

                        left = max(center_x - new_width // 2, 0)
                        top = max(center_y - new_height // 2, 0)
                        right = min(left + new_width, width)
                        bottom = min(top + new_height, height)

                        if right == width:
                            left = max(width - new_width, 0)
                        if bottom == height:
                            top = max(height - new_height, 0)

                        crop_3_4 = image[top:bottom, left:right]

                        webp_file_name_thumb = f"{output_dir}/{original_name_no_ext}"
                        cv2.imwrite(webp_file_name_thumb + ".webp", crop_3_4)
                        print(f"변환 완료: {webp_file_name_thumb}.webp")
                    else:
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
                    
                    continue
                
                if img_type == 'product':
                    faces = detect_faces(image, cascade_file)
                    
                    valid_faces = []
                    image_area = image.shape[0] * image.shape[1]
                    for face in faces:
                        x, y, w, h = face
                        face_area = w * h
                        if face_area >= image_area / 100:
                            valid_faces.append(face)
                    
                    if len(valid_faces) > 0:
                        largest_face = max(valid_faces, key=lambda face: face[2] * face[3])
                        x, y, w, h = largest_face
                        center_x, center_y = x + w // 2, y + h // 2

                        # 얼굴만 크롭 (1:1 비율)
                        face_size = max(w, h)
                        left = max(x - (face_size - w) // 2, 0)
                        top = max(y - (face_size - h) // 2, 0)
                        right = min(left + face_size, image.shape[1])
                        bottom = min(top + face_size, image.shape[0])

                        crop_1_1_face = image[top:bottom, left:right]

                        webp_file_name_1_1_face = f"{output_dir}/{original_name_no_ext}"
                        cv2.imwrite(webp_file_name_1_1_face + ".webp", crop_1_1_face)
                        print(f"변환 완료: {webp_file_name_1_1_face}.webp")

                        # 넓은 영역 크롭 (1:1 비율) - 기존 -t 이미지
                        height, width = image.shape[:2]
                        side_length = min(width, height)
                        left = max(0, center_x - side_length // 2)
                        top = max(0, center_y - side_length // 2)
                        right = min(width, left + side_length)
                        bottom = min(height, top + side_length)

                        if right - left < side_length:
                            left = max(0, right - side_length)
                        if bottom - top < side_length:
                            top = max(0, bottom - side_length)

                        crop_1_1_wide = image[top:bottom, left:right]

                        webp_file_name_1_1_wide = f"{output_dir}/{original_name_no_ext}-t"
                        cv2.imwrite(webp_file_name_1_1_wide + ".webp", crop_1_1_wide)
                        print(f"변환 완료: {webp_file_name_1_1_wide}.webp")
                    else:
                        print(f"상품 이미지에서 유효한 얼굴 인식 실패 {url}. 위에 1/3 지점 편집.")
                        
                        height, width = image.shape[:2]
                        side_length = min(height, width)
                        center_x = width // 2
                        center_y = height // 3
                        
                        # 상단 1/3 지점 크롭 (1:1 비율)
                        left = max(0, center_x - side_length // 2)
                        top = max(0, center_y - side_length // 2)
                        right = min(width, left + side_length)
                        bottom = min(height, top + side_length)
                        
                        crop_upper_third = image[top:bottom, left:right]
                        if crop_upper_third is not None and crop_upper_third.size > 0:
                            webp_file_name_1_1 = f"{output_dir}/{original_name_no_ext}"
                            cv2.imwrite(webp_file_name_1_1 + ".webp", crop_upper_third)
                            print(f"변환 완료: {webp_file_name_1_1}.webp")
                        
                        # 약간 확대된 영역 크롭 (1:1 비율) - 기존 -t 이미지
                        enlarged_side_length = int(side_length * 1.2)
                        left = max(0, center_x - enlarged_side_length // 2)
                        top = max(0, center_y - enlarged_side_length // 2)
                        right = min(width, left + enlarged_side_length)
                        bottom = min(height, top + enlarged_side_length)
                        
                        crop_upper_third_enlarged = image[top:bottom, left:right]
                        if crop_upper_third_enlarged is not None:
                            webp_file_name_1_1_enlarged = f"{output_dir}/{original_name_no_ext}-t"
                            cv2.imwrite(webp_file_name_1_1_enlarged + ".webp", crop_upper_third_enlarged)
                            print(f"변환 완료: {webp_file_name_1_1_enlarged}.webp")
                    
                    continue
                
                print(f"Processed {url}: Found {len(faces)} faces")
                
                if img_type == 'thumbnail':
                    thumbnail_count += 1
                    if thumbnail_count == 1:
                        print("모든 섬네일 이미지 처리 완료.")
                elif img_type == 'description':
                    description_count += 1
                    if description_count == len(data['description_urls']):
                        print("모든 설명 이미지 처리 완료.")
                elif img_type == 'product':
                    product_count += 1
                    if product_count == len(data['product_urls']):
                        print("모든 상품 이미지 처리 완료.")

            except requests.RequestException as e:
                print(f"오류 발생: {str(e)}")
                continue
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {str(e)}")
                continue

        print(f"모든 섬네일 이미지 처리 완료: {thumbnail_count}개")
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
                crop_3_4 = crop_face(image, face, '3:4')
                cv2.imwrite(str(output_dir / f"face_{i}_{j}_3_4.jpg"), crop_3_4)
                
                crop_1_1 = crop_face(image, face, '1:1')
                cv2.imwrite(str(output_dir / f"face_{i}_{j}_1_1.jpg"), crop_1_1)
            
            total_processing_time += time.time() - start_processing
            
            print(f"Processed {url}: Found {len(faces)} faces")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

    total_time = time.time() - start_time
    other_time = total_time - (total_download_time + total_processing_time)

    log_file = output_dir / "processing_time.txt"
    with open(log_file, "w") as f:
        f.write(f"파일 다운로드 시간 (네트워크 지연): {total_download_time:.2f} 초\n")
        f.write(f"이미지 처리 시간: {total_processing_time:.2f} 초\n")
        f.write(f"타 처리 간 (라이브러리 로딩 등): {other_time:.2f} 초\n")
        f.write(f"총 처리 시간: {total_time:.2f} 초\n")

def receive_sqs_messages(queue_url):
    sqs = boto3.client('sqs')
    error_occurred = False

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10
            )
            
            messages = response.get('Messages', [])
            if not messages:
                print("메시지가 없습니다. 시 후 다시 시도합니다.")
                continue
            
            for message in messages:
                body = json.loads(message['Body'])
                # print("원본 메시지:", body)  # 이 줄을 주석 처��하거나 제거합니다.
                
                output_dir = 'output_directory'
                cascade_file = 'lbpcascade_animeface.xml'
                
                process_urls(body, output_dir, cascade_file)
                
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                
            error_occurred = False

        except Exception as e:
            if not error_occurred:
                print(f"오류 발생: {str(e)}")
                error_occurred = True

queue_url = 'queue_url'
receive_sqs_messages(queue_url)

def crop_face(image, face, ratio):
    x, y, w, h = face
    center_x, center_y = x + w // 2, y + h // 2

    height, width = image.shape[:2]
    
    if ratio == '1:1':
        new_size = min(w, h)
        left = max(center_x - new_size // 2, 0)
        top = max(center_y - new_size // 2, 0)
        right = min(left + new_size, width)
        bottom = min(top + new_size, height)
    elif ratio == '3:4':
        new_width = w
        new_height = int(new_width * 4 / 3)
        left = max(center_x - new_width // 2, 0)
        top = max(center_y - new_height // 2, 0)
        right = min(left + new_width, width)
        bottom = min(top + new_height, height)
    else:
        raise ValueError("지원되지 않는 비율입니다. '1:1' 또는 '3:4'를 사용하세요.")

    if right == width:
        left = max(width - (right - left), 0)
    if bottom == height:
        top = max(height - (bottom - top), 0)

    crop = image[top:bottom, left:right]
    return crop

def get_unique_filename(base_path):
    counter = 1
    file_path = f"{base_path}.webp"
    while os.path.exists(file_path):
        file_path = f"{base_path}_{counter}.webp"
        counter += 1
    return file_path

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, '')
    output_dir = "output_faces"
    cascade_file = "lbpcascade_animeface.xml"
    process_urls(input_file, output_dir, cascade_file)
