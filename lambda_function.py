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
from vibrant import Vibrant
import threading
from pymongo import MongoClient
from bson import ObjectId


s3_client = boto3.client('s3')
mongodb_uri = os.getenv('MONGODB_URI')
client = MongoClient(mongodb_uri)
db = client['kiteapp']
collection = db['booth']


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
def save_as_webp(image, file_path, type=None, quality=95, extracted_color=None):
    # WebP로 저장
    cv2.imwrite(file_path, image, [cv2.IMWRITE_WEBP_QUALITY, quality])
    file_name, file_ext = os.path.splitext(file_path)
    new_file_name = file_path

    if type != 'description':
        if extracted_color:
            muted_color = extracted_color
        else:
            # 이미지에서 muted 색상 추출
            v = Vibrant()
            palette = v.get_palette(file_path)
            muted_color = '{:02x}{:02x}{:02x}'.format(*palette.muted.rgb)
        
        # 색상 정보 포함하도록 파일명 변경
        new_file_name = f"{file_name}-c({muted_color})"
        
        if type == 'profile':
            new_file_name += '-p'
        
        new_file_name += file_ext
        os.rename(file_path, new_file_name)
    
    print(new_file_name)
    return new_file_name

# 인포 이미지 처리
def process_description_image(image, output_dir, original_name_no_ext):
    height, width = image.shape[:2]
    webp_file_names = []
    
    if height > 8192:  # 세로 8192px 초과하는 이미지에 대해
        total_parts = (height // 8192) + (1 if height % 8192 > 0 else 0)
        for d in range(total_parts):
            part_height = min(8192, height - d * 8192)
            crop_part = image[d * 8192: d * 8192 + part_height, :]  # 8192픽셀씩 쪼갬
            webp_file_name = f"{output_dir}/{original_name_no_ext}-w({width})-h({height})-d({d+1}-{total_parts}).webp"  # 파일명에 w, h, 분할수 포함
            result = save_as_webp(crop_part, webp_file_name, 'description')  # WEBP 저장
            if result:
                webp_file_names.append(result)
            del crop_part  # GC
    else:  # 8192픽셀 이하 이미지에 대해
        webp_file_name = f"{output_dir}/{original_name_no_ext}-w({width})-h({height}).webp"  # 파일명에 w, h 포함
        result = save_as_webp(image, webp_file_name, 'description')  # WEBP 저장
        if result:
            webp_file_names.append(result)
    
    return webp_file_names


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
    result = save_as_webp(crop, webp_file_name) # WEBP 저장
    del crop # GC  
    return [result]


# 굿즈 이미지
def process_product_image(image, output_dir, original_name_no_ext, cascade_file):
    faces = detect_faces(image, cascade_file)
    height, width = image.shape[:2]

    # 유효한 얼굴 선별
    valid_faces = []
    image_area = height * width
    for face in faces:
        x, y, w, h = face
        face_area = w * h
        if face_area >= image_area / 100:
            valid_faces.append(face)

    # 굿즈 이미지: 1:1 비율로 꽉차게 크롭 (이미지 경계 내에서)
    if len(valid_faces) > 0:
        x, y, w, h = max(valid_faces, key=lambda f: f[2] * f[3])
        center_x, center_y = x + w // 2, y + h // 2
    else:
        center_x, center_y = width // 2, 0  # 이미지 상단 중앙

    side_length = min(width, height)
    left = max(0, min(center_x - side_length // 2, width - side_length))
    top = max(0, min(center_y - side_length // 2, height - side_length))
    right = left + side_length
    bottom = top + side_length

    crop = image[top:bottom, left:right]

    webp_file_name = f"{output_dir}/{original_name_no_ext}.webp"
    result = save_as_webp(crop, webp_file_name)
    
    # 원본 이미지에서 추출한 색상 가져오기
    extracted_color = result.split('-c(')[1].split(')')[0]

    # 프로필 이미지: 얼굴 크롭 또는 1.25배 확대 크롭 (1:1 비율 유지)
    if len(valid_faces) > 0:
        x, y, w, h = max(valid_faces, key=lambda f: f[2] * f[3])
        center_x, center_y = x + w // 2, y + h // 2
        crop_size = int(max(w, h) * 1.25)
    else:
        # 얼굴이 감지되지 않은 경우, 이미지 상단 20% 지점을 중심으로 1.25배 확대
        center_x = width // 2
        center_y = int(height * 0.2)  # 상단 20% 지점
        crop_size = int(min(width, height) / 1.25)  

    # 크롭 영역 계산
    left_p = max(0, center_x - crop_size // 2)
    top_p = max(0, center_y - crop_size // 2)
    right_p = min(width, left_p + crop_size)
    bottom_p = min(height, top_p + crop_size)

    # 정사각형 유지를 위해 짧은 쪽에 맞춤
    crop_width = right_p - left_p
    crop_height = bottom_p - top_p
    if crop_width < crop_height:
        diff = crop_height - crop_width
        top_p += diff // 2
        bottom_p -= diff - diff // 2
    elif crop_height < crop_width:
        diff = crop_width - crop_height
        left_p += diff // 2
        right_p -= diff - diff // 2

    # 크롭 및 리사이즈
    crop_p = image[top_p:bottom_p, left_p:right_p]
    crop_p = cv2.resize(crop_p, (int(crop_size * 1.25), int(crop_size * 1.25)), interpolation=cv2.INTER_LINEAR)

    # 처리 B 결과 저장 (원본 이미지의 색상 사용)
    webp_file_name_p = f"{output_dir}/{original_name_no_ext}.webp"
    result_p = save_as_webp(crop_p, webp_file_name_p, 'profile', extracted_color=extracted_color)

    # 메모리 정리
    del crop, crop_p
    gc.collect()

    return [result, result_p]

# 이미지 처리 개시
def process_image(img_type, image_data, s3_path, output_dir, cascade_file, image_id):
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
        if 'thumbnail' in images and images['thumbnail']:
            s3_paths.append(('thumbnail', urlparse(images['thumbnail']).path.lstrip('/')))
        if 'description' in images:
            s3_paths.extend([('description', urlparse(desc).path.lstrip('/')) for desc in images['description']])
        if 'product' in images:
            s3_paths.extend([('product', urlparse(prod).path.lstrip('/')) for prod in images['product']])
        if 'watermark' in images and images['watermark']:
            s3_paths.append(('watermark', urlparse(images['watermark']).path.lstrip('/')))

        results = []
        url_mappings = {}
        with ThreadPoolExecutor(max_workers=10) as executor:

            download_futures = {executor.submit(download_image_from_s3, bucket_name, s3_key): (img_type, s3_key) for img_type, s3_key in s3_paths}
        
            for future in as_completed(download_futures):
                img_type, s3_key = download_futures[future]

                image_data, download_time, s3_path = future.result()
                process_future = executor.submit(process_image, img_type, image_data, s3_path, output_dir, cascade_file, image_id)
                results.append((process_future, image_id, s3_key))

        return results, image_id, url_mappings

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {str(e)}")
    except Exception as e:
        print(f"Error processing message: {str(e)}")
 
 #이미지 삭제단
def parse_s3_url(url):
    parsed_url = urlparse(url)
    bucket_name = parsed_url.netloc.split('.')[0]
    object_key = parsed_url.path.lstrip('/')
    return bucket_name, object_key

def delete_original_image(s3_url):
    try:
        bucket_name, object_key = parse_s3_url(s3_url)
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        print(f"원본 이미지 삭제 성공: {s3_url}")
    except Exception as e:
        print(f"원본 이미지 삭제 실패: {s3_url}, 오류: {str(e)}")


def update_dynamodb(image_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('kiteapp-image-transformation')

    try:
        response = table.update_item(
            Key={'id': image_id},
            UpdateExpression="ADD completed :inc",
            ExpressionAttributeValues={':inc': 1},
            ReturnValues="UPDATED_NEW"
        )
        new_completed_value = response['Attributes'].get('completed', 0)
        print(f"DynamoDB 업데이트 성공: {image_id}, completed: {new_completed_value}")
    except Exception as e:
        print(f"DynamoDB 업데이트 실패: {image_id}, 오류: {str(e)}")

def count_original_images(record):
    body = json.loads(record['body'])
    images = body['images']
    total = 0
    
    if 'thumbnail' in images and images['thumbnail']:
        total += 1
    if 'watermark' in images and images['watermark']:
        total += 1
    total += len(images.get('description', []))
    total += len(images.get('product', []))
    
    return total

# 메인
def lambda_handler(event, context):
    all_url_mappings = {}
    output_dir = '/tmp/output'
    os.makedirs(output_dir, exist_ok=True)
    cascade_file = 'lbpcascade_animeface.xml'
    bucket_name = 'kiteapp'

    start_time = time.time()

    processing_times = []
    upload_times = []
    delete_futures = []
    
    # dynamodb 처리
    total_images = sum(count_original_images(record) for record in event['Records'])
    completed_images = 0
    status_lock = threading.Lock()

    print(f"처리할 이미지: {total_images}")
    print(f"완료된 이미지: {completed_images}")

    def update_completed_count():
        nonlocal completed_images
        with status_lock:
            completed_images += 1
            print(f"완료된 이미지: {completed_images}")

    all_url_mappings = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        record_futures = [executor.submit(process_record, record, output_dir, cascade_file, bucket_name) for record in event['Records']]
        
        all_results = []
        for future in as_completed(record_futures):
            result = future.result()
            if result:
                results, image_id, url_mappings = result
                all_results.extend(results)
                all_url_mappings[image_id] = url_mappings

        upload_futures = []
        
        for process_future, image_id, original_s3_key in all_results:
            result = process_future.result()
            if result:
                processed_files, s3_path, processing_time = result
                processing_times.append(processing_time)
                update_completed_count()
                executor.submit(update_dynamodb, image_id)
                old_url = f"https://{bucket_name}.s3.ap-northeast-2.amazonaws.com/{original_s3_key}"
                
                for local_path in processed_files:
                    relative_path = os.path.relpath(local_path, output_dir)
                    s3_path = os.path.join('booth', image_id, relative_path)# booth 폴더 내 _id별로 폴더 구분해서 저장
                    
                    upload_future = executor.submit(upload_to_s3, local_path, bucket_name, s3_path)
                    upload_futures.append(upload_future)
                    new_url = f"https://{bucket_name}.s3.ap-northeast-2.amazonaws.com/{s3_path}"
                    
                    if '-d(' in relative_path:
                        parts = relative_path.split('-d(')
                        new_url = f"https://{bucket_name}.s3.ap-northeast-2.amazonaws.com/booth/{image_id}/{parts[0]}-d(0-{parts[1].split('-')[1]}"
                    
                    if '-p' not in relative_path:
                        all_url_mappings[image_id][old_url] = new_url
                
                # 원본 이미지 삭제 작업을 별도의 Future로 생성
                delete_future = executor.submit(delete_original_image, f"s3://{bucket_name}/{original_s3_key}")
                delete_futures.append(delete_future)
                

        # 업로드 완료 대기
        for future in as_completed(upload_futures):
            upload_time = future.result()
            upload_times.append(upload_time)

        # 삭제 작업 완료 대기
        for future in as_completed(delete_futures):
            future.result() 
        
    print("모든 이미지 처리 완료. MongoDB 업데이트 시작.")
    for image_id, url_mappings in all_url_mappings.items():
        try:
            update_mongodb_urls(image_id, url_mappings)
        except Exception as e:
            print(f"MongoDB 업데이트 중 오류 발생 (이미지 ID: {image_id}): {str(e)}")


    total_time = time.time() - start_time
    max_processing_time = max(processing_times) if processing_times else 0
    max_upload_time = max(upload_times) if upload_times else 0

    print(f"최대 이미지 처리 시간 (병렬 처리): {max_processing_time:.2f} 초")
    print(f"최대 S3 업로드 시간 (병렬 처리): {max_upload_time:.2f} 초")
    print(f"총 처리 시간 (병렬 처리 포함): {total_time:.2f} 초")

    gc.collect()
    client.close()
    return {
        'statusCode': 200,
        'body': json.dumps('Processing completed')
    }


def update_urls_in_data(data, url_mappings):
    updates = {}
    stack = [('', data)]
    
    while stack:
        path, value = stack.pop()
        if isinstance(value, dict):
            for k, v in value.items():
                new_path = f"{path}.{k}" if path else k
                if k in ['thumbnail', 'src', 'image'] and isinstance(v, str):
                    new_value = url_mappings.get(v)
                    if new_value:
                        updates[new_path] = new_value
                elif isinstance(v, (dict, list)):
                    stack.append((new_path, v))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                new_path = f"{path}.{i}"
                if isinstance(item, str):
                    new_value = url_mappings.get(item)
                    if new_value:
                        updates[new_path] = new_value
                elif isinstance(item, (dict, list)):
                    stack.append((new_path, item))
    
    return updates


def update_mongodb_urls(image_id, url_mappings):
    print(f"MongoDB 업데이트 시작. booth ID: {image_id}")
    print(f"URL 매핑: {url_mappings}")

    projection = {
        'thumbnail': 1,
        'description.content.attrs.src': 1,
        'product.option.image': 1,
    }

    try:
        document = collection.find_one({'_id': ObjectId(image_id)}, projection)
        
        if document:
            updates = update_urls_in_data(document, url_mappings)
            collection.update_one(
                {'_id': ObjectId(image_id)},
                {'$set': updates}
            )
        else:
            print(f"문서를 찾을 수 없음. ID: {image_id}")

    except Exception as e:
        print(f"MongoDB 업데이트 중 오류 발생. 이미지 ID: {image_id}, 오류: {str(e)}")
    
    print(f"MongoDB 업데이트 종료. 이미지 ID: {image_id}")









    #테스트를 위한 코드 수저