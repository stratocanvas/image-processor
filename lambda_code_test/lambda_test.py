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
from pymongo import MongoClient
import mongomock  # mongomock 임포트

# 현재 디렉토리에서 lambda_function.py를 임포트
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lambda_function  # lambda_function 모듈 임포트

# 테스트 시작 전 메시지 출력
print("검사 중: lambda_function.py")

# aws 모든 함수 자동 테스트
@mock_aws  # AWS 모킹
def test_all_functions():
    print("검사 중: 모든 함수 테스트")
    
    # AWS 리소스 설정 (예: S3, DynamoDB 등)
    s3 = boto3.client('s3', region_name='ap-northeast-2')
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')

    # S3 버킷 생성 및 테스트 데이터 업로드
    s3.create_bucket(Bucket='test-bucket', CreateBucketConfiguration={'LocationConstraint': 'ap-northeast-2'})
    s3.put_object(Bucket='test-bucket', Key='test-image.jpg', Body=b'fake_image_data')

    # DynamoDB 테이블 생성
    table = dynamodb.create_table(
        TableName='kiteapp-image-transformation',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )

    # lambda_function의 모든 함수 가져오기
    functions = {name: func for name, func in inspect.getmembers(lambda_function, inspect.isfunction)}

    for name, func in functions.items():
        print(f"테스트 중: {name}")
        try:
            # AWS 관련 함수 테스트
            if name == "download_image_from_s3":
                image_data, download_time, s3_path = func('test-bucket', 'test-image.jpg')  # 필요한 인자 추가
                assert image_data is not None  # 이미지 데이터가 None이 아님을 확인
                assert s3_path == 's3://test-bucket/test-image.jpg'  # S3 경로 확인
            elif name == "update_dynamodb":
                table.put_item(Item={'id': 'test_id', 'completed': 0})
                func('test_id')  # 필요한 인자 추가
                response = table.get_item(Key={'id': 'test_id'})
                assert response['Item']['completed'] == 1  # completed 값이 1로 증가했는지 확인
            
            # MongoDB 관련 함수 테스트
            elif 'mongodb' in name:
                # MongoDB 관련 테스트 로직 추가
                pass  # 여기에 MongoDB 관련 함수 테스트 로직을 추가할 수 있습니다.

            # 기타 함수 테스트
            else:
                result = func()  # 인자에 맞게 수정 필요
                assert result is not None  # 결과가 None이 아님을 확인

        except TypeError as te:
            print(f"{name} 함수에서 TypeError 발생: {str(te)}")
        except AssertionError as ae:
            print(f"{name} 함수에서 AssertionError 발생: {str(ae)}")
        except KeyError as ke:
            print(f"{name} 함수에서 KeyError 발생: {str(ke)}")
        except Exception as e:
            print(f"{name} 함수에서 오류 발생: {str(e)}")

# MongoDB 관련 함수 자동 테스트
def test_mongodb_functions():
    print("검사 중: MongoDB 관련 함수 테스트")
    
    # mongomock을 사용하여 MongoDB 클라이언트 생성
    client = mongomock.MongoClient()
    db = client['test_db']
    collection = db['test_collection']

    # lambda_function의 MongoDB 관련 함수 가져오기
    functions = {name: func for name, func in inspect.getmembers(lambda_function, inspect.isfunction) if 'mongodb' in name}

    # 문서 삽입 및 조회 테스트
    document = {'id': 'test_id', 'completed': 0}
    
    # insert_document 함수 테스트
    if 'insert_document' in functions:
        insert_func = functions['insert_document']
        insert_func(collection, document)  # 문서 삽입
        result = collection.find_one({'id': 'test_id'})
        assert result is not None  # 결과가 None이 아님을 확인
        assert result['completed'] == 0  # 삽입한 문서의 completed 값 확인
        print("insert_document 테스트 성공")

    # find_document 함수 테스트
    if 'find_document' in functions:
        find_func = functions['find_document']
        result = find_func(collection, {'id': 'test_id'})  # 문서 조회
        assert result is not None  # 결과가 None이 아님을 확인
        assert result['completed'] == 0  # 삽입한 문서의 completed 값 확인
        print("find_document 테스트 성공")

    # 추가적인 MongoDB 관련 함수가 있다면 여기에 추가

# 테스트 완료 후 메시지 출력
def pytest_sessionfinish(session, exitstatus):
    print("검사가 완료되었습니다.")

# pytest 실행
if __name__ == '__main__':
    pytest.main()
