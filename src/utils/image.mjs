import sharp from 'sharp';
import Vibrant from 'node-vibrant';

export async function cropImage(buffer, options) {
  const { width, height, left, top } = options;
  return sharp(buffer)
    .extract({
      width: Math.max(1, Math.round(width)),
      height: Math.max(1, Math.round(height)),
      left: Math.max(0, Math.round(left)),
      top: Math.max(0, Math.round(top))
    })
    .toBuffer();
}

export async function cropProductImage(buffer, box) {
  const image = sharp(buffer);
  const { width, height } = await image.metadata();

  const cropOptions = getCropOptions(width, height, box);
  
  // 두 크롭 작업을 병렬로 실행
  const [squareCrop, boxCrop] = await Promise.all([
    cropImage(buffer, cropOptions.square),
    cropImage(buffer, cropOptions.box)
  ]);

  return [squareCrop, boxCrop];
}

function getCropOptions(width, height, box) {
  const squareSize = Math.min(width, height);
  const squareCrop = {
    width: squareSize,
    height: squareSize,
    left: 0,
    top: 0,
  };

  let boxCrop = { ...squareCrop };

  if (box && typeof box.x === 'number' && typeof box.y === 'number' && typeof box.w === 'number' && typeof box.h === 'number') {
    const { x, y, w, h } = box;
    const centerX = x + w / 2;
    const centerY = y + h / 2;

    squareCrop.left = Math.max(0, Math.min(width - squareSize, Math.round(centerX - squareSize / 2)));
    squareCrop.top = Math.max(0, Math.min(height - squareSize, Math.round(centerY - squareSize / 2)));

    const boxSize = Math.max(w, h);
    boxCrop = {
      width: Math.min(width, boxSize),
      height: Math.min(height, boxSize),
      left: Math.max(0, Math.min(width - boxSize, Math.round(x + (w - boxSize) / 2))),
      top: Math.max(0, Math.min(height - boxSize, Math.round(y + (h - boxSize) / 2))),
    };
  }

  return { square: squareCrop, box: boxCrop };
}

export async function cropThumbnailImage(buffer, box) {
  const image = sharp(buffer);
  const { width, height } = await image.metadata();

  const aspectRatio = 3 / 4;
  let cropWidth, cropHeight, left, top;

  if (box && typeof box.x === 'number' && typeof box.y === 'number' && typeof box.w === 'number' && typeof box.h === 'number') {
    const { x, y, w, h } = box;
    const centerX = x + w / 2;
    const centerY = y + h / 2;

    // 가로나 세로 중 하나가 원본 이미지에 꽉 차도록 계산
    if (width / height > aspectRatio) {
      // 세로가 꽉 차는 경우
      cropHeight = height;
      cropWidth = cropHeight * aspectRatio;
    } else {
      // 가로가 꽉 차는 경우
      cropWidth = width;
      cropHeight = cropWidth / aspectRatio;
    }

    // box의 중심을 기준으로 crop 영역 계산
    left = Math.max(0, Math.min(width - cropWidth, centerX - cropWidth / 2));
    top = Math.max(0, Math.min(height - cropHeight, centerY - cropHeight / 2));
  } else {
    // box가 없는 경우, 이전과 동일하게 처리
    if (width / height > aspectRatio) {
      cropHeight = height;
      cropWidth = cropHeight * aspectRatio;
    } else {
      cropWidth = width;
      cropHeight = cropWidth / aspectRatio;
    }

    left = (width - cropWidth) / 2;
    top = (height - cropHeight) / 2;
  }

  return cropImage(buffer, { 
    width: Math.max(1, Math.round(cropWidth)), 
    height: Math.max(1, Math.round(cropHeight)), 
    left: Math.max(0, Math.round(left)), 
    top: Math.max(0, Math.round(top))
  });
}

export async function cropArticleImage(buffer) {
  const image = sharp(buffer);
  const { width, height } = await image.metadata();

  const maxHeight = 8192;
  const parts = Math.ceil(height / maxHeight);

  const croppedImages = [];

  for (let i = 0; i < parts; i++) {
    const partHeight = Math.min(maxHeight, height - i * maxHeight);
    const crop = {
      width: Math.round(width),
      height: Math.round(partHeight),
      left: 0,
      top: Math.round(i * maxHeight),
    };
    const croppedBuffer = await cropImage(buffer, crop);
    croppedImages.push({
      buffer: croppedBuffer,
      width,
      height: partHeight,
      part: i + 1,
      total: parts,
    });
  }

  return croppedImages;
}

export async function extractMutedColor(buffer) {
  try {
    if (!Buffer.isBuffer(buffer) || buffer.length === 0) {
      throw new Error('Invalid buffer provided to extractMutedColor');
    }

    // buffer를 PNG 형식으로 변환
    const pngBuffer = await sharp(buffer)
      .png()
      .toBuffer();
    
    // Vibrant.from에 Buffer를 직접 전달
    const palette = await Vibrant.from(pngBuffer).getPalette();
    
    if (!palette.Muted) {
      throw new Error('No Muted color found in the palette');
    }

    return palette.Muted.hex.substring(1);
  } catch (error) {
    console.error('Error in extractMutedColor:', error);
    throw error; // 오류를 상위로 전파하여 호출자가 처리하도록 함
  }
}

export async function getImageMetadata(buffer) {
  const metadata = await sharp(buffer).metadata();
  return {
    width: metadata.width,
    height: metadata.height
  };
}