import { GetObjectCommand, PutObjectCommand, DeleteObjectsCommand, S3Client, CopyObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import dotenv from 'dotenv';

// .env 파일 로드
dotenv.config({ path: '.env.local' });

const client = new S3Client({
  region: process.env.AWS_REGION || "ap-northeast-2",
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_ACCESS_KEY_SECRET,
  },
});
export const download = async (filename) => {
  const command = new GetObjectCommand({
    Bucket: "kiteapp",
    Key: `booth/queue/${filename}`,
    region: process.env.AWS_REGION,
  });

  try {
    const response = await client.send(command);
    // 파일 내용을 버퍼로 변환하여 반환
    return await response.Body.transformToByteArray();
  } catch (err) {
    console.error(`Error downloading file ${filename}:`, err);
    throw err;
  }
};

export const remove = async (filenames) => {
  if (filenames.length === 0) {
    return;
  }

  const command = new DeleteObjectsCommand({
    Bucket: "kiteapp",
    Delete: {
      Objects: filenames.map((filename) => ({ Key: `booth/queue/${filename}` })),
      Quiet: false,
    },
  });
  try {
    const response = await client.send(command);
    if (response.Errors && response.Errors.length > 0) {
      console.error('Some files could not be deleted:', response.Errors);
    }
    return response;
  } catch (err) {
    console.error('Error in remove function:', err);
    throw err;
  }
};

export const upload = async (boothId, filename, data) => {
  const command = new PutObjectCommand({
    Bucket: "kiteapp",
    Key: `booth/${boothId}/${filename}`,
    Body: data,
  });
  try {
    const response = await client.send(command);
    return response;
  } catch (err) {
    console.error(`Error uploading ${filename} to booth/${boothId}/:`, err);
    throw err;
  }
};

export const moveObject = async (sourceKey, destinationKey) => {
  try {
    // 1. Copy the object to the new location
    await client.send(new CopyObjectCommand({
      Bucket: "kiteapp",
      CopySource: `/kiteapp/${sourceKey}`,
      Key: destinationKey,
    }));

    // 2. Delete the object from the old location
    await client.send(new DeleteObjectCommand({
      Bucket: "kiteapp",
      Key: sourceKey,
    }));

  } catch (err) {
    console.error(`Error moving ${sourceKey} to ${destinationKey}:`, err);
    throw err;
  }
};
