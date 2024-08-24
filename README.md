## Kite Image Transformation
Kite 서비스용 이미지 처리 레이어
AWS Lambda에서 구동

## 사용 라이브러리
- OpenCV
- Vibrant

## AWS Layer 생성

1. 다음 명령어 실행
```shell
pip install --platform manylinux2014_aarch64 --target=./python/lib/python3.12/site-packages --implementation cp --python-version 3.12 --only-binary=:all: --upgrade opencv-python-headless requests vibrant-python
```
2. 생성된 `python`폴더 압축
3. 압축 파일 S3에 업로드 후 Layer 지정

