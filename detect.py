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
        print("크롭 영역이 유효하지 않습니다.")
        return None  # 빈 이미지 반환

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

                    if img_type == 'description':
                        # 얼굴 감지 생략
                        width, height = image.shape[1], image.shape[0]
                        
                        if height > 8192:  # 세로가 8192px 이상일 때
                            total_parts = (height // 8192) + (1 if height % 8192 > 0 else 0)
                            for d in range(total_parts):
                                part_height = min(8192, height - d * 8192)
                                crop_part = image[d * 8192: d * 8192 + part_height, :]
                                webp_file_name_desc = f"{output_dir}/{original_name_no_ext}-w{width}-h{height}-d{d+1}-{total_parts}"  # 확장자 제거
                                cv2.imwrite(webp_file_name_desc + ".webp", crop_part)  # 분할된 이미지 저장
                                print(f"변환 완료: {webp_file_name_desc}.webp")  # 저장 완료 메시지 출력
                        else:
                            webp_file_name_desc = f"{output_dir}/{original_name_no_ext}-w{width}-h{height}"  # 확장자 제거
                            cv2.imwrite(webp_file_name_desc + ".webp", image)  # 설명 이미지 저장
                            print(f"변환 완료: {webp_file_name_desc}.webp")  # 저장 완료 메시지 출력
                        continue  # 다음 이미지로 넘어감
                    
                    if img_type == 'thumbnail':
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
                        
                        continue  # 다음 이미지로 넘어감
                    
                    if img_type == 'product':
                        # 얼굴 감지
                        faces = detect_faces(image, cascade_file)
                        
                        # 유효한 얼굴 필터링
                        valid_faces = []
                        image_area = image.shape[0] * image.shape[1]
                        for face in faces:
                            x, y, w, h = face
                            face_area = w * h
                            if face_area >= image_area / 100:  # 얼굴 크기가 이미지의 1/100 이상인 경우만 유효
                                valid_faces.append(face)
                        
                        if len(valid_faces) > 0:
                            # 가장 큰 얼굴 찾기
                            largest_face = max(valid_faces, key=lambda face: face[2] * face[3])
                            
                            # 1. 가장 큰 얼굴 중심의 1:1 크롭 (좁은 영역)
                            crop_1_1_face = crop_face(image, largest_face, '1:1')
                            if crop_1_1_face is not None:
                                webp_file_name_1_1_face = f"{output_dir}/{original_name_no_ext}"
                                cv2.imwrite(webp_file_name_1_1_face + ".webp", crop_1_1_face)
                                print(f"변환 완료: {webp_file_name_1_1_face}.webp")
                            
                            # 2. 가능한 가장 큰 1:1 크롭 (가장 큰 얼굴 포함)
                            x, y, w, h = largest_face
                            center_x, center_y = x + w // 2, y + h // 2
                            side_length = min(image.shape[0], image.shape[1])
                            
                            left = max(0, center_x - side_length // 2)
                            top = max(0, center_y - side_length // 2)
                            right = min(image.shape[1], left + side_length)
                            bottom = min(image.shape[0], top + side_length)
                            
                            if right - left < side_length:
                                left = max(0, right - side_length)
                            if bottom - top < side_length:
                                top = max(0, bottom - side_length)
                            
                            crop_1_1_wide = image[top:bottom, left:right]
                            if crop_1_1_wide is not None and crop_1_1_wide.size > 0:
                                webp_file_name_1_1_wide = f"{output_dir}/{original_name_no_ext}-t"
                                cv2.imwrite(webp_file_name_1_1_wide + ".webp", crop_1_1_wide)
                                print(f"변환 완료: {webp_file_name_1_1_wide}.webp")
                        else:
                            # 유효한 얼굴 인식 실패 시 위에서 1/3 지점을 중심으로 1:1 비율 크롭 생성
                            print(f"상품 이미지에서 유효한 얼굴 인식 실패 {url}. 위에서 1/3 지점 편집.")
                            
                            height, width = image.shape[:2]
                            side_length = min(height, width)
                            center_x = width // 2
                            center_y = height // 3  # 위에서 1/3 지점
                            
                            # 1. 원본 크기의 1:1 크롭 (위에서 1/3 지점 기준)
                            left = center_x - side_length // 2
                            top = max(0, center_y - side_length // 2)
                            right = left + side_length
                            bottom = top + side_length
                            
                            # 이미지 경계를 벗어나지 않도록 조정
                            if bottom > height:
                                top = max(0, height - side_length)
                                bottom = height
                            
                            crop_upper_third = image[top:bottom, left:right]
                            if crop_upper_third is not None and crop_upper_third.size > 0:
                                webp_file_name_1_1 = f"{output_dir}/{original_name_no_ext}-t"
                                cv2.imwrite(webp_file_name_1_1 + ".webp", crop_upper_third)
                                print(f"변환 완료: {webp_file_name_1_1}.webp")
                            
                            # 2. 0.7배 확대된 1:1 크롭 (위에서 1/3 지점 기준)
                            enlarged_side_length = int(side_length * 0.7)
                            left = center_x - enlarged_side_length // 2
                            top = max(0, center_y - enlarged_side_length // 2)
                            right = left + enlarged_side_length
                            bottom = top + enlarged_side_length
                            
                            # 크롭 영역이 이미지 경계를 벗어나지 않도록 조정
                            left = max(0, left)
                            top = max(0, top)
                            right = min(width, right)
                            bottom = min(height, bottom)
                            
                            crop_upper_third_enlarged = image[top:bottom, left:right]
                            if crop_upper_third_enlarged is not None:
                                webp_file_name_1_1_enlarged = f"{output_dir}/{original_name_no_ext}"
                                cv2.imwrite(webp_file_name_1_1_enlarged + ".webp", crop_upper_third_enlarged)
                                print(f"변환 완료: {webp_file_name_1_1_enlarged}.webp")
                        
                        continue  # 다음 이미지로 넘어감
                    
                    faces = detect_faces(image, cascade_file)
                    
                    if len(faces) == 0:
                        # 얼굴 인식 실패 시 중앙 기준으로 자르기
                        print(f"얼굴 인식 실패 {url}. 중앙 편집.")
                        crop_3_4 = crop_face(image, (0, 0, image.shape[1], image.shape[0]), '3:4')  # 전체 이미지 자르기
                        webp_file_name_3_4 = f"{output_dir}/{original_name_no_ext}"  # 파일 이름 수정 (확장자 제거)
                        cv2.imwrite(webp_file_name_3_4 + ".webp", crop_3_4)  # 크기 조정 후 저장
                        print(f"변환 완료: {webp_file_name_3_4}.webp")  # 저장 완료 메시지 출력
                        
                        crop_1_1 = crop_face(image, (0, 0, image.shape[1], image.shape[0]), '1:1')  # 전체 이미지 자르기
                        webp_file_name_1_1 = f"{output_dir}/{original_name_no_ext}"  # 파일 이름 수정 (확장자 제거)
                        cv2.imwrite(webp_file_name_1_1 + ".webp", crop_1_1)  # 크기 조정 후 저장
                        print(f"변환 완료: {webp_file_name_1_1}.webp")  # 저장 완료 메시지 출력
                        
                        # 이미지 분할 처
                        if (image.shape[1] + image.shape[0]) > 8192:  # 가로세로 ��이 8192px 이상일 때
                            height, width = image.shape[:2]
                            total_parts = (height // 8192) + (width // 8192) + 1
                            for d in range(total_parts):
                                # 분할 로직 구현
                                part_height = min(8192, height - d * 8192)
                                part_width = min(8192, width - d * 8192)
                                crop_part = image[d * 8192: d * 8192 + part_height, d * 8192: d * 8192 + part_width]
                                webp_file_name_face = f"{output_dir}/{original_name_no_ext}_3_4-d{d+1}-{total_parts}"  # 확장자 제거
                                cv2.imwrite(webp_file_name_face + ".webp", crop_part)  # 분할된 이미지 저장
                                print(f"변환 완료: {webp_file_name_face}.webp")  # 저장 완료 메시지 출력
                
                    else:
                        for j, face in enumerate(faces):
                            # 3:4 율로 자르기
                            crop_3_4 = crop_face(image, face, '3:4')
                            webp_file_name_3_4 = f"{output_dir}/{original_name_no_ext}"  # 원래 이름 기반으로 수정 (확장자 제거)
                            cv2.imwrite(webp_file_name_3_4 + ".webp", crop_3_4)  # 크기 조정 후 저장
                            print(f"변환 완료: {webp_file_name_3_4}.webp")  # 저장 완료 메시지 출력
                            
                            # 1:1 비율로 자르기
                            crop_1_1 = crop_face(image, face, '1:1')
                            webp_file_name_1_1 = f"{output_dir}/{original_name_no_ext}"  # 원래 이름 기반으로 수정 (확장자 제거)
                            cv2.imwrite(webp_file_name_1_1 + ".webp", crop_1_1)  # 크기 조정 후 저장
                            print(f"변환 완료: {webp_file_name_1_1}.webp")  # 저장 완료 메시지 출력
                            
                            # 이미지 분할 처리
                            if (image.shape[1] + image.shape[0]) > 8192:  # 가로세로  8192px 이상일 때
                                height, width = image.shape[:2]
                                total_parts = (height // 8192) + (width // 8192) + 1
                                for d in range(total_parts):
                                    # 분할 로직 구현
                                    part_height = min(8192, height - d * 8192)
                                    part_width = min(8192, width - d * 8192)
                                    crop_part = image[d * 8192: d * 8192 + part_height, d * 8192: d * 8192 + part_width]
                                    webp_file_name_face = f"{output_dir}/{original_name_no_ext}_3_4-d{d+1}-{total_parts}"  # 확장자 제거
                                    cv2.imwrite(webp_file_name_face + ".webp", crop_part)  # 분할된 이미지 저장
                                    print(f"변환 완료: {webp_file_name_face}.webp")  # 저장 완료 메시지 출력
                
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
                        
                        if product_count == len(data['images']['product']):  # 모 품 처리 후
                            print("모든 상품 이미지 처리 완료.")

                except requests.RequestException as e:
                    print(f"Error downloading {url}: {str(e)}")
                except Exception as e:
                    print(f"Error processing {url}: {str(e)}")

            # 모든 이미지 처리 후 알림 출력
            print(f"모든 섭네일 이미지 처리 완료: {thumbnail_count}개")
            print(f"모든 상품 이미지 처리 료: {product_count}개")
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
        f.write(f"타 처리 시간 (라이브러리 로딩 등): {other_time:.2f} 초\n")
        f.write(f"총 처리 시간: {total_time:.2f} 초\n")

if __name__ == "__main__":
    # 현재 스크립트의 디렉토 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, 'source.json')  # 상대 경로 수정
    output_dir = "output_faces"
    cascade_file = "lbpcascade_animeface.xml"
    process_urls(input_file, output_dir, cascade_file)