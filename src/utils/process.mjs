import { download, upload, moveObject, remove } from './net/s3.mjs';
import { runDetection } from '@stratocanvas/easy-ort';
import { cropProductImage, cropThumbnailImage, cropArticleImage, extractMutedColor, getImageMetadata } from './image.mjs';
import { update } from './net/rpc.mjs';

export async function processImages(message) {
  const { booth_id, images } = message;
  const imageCategories = ['thumbnail', 'article', 'product'];

  // 이미지 다운로드 및 처리
  const processedImages = await Promise.all(
    imageCategories.flatMap(category => 
      (Array.isArray(images[category]) ? images[category] : [images[category]])
        .filter(Boolean)
        .map(url => downloadAndProcessImage(category, url))
    )
  );

  // 이미지 크롭
  const croppedImages = await Promise.all(processedImages.map(processCategoryImage));
  
  // S3에 업로드 및 정리
  await uploadAndCleanup(booth_id, croppedImages, images);

  // 데이터베이스 업데이트를 위한 쿼리 생성 및 실행
  const updateQuery = createUpdateQuery(booth_id, croppedImages, images);
  try {
    await update(updateQuery);
    console.log('Database updated successfully');
  } catch (error) {
    console.error('Error updating database:', error);
  }

  return croppedImages;
}

async function downloadAndProcessImage(category, url) {
  const filename = url.split('/').pop();
  try {
    const buffer = await download(filename);
    const processedImage = { category, originalUrl: url, buffer };
    
    if (category === 'product' || category === 'thumbnail') {
      const detectionResult = await runDetectionOnImage(buffer);
      const box = detectionResult ? findBestDetection(detectionResult.detections) : null;
      processedImage.box = box;
    }
    
    return processedImage;
  } catch (error) {
    console.error(`Error processing image ${url}:`, error);
    return { category, originalUrl: url, error: error.message };
  }
}

async function runDetectionOnImage(buffer) {
  const options = {
    modelPath: process.env.MODEL_PATH,
    labels: ['head'],
    iouThreshold: 0.6,
    confidenceThreshold: 0.25,
    targetSize: [384, 384],
    headless: true,
  };

  try {
    const results = await runDetection([buffer], options);
    return results[0];
  } catch (error) {
    console.error('Error in runDetection:', error);
    return null;
  }
}

async function cropImages(processedImages) {
  return Promise.all(processedImages.map(processCategoryImage));
}

async function processCategoryImage(image) {
  if (image.error) return image;

  try {
    const result = await (async () => {
      switch (image.category) {
        case 'product':
          return processProductImage(image);
        case 'thumbnail':
          return processThumbnailImage(image);
        case 'article':
          return processArticleImage(image);
        default:
          throw new Error(`Unsupported image category: ${image.category}`);
      }
    })();

    // 원본 buffer 제거
    const { buffer, ...imageWithoutBuffer } = image;
    
    return result;
  } catch (error) {
    console.error(`Error processing ${image.category} image:`, error);
    return {
      category: image.category,
      originalUrl: image.originalUrl,
      error: error.message,
    };
  }
}

async function processProductImage(image) {
  try {
    const [squareCrop, boxCrop] = await cropProductImage(image.buffer, image.box);
    if (!squareCrop || !boxCrop || !Buffer.isBuffer(squareCrop) || !Buffer.isBuffer(boxCrop)) {
      throw new Error('Invalid product crop results');
    }
    const squareColor = await extractMutedColor(squareCrop).catch(() => 'default');

    return {
      category: image.category,
      originalUrl: image.originalUrl,
      croppedImages: [
        { buffer: squareCrop, suffix: `-c(${squareColor})` },
        { buffer: boxCrop, suffix: `-c(${squareColor})-p` },
      ],
    };
  } catch (error) {
    console.error('Error in processProductImage:', error);
    return {
      category: image.category,
      originalUrl: image.originalUrl,
      error: error.message,
    };
  }
}

