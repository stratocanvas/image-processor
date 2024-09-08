# Kite Image Transformation
Kite 서비스용 이미지 처리 레이어
AWS Lambda에서 구동
[![Deploy to AWS Lambda](https://github.com/stratocanvas/kiteapp-image-transformation/actions/workflows/aws.yml/badge.svg)](https://github.com/stratocanvas/kiteapp-image-transformation/actions/workflows/aws.yml)

## 기능
- [x] 이미지에서 캐릭터 얼굴 인식하여 인식된 얼굴 중심으로 크롭
- [x] 8192px 초과 이미지에 대해 분할 생성
- [x] 이미지에서 주요 색상 추출하여 파일명에 반영
- [x] 이미지를 Webp 포맷으로 변환
- [x] 이미지 모델 변경
- [ ] 사용자 지정 워터마크 적용

## 사용 라이브러리
- OpenCV: 워크 플로워
- [yolov8_animeface](https://github.com/MagicalKyaru/yolov8_animeface)
-[anime_face_detection](https://huggingface.co/deepghs/anime_face_detection):사용 모델

- [Vibrant](https://github.com/totallynotadi/vibrant-python): 이미지 주요 색상 추출

## AWS Layer 생성
> [!IMPORTANT]
> 이 Lambda는 Python 3.12 arm64 (linux) 환경에서 구동됩니다.
> 일부 라이브러리는 arm64 linux 환경에 맞는 배포 버전을 사용하거나, 혹은 직접 빌드해야 합니다.

1. 다음 명령어 실행
```shell
pip install --platform manylinux2014_aarch64 --target=./python/lib/python3.12/site-packages --implementation cp --python-version 3.12 --only-binary=:all: --upgrade opencv-python-headless requests vibrant-python
```
2. 생성된 `python`폴더 압축
3. 압축 파일 S3에 업로드 후 Layer 지정

<<<<<<< HEAD
## 배포
- `main` branch에 커밋하면 Github Actions를 통해 자동으로 배포됩니다.

## TODO
- [X]커스텀 OpenCV 빌드하여 라이브러리 경량화
- [ ] 이미지 크롭에 cv2 대신 pyvips 또는 Pillow-SIMD 사용
=======
>>>>>>> origin/dev
