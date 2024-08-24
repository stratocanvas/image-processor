import cv2
import numpy as np
import boto3
from urllib.parse import urlparse
from pathlib import Path
import time
import json
from io import BytesIO
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import gc

s3_client = boto3.client('s3')

# AWS S3에서 이미지 다운로드
# URL 대신 S3 SDK 사용
def download_image_from_s3(bucket, key):
    start_time = time.time()
    response = s3_client.get_object(Bucket=bucket, Key=key)
    image_data = np.frombuffer(response['Body'].read(), dtype=np.uint8)
    download_time = time.time() - start_time
    return image_data, download_time, f"s3://{bucket}/{key}"

# 캐릭터 얼굴 감지
def detect_faces(image, cascade_file):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cascade_file)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return faces

# WEBP 변환
def save_as_webp(image, file_path, quality=80):
    cv2.imwrite(file_path, image, [cv2.IMWRITE_WEBP_QUALITY, quality])

# 인포 이미지 처리
def process_description_image(image, output_dir, original_name_no_ext):
    height, width = image.shape[:2]
    if height > 8192: # 세로 8192px 초과하는 이미지에 대해
        total_parts = (height // 8192) + (1 if height % 8192 > 0 else 0)
        webp_file_names = []
        for d in range(total_parts):
            part_height = min(8192, height - d * 8192)
            crop_part = image[d * 8192: d * 8192 + part_height, :] # 8192픽셀씩 쪼갬
            webp_file_name = f"{output_dir}/{original_name_no_ext}-w({width})-h({height})-d({d+1}-{total_parts}).webp" # 파일명에 w, h, 분할수 포함
            save_as_webp(crop_part, webp_file_name) # WEBP 저장
            webp_file_names.append(webp_file_name)
            del crop_part # GC  
        return webp_file_names
    else: # 8192픽셀 이하 이미지에 대해
        webp_file_name = f"{output_dir}/{original_name_no_ext}-w({width})-h({height}).webp" # 파일명에 w, h 포함
        save_as_webp(image, webp_file_name) # WEBP 저장
        return [webp_file_name]

# 현수막 이미지
def process_thumbnail_image(image, output_dir, original_name_no_ext, cascade_file):
    faces = detect_faces(image, cascade_file) # 얼굴 감지
    height, width = image.shape[:2]
    if len(faces) > 0: # 얼굴이 감지된 경우
        x, y, w, h = faces[0]
        center_x, center_y = x + w // 2, y + h // 2
        new_width = int(height * 3 / 4)
        left = max(center_x - new_width // 2, 0)
        top = 0
        right = min(left + new_width, width)
        bottom = height
        crop = image[top:bottom, left:right] # 감지된 얼굴 기준으로 3/4 비율 크롭
    else: # 얼굴이 감지되지 않은 경우
        new_width = int(height * 3 / 4)
        left = (width - new_width) // 2
        crop = image[:, left:left+new_width] # 가로 기준 중앙을 기준으로 3/4 비율 크롭
    
    webp_file_name = f"{output_dir}/{original_name_no_ext}.webp"
    save_as_webp(crop, webp_file_name) # WEBP 저장
    del crop # GC  
    return [webp_file_name]

# 굿즈 이미지
def process_product_image(image, output_dir, original_name_no_ext, cascade_file):
    faces = detect_faces(image, cascade_file) # 얼굴 감지
    height, width = image.shape[:2]
    
    if len(faces) > 0: # 얼굴이 감지된 경우
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3]) # 가장 큰 얼굴 선택
        center_x, center_y = x + w // 2, y + h // 2
        side_length = max(w, h)
        left = max(center_x - side_length // 2, 0)
        top = max(center_y - side_length // 2, 0)
        right = min(left + side_length, width)
        bottom = min(top + side_length, height)
    else: # 얼굴이 감지되지 않은 경우
        side_length = min(width, height)
        center_x = width // 2
        center_y = height // 3 # 가로 중앙, 세로 1/3 지점 선택
        left = max(0, center_x - side_length // 2)
        top = max(0, center_y - side_length // 2)
        right = min(width, left + side_length)
        bottom = min(height, top + side_length)
    
    crop = image[top:bottom, left:right] # 지정된 영역으로 크롭
    webp_file_name = f"{output_dir}/{original_name_no_ext}-p.webp"
    save_as_webp(crop, webp_file_name) # WEBP 저장
    del crop # GC
    
    return [webp_file_name]

# 이미지 처리 개시
def process_image(img_type, image_data, s3_path, output_dir, cascade_file):
    try:
        start_time = time.time()
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        
        if image is None:
            print(f"이미지를 로드할 수 없습니다: {s3_path}")
            return None

        # 파일명 추출 및 확장자 제거
        original_name = os.path.basename(urlparse(s3_path).path)
        original_name_no_ext = os.path.splitext(original_name)[0]

        # 이미지 종류에 따라 처리 함수 호출
        if img_type == 'description':
            result = process_description_image(image, output_dir, original_name_no_ext)
        elif img_type == 'thumbnail':
            result = process_thumbnail_image(image, output_dir, original_name_no_ext, cascade_file)
        elif img_type == 'product':
            result = process_product_image(image, output_dir, original_name_no_ext, cascade_file)
        else:
            print(f"Unsupported image type: {img_type}")
            return None

        del image 
        gc.collect() # GC

        processing_time = time.time() - start_time
        print(f"Processed {s3_path} in {processing_time:.2f} seconds")
        return result, s3_path, processing_time

    except Exception as e:
        print(f"Error processing {s3_path}: {str(e)}")
        return None

# S3 업로드
# TODO: 원본 파일의 path에 기존 파일 대체하도록 수정해야함 
def upload_to_s3(local_path, bucket_name, s3_path):
    start_time = time.time()
    with open(local_path, 'rb') as file:
        s3_client.upload_fileobj(file, bucket_name, s3_path)
    upload_time = time.time() - start_time
    print(f"Uploaded {local_path} to {s3_path} in bucket {bucket_name} in {upload_time:.2f} seconds")
    os.remove(local_path)  # 업로드 후 로컬 파일 삭제
    return upload_time

# SQS 메시지 처리
def process_record(record, output_dir, cascade_file, bucket_name):
    try:
        body = json.loads(record['body'])
        image_id = body['_id']
        images = body['images']
        
        s3_paths = []
        if 'thumbnail' in images:
            s3_paths.append(('thumbnail', urlparse(images['thumbnail']).path.lstrip('/')))
        if 'description' in images:
            s3_paths.extend(('description', urlparse(desc).path.lstrip('/')) for desc in images['description'])
        if 'product' in images:
            s3_paths.extend(('product', urlparse(prod).path.lstrip('/')) for prod in images['product'])
        if 'watermark' in images:
            s3_paths.append(('watermark', urlparse(images['watermark']).path.lstrip('/')))

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            download_futures = [executor.submit(download_image_from_s3, bucket_name, s3_key) for _, s3_key in s3_paths]
            
            for future, (img_type, _) in zip(as_completed(download_futures), s3_paths):
                image_data, download_time, s3_path = future.result()
                process_future = executor.submit(process_image, img_type, image_data, s3_path, output_dir, cascade_file)
                results.append((process_future, image_id))

        return results

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {str(e)}")
    except Exception as e:
        print(f"Error processing message: {str(e)}")

# 메인
def lambda_handler(event, context):
    output_dir = '/tmp/output'
    os.makedirs(output_dir, exist_ok=True)
    cascade_file = 'lbpcascade_animeface.xml'
    bucket_name = 'kiteapp'

    start_time = time.time()

    processing_times = []
    upload_times = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        record_futures = [executor.submit(process_record, record, output_dir, cascade_file, bucket_name) for record in event['Records']]
        
        all_results = []
        for future in as_completed(record_futures):
            if future.result():
                all_results.extend(future.result())

        upload_futures = []
        for process_future, image_id in all_results:
            result = process_future.result()
            if result:
                processed_files, s3_path, processing_time = result
                processing_times.append(processing_time)
                for local_path in processed_files:
                    relative_path = os.path.relpath(local_path, output_dir)
                    s3_path = os.path.join('processed_images', image_id, relative_path)
                    upload_futures.append(executor.submit(upload_to_s3, local_path, bucket_name, s3_path))

        for future in as_completed(upload_futures):
            upload_time = future.result()
            upload_times.append(upload_time)

    total_time = time.time() - start_time

    max_processing_time = max(processing_times) if processing_times else 0
    max_upload_time = max(upload_times) if upload_times else 0

    print(f"최대 이미지 처리 시간 (병렬 처리): {max_processing_time:.2f} 초")
    print(f"최대 S3 업로드 시간 (병렬 처리): {max_upload_time:.2f} 초")
    print(f"총 처리 시간 (병렬 처리 포함): {total_time:.2f} 초")

    gc.collect()

    return {
        'statusCode': 200,
        'body': json.dumps('Processing completed')
    }