async function processThumbnailImage(image) {
  try {
    const thumbnailCrop = await cropThumbnailImage(image.buffer, image.box);
    if (!thumbnailCrop || !Buffer.isBuffer(thumbnailCrop)) {
      throw new Error('Invalid thumbnail crop result');
    }
    const thumbnailColor = await extractMutedColor(thumbnailCrop).catch(() => 'default');

    return {
      category: image.category,
      originalUrl: image.originalUrl,
      croppedImages: [
        { buffer: thumbnailCrop, suffix: `-c(${thumbnailColor})` },
      ],
    };
  } catch (error) {
    console.error('Error in processThumbnailImage:', error);
    return {
      category: image.category,
      originalUrl: image.originalUrl,
      error: error.message,
    };
  }
}

async function processArticleImage(image) {
  const { width: originalWidth, height: originalHeight } = await getImageMetadata(image.buffer);

  const articleCrops = await cropArticleImage(image.buffer);

  return {
    category: image.category,
    originalUrl: image.originalUrl,
    croppedImages: articleCrops.map((crop) => {
      let suffix = `-w(${originalWidth})-h(${originalHeight})`;
      if (originalHeight > 8192) {
        suffix += `-d(${crop.part}-${crop.total})`;
      }
      return {
        buffer: crop.buffer,
        suffix: suffix,
        width: crop.width,
        height: crop.height,
        part: crop.part,
        total: crop.total,
      };
    }),
  };
}

function findBestDetection(detections) {
  if (!detections || detections.length === 0) return null;
  const best = detections.reduce((best, current) => 
    (current.confidence * current.squareness > best.confidence * best.squareness) ? current : best
  );
  
  // box 배열을 x, y, w, h 객체로 변환
  return {
    x: best.box[0],
    y: best.box[1],
    w: best.box[2],
    h: best.box[3],
    confidence: best.confidence,
    squareness: best.squareness
  };
}

async function uploadAndCleanup(boothId, processedImages, originalImages) {
  const uploadTasks = [];
  const moveOriginalTasks = [];
  const imagesToDelete = new Set();

  for (const image of processedImages) {
    if (image.error) continue;

    const { category, originalUrl, croppedImages } = image;
    const filename = originalUrl.split('/').pop();

    uploadTasks.push(...croppedImages.map(croppedImage => {
      const croppedFilename = `${filename.split('.')[0]}${croppedImage.suffix}.jpg`;
      return upload(boothId, croppedFilename, croppedImage.buffer);
    }));

    if (category === 'product' || category === 'thumbnail') {
      const sourceKey = `${process.env.QUEUE_PATH}/${filename}`;
      const destinationKey = `booth/${boothId}/${filename}`;
      moveOriginalTasks.push(moveObject(sourceKey, destinationKey));
    }

    imagesToDelete.add(filename);
  }

  try {
    await Promise.all([...uploadTasks, ...moveOriginalTasks]);

    // queue에서 모든 원본 이미지 삭제
    if (imagesToDelete.size > 0) {
      await remove(Array.from(imagesToDelete));
    } else {
      console.log('No images to delete from queue');
    }
  } catch (error) {
    console.error('Error in uploadAndCleanup:', error);
    throw error;
  }
}

function createUpdateQuery(boothId, croppedImages, originalImages) {
  const urls = {
    thumbnail: null,
    article: {},
    product: {}
  };

  for (const image of croppedImages) {
    if (image.error) continue;

    const { category, originalUrl, croppedImages } = image;
    const filename = originalUrl.split('/').pop();
    const baseUrl = `https://${process.env.BUCKET_NAME}.s3.${process.env.AWS_REGION}.amazonaws.com/booth/${boothId}/${filename.split('.')[0]}`;

    switch (category) {
      case 'thumbnail':
        urls.thumbnail = `${baseUrl}${croppedImages[0].suffix}.jpg`;
        break;
      case 'article':
        {
          let articleUrl = `${baseUrl}-w(${croppedImages[0].width})-h(${croppedImages[0].height})`;
          if (croppedImages[0].total > 1) {
            articleUrl += '-d(0-0)';
          }
          urls.article[originalUrl] = `${articleUrl}.jpg`;
        }
        break;
      case 'product':
        {
          const mainImageSuffix = croppedImages[0].suffix.replace(/-c\([^)]+\)-t/, '-c($1)');
          const mainImageUrl = `${baseUrl}${mainImageSuffix}.jpg`;
          urls.product[originalUrl] = mainImageUrl;
        }
        break;
    }
  }

  return {
    booth_id: boothId,
    urls: urls
  };
}