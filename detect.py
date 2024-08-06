import json
import time
import os
import requests
from PIL import Image
import io

output_dir = "output_faces"

def update_status(item_id, status):
    print(f"상태 업데이트: {item_id} - {status}")

def process_image(image_url, item_id, image_type):
    print(f"이미지 처리 중: {image_url}")
    
    try:
        # 이미지 다운로드
        response = requests.get(image_url)
        response.raise_for_status()  # HTTP 오류 확인
        
        # 응답 내용 확인
        content_type = response.headers.get('content-type')
        print(f"콘텐츠 타입: {content_type}")  # 디버깅용 출력
        if 'image' not in content_type:
            print(f"경고: 콘텐츠 타입이 이미지가 아닙니다: {content_type}")
            return

        img = Image.open(io.BytesIO(response.content))
        print(f"원본 이미지 모드: {img.mode}")  # 디버깅용 출력
        
        # RGBA 모드인 경우 RGB로 변환
        if img.mode == 'RGBA':
            img = img.convert('RGB')
            print("RGBA에서 RGB로 변환됨")  # 디버깅용 출력
        
        print(f"최종 이미지 모드: {img.mode}")  # 디버깅용 출력
        
        # 처리된 이미지 저장
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        output_filename = f"{item_id}_{image_type}.png"  # JPEG 대신 PNG 사용
        output_path = os.path.join(output_dir, output_filename)
        
        img.save(output_path)
        
        print(f"이미지 저장됨: {output_path}")
        update_status(item_id, f"{image_type}_완료")
    except requests.RequestException as e:
        print(f"이미지 다운로드 오류: {e}")
    except Image.UnidentifiedImageError:
        print(f"이미지를 식별할 수 없음: {image_url}")
    except Exception as e:
        print(f"이미지 처리 중 오류 발생: {e}")

def process_message(data):
    item_id = data['_id']
    images = data['images']
    
    # 썸네일 이미지 처리
    if 'thumbnail' in images:
        process_image(images['thumbnail'], item_id, '썸네일')
    
    # 설명 이미지 처리
    for i, img_url in enumerate(images.get('description', []), 1):
        process_image(img_url, item_id, f'설명_{i}')
    update_status(item_id, '설명_모두_완료')
    
    # 제품 이미지 처리
    for i, img_url in enumerate(images.get('product', []), 1):
        process_image(img_url, item_id, f'제품_{i}')
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