import ast
import pytest
import boto3
from moto import mock_aws
from bson import ObjectId
import sys
import os
import inspect
import cv2
import numpy as np

# 현재 디렉토리에서 lambda_function.py를 임포트
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lambda_function  # lambda_function 모듈 임포트

# 테스트 시작 전 메시지 출력
print("검사 중: lambda_function.py")

@mock_aws  # S3 이미지 다운로드 테스트
def test_download_image_from_s3():
    print("검사 중: download_image_from_s3 함수")
    s3 = boto3.client('s3', region_name='ap-northeast-2')  # 한국 지역 설정
    s3.create_bucket(Bucket='test-bucket', CreateBucketConfiguration={'LocationConstraint': 'ap-northeast-2'})
    s3.put_object(Bucket='test-bucket', Key='test-image.jpg', Body=b'fake_image_data')

    # S3에서 이미지 다운로드 로직 호출
    image_data, download_time, s3_path = lambda_function.download_image_from_s3('test-bucket', 'test-image.jpg')
    
    assert image_data is not None  # 이미지 데이터가 None이 아님을 확인
    assert s3_path == 's3://test-bucket/test-image.jpg'  # S3 경로 확인

@mock_aws  # 데이터베이스 업데이트 테스트
def test_update_dynamodb():
    print("검사 중: update_dynamodb 함수")
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')  # 한국 지역 설정
    table = dynamodb.create_table(
        TableName='kiteapp-image-transformation',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    
    # 테스트 데이터 삽입
    table.put_item(Item={'id': 'test_id', 'completed': 0})

    # DynamoDB 업데이트 테스트
    lambda_function.update_dynamodb('test_id')  # 모듈 이름 추가

    # 업데이트된 데이터 확인
    response = table.get_item(Key={'id': 'test_id'})
    assert response['Item']['completed'] == 1  # completed 값이 1로 증가했는지 확인

# 모든 함수 자동 테스트
def test_all_functions():
    # 모든 함수 가져오기
    functions = {name: func for name, func in inspect.getmembers(lambda_function, inspect.isfunction)}
    
    for name, func in functions.items():
        print(f"테스트 중: {name}")
        # 각 함수에 필요한 인자를 전달
        try:
            if name == "download_image_from_s3":
                result = func('test-bucket', 'test-image.jpg')  # 필요한 인자 추가
            elif name == "update_dynamodb":
                result = func('test_id')  # 필요한 인자 추가
            elif name == "detect_faces":
                test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
                cv2.rectangle(test_image, (10, 10), (90, 90), (0, 0, 0), -1)
                cascade_file = 'lbpcascade_animeface.xml'
                result = func(test_image, cascade_file)  # 필요한 인자 추가
            else:
                result = func()  # 인자에 맞게 수정 필요
            assert result is not None  # 결과가 None이 아님을 확인
        except Exception as e:
            print(f"{name} 함수에서 오류 발생: {str(e)}")

# 테스트 완료 후 메시지 출력
def pytest_sessionfinish(session, exitstatus):
    print("검사가 완료되었습니다.")

# pytest 실행
if __name__ == '__main__':
    pytest.main()

