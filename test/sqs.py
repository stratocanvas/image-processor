import boto3
import requests
import cv2
import numpy as np
import json

# AWS 자격 증명 설정
aws_access_key_id = '검열'
aws_secret_access_key = '검열'
region_name = 'ap-northeast-2'  # 서울 리전

# SQS 클라이언트 생성
sqs = boto3.client(
    'sqs',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)

# 큐 URL 설정
queue_url = 'sqs url'

# 메시지 보내기
def send_messages(data):
    # 전체 데이터를 메시지 본문으로 전송
    message_body = {
        "_id": data["_id"],  # ID 추가
        "thumbnail": data["images"]["thumbnail"],  # 썸네일 추가
        "description_urls": data['images']['description'],  # 설명 URL 추가
        "product_urls": data['images']['product'],  # 제품 URL 추가
        "is_split": False,  # 나누어진 메시지가 아님을 표시
        "message_id": "full_message"  # 전체 메시지 ID
    }
    
    print("전송할 메시:", message_body)  # 전송할 메시지 출력
    
    # 메시지 크기 확인 및 나누어 보내기
    message_json = json.dumps(message_body)
    if len(message_json.encode('utf-8')) > 128 * 1024:  # 128KB 초과 확인
        # 메시지를 나누어 보내기
        split_messages = []
        max_urls_per_message = 10  # 각 메시지에 포함할 URL 수
        description_urls = data['images']['description']
        product_urls = data['images']['product']
        
        # 설명 URL 나누기
        for i in range(0, len(description_urls), max_urls_per_message):
            split_messages.append({
                "_id": data["_id"],
                "thumbnail": data["images"]["thumbnail"],
                "description_urls": description_urls[i:i + max_urls_per_message],
                "product_urls": [],
                "is_split": True,
                "message_id": f"split_message_{i // max_urls_per_message + 1}"
            })
        
        # 제품 URL 나누기
        for i in range(0, len(product_urls), max_urls_per_message):
            split_messages.append({
                "_id": data["_id"],
                "thumbnail": data["images"]["thumbnail"],
                "description_urls": [],
                "product_urls": product_urls[i:i + max_urls_per_message],
                "is_split": True,
                "message_id": f"split_message_{len(description_urls) // max_urls_per_message + (i // max_urls_per_message) + 1}"
            })
        
        # 나누어진 메시지 전송
        for msg in split_messages:
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(msg)  # JSON 형식으로 전송
            )
            print(f"Message sent! Message ID: {response['MessageId']}")
    else:
        # 전체 메시지 전송
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_json  # JSON 형식으로 전송
        )
        print(f"Message sent! Message ID: {response['MessageId']}")

    print("전송 완료")  # 전송 완료 메시지 출력

if __name__ == "__main__":
    # 주어진 JSON 데이터
    data = {
        "_id": "TEST_ID_001",
        "images": {
            "thumbnail": "https://d2i2w6ttft7yxi.cloudfront.net/thumbnail/ts320240802034903_1123802_rs.jpg",
            "description": [
                "https://i.namu.wiki/i/ujWyCRh8LnPuni7XcyEy4kPJ_XdsgDPCJpLbWqN3rgSxvVlaj9uViEAtfQPWzR_0TixksrT-FuVN2h8WhXtdrQ.webp",
                "https://kiteapp.s3.ap-northeast-2.amazonaws.com/artist/7JYhze1wBRe7OcLN_C_9c.png",
                "https://kiteapp.s3.ap-northeast-2.amazonaws.com/artist/QjTtNCKvFvQw0JrtfohEk.png"
            ],
            "product": [
                "https://kiteapp.s3.ap-northeast-2.amazonaws.com/test/GSWwZ0AWUAAM2T21.jpg",
                "https://kiteapp.s3.ap-northeast-2.amazonaws.com/test/GSWwWnaXoAAeegN1.jpg",
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDiuUO82UVePo2MweEE2cflMQiUo9ibTa27A&s",
                "https://dcimg4.dcinside.co.kr/viewimage.php?id=3dafdf2ce0d12cab76&no=24b0d769e1d32ca73de983fa11d02831c6c0b61130e4349ff064c41af0d3cfaa6a249bb9689408f24d15b17a5b50f1a03a81b64f2dd2526a2eda256a84432f1e3441ba2e4ada4fcb278f25b899bbe7ecbd",
                "https://pbs.twimg.com/media/FhXWeMGUoAA-8yx?format=jpg&name=4096x4096",
                "https://api.kitebooth.com/storage/v1/object/public/product/option/f692ffa5-e3ee-4c12-86b5-50fe8c5621e6-c(91828c)-w(380)-h(415).png",
                "https://dcimg4.dcinside.co.kr/viewimage.php?id=3dafdf2ce0d12cab76&no=24b0d769e1d32ca73de983fa11d02831c6c0b61130e4349ff064c41af0dccfaa0bc88f208486feb0bbb43ee4615e53a8d654589aae45a81bbcf8a54a8c46a359c8aaa178df190522278dcfaf5fa786c3fae7eb3736982c1dfd570e94196d5233406e6c6e3eb30c64c7",
                "https://dcimg4.dcinside.co.kr/viewimage.php?id=3dafdf2ce0d12cab76&no=24b0d769e1d32ca73de983fa11d02831c6c0b61130e4349ff064c41af0dccfaa0bc88f208486feb0bbb43ee4615c52a9196d65d3c5cd6975eae5045e9b1eaf081f4aa7b2",
                "https://mblogthumb-phinf.pstatic.net/MjAyMzA3MTFfODQg/MDAxNjg5MDY0ODc2MDc3.pf8DDWa1EE4BC_6PdALjqR_RM6zC0ryVFKHXza5-x48g.t8jJrTlg7onw9ZRUq4oylWpqLubNNwtMX_UTSe3R7bog.PNG.sniperriflesr2/1.png?type=w800",
                "https://api.kitebooth.com/storage/v1/object/public/product/option/8fb73773-5658-47a1-b46b-e073383f1c38-c(669ca4)-w(721)-h(695).jpeg",
                "https://www.kitebooth.com/_next/image?url=https%3A%2F%2Fapi.kitebooth.com%2Fstorage%2Fv1%2Fobject%2Fpublic%2Fproduct%2Foption%2F85f57cee-6533-4100-8903-6f0ecf649505-c(a07660)-w(721)-h(695).jpeg&w=3840&q=75",
                "https://i.pinimg.com/736x/00/f3/b0/00f3b0c2b42a690cd91d5d51b1020747.jpg",
                "https://image.fmkorea.com/files/attach/new4/20240626/7184641312_2895716_805433a521f906a67fc61ef1dda61cf1.jpg",
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQO-BeuKanmiXNHa-uGTYIqIb1NPuYpvuqcKw&s"
            ],
            "watermark": "https://kiteapp.s3.ap-northeast-2.amazonaws.com/test/watermark.jpg"
        }
    }
    send_messages(data)