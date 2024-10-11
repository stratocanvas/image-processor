import { GetObjectCommand, PutObjectCommand, DeleteObjectsCommand, S3Client, CopyObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
const client = new S3Client({});
export const download = async (filename) => {
  const command = new GetObjectCommand({
    Bucket: process.env.BUCKET_NAME,
    Key: `${process.env.QUEUE_PATH}/${filename}`,
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
    Bucket: process.env.BUCKET_NAME,
    Delete: {
      Objects: filenames.map((filename) => ({ Key: `${process.env.QUEUE_PATH}/${filename}` })),
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
    Bucket: process.env.BUCKET_NAME,
    Key: `${process.env.BOOTH_PATH}/${boothId}/${filename}`,
    Body: data,
  });
  try {
    const response = await client.send(command);
    return response;
  } catch (err) {
    console.error(`Error uploading ${filename}:`, err);
    throw err;
  }
};

export const moveObject = async (sourceKey, destinationKey) => {
  try {
    await client.send(new CopyObjectCommand({
      Bucket: process.env.BUCKET_NAME,
      CopySource: `/${process.env.BUCKET_NAME}/${sourceKey}`,
      Key: destinationKey,
    }));

    await client.send(new DeleteObjectCommand({
      Bucket: process.env.BUCKET_NAME,
      Key: sourceKey,
    }));

  } catch (err) {
    console.error(`Error moving ${sourceKey} to ${destinationKey}:`, err);
    throw err;
  }
};
