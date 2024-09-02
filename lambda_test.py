import ast
import pytest
import boto3  # boto3는 여기서만 사용
from moto import mock_aws  # 모든 AWS 서비스 모킹
from lambda_function import download_image_from_s3, update_dynamodb  # 테스트할 함수 임포트

def extract_aws_and_mongodb_functions(file_path):
    with open(file_path, "r") as file:
        node = ast.parse(file.read())
    
    aws_functions = []
    mongodb_functions = []
    
    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef):
            # AWS 관련 함수 (예: 's3', 'dynamodb'가 포함된 함수)
            if 's3' in n.name or 'dynamodb' in n.name:
                aws_functions.append(n.name)
            # MongoDB 관련 함수 (예: 'mongodb'가 포함된 함수)
            if 'mongodb' in n.name or 'collection' in n.name:
                mongodb_functions.append(n.name)
    
    return aws_functions, mongodb_functions

# 사용 예시
aws_functions, mongodb_functions = extract_aws_and_mongodb_functions('lambda_function.py')

print("AWS Functions:", aws_functions)
print("MongoDB Functions:", mongodb_functions)

# 테스트 코드
@mock_aws
def test_download_image_from_s3():
    s3 = boto3.client('s3', region_name='ap-northeast-2')  # 한국 지역 설정
    s3.create_bucket(Bucket='test-bucket', CreateBucketConfiguration={'LocationConstraint': 'ap-northeast-2'})
    s3.put_object(Bucket='test-bucket', Key='test-image.jpg', Body=b'fake_image_data')

    # S3에서 이미지 다운로드 로직 호출
    image_data, download_time, s3_path = download_image_from_s3('test-bucket', 'test-image.jpg')
    
    assert image_data is not None  # 이미지 데이터가 None이 아님을 확인
    assert s3_path == 's3://test-bucket/test-image.jpg'  # S3 경로 확인

@mock_aws
def test_update_dynamodb():
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')  # 한국 지역 설정
    table = dynamodb.create_table(
        TableName='test_table',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    
    # 테스트 데이터 삽입
    table.put_item(Item={'id': 'test_id', 'completed': 0})

    # DynamoDB 업데이트 테스트
    update_dynamodb('test_id')  # region_name 인자 제거

    # 업데이트된 데이터 확인
    response = table.get_item(Key={'id': 'test_id'})
    assert response['Item']['completed'] == 1  # completed 값이 1로 증가했는지 확인

# pytest 실행
if __name__ == '__main__':
    pytest.main()
