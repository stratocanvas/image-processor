import { update } from './utils/net/rpc.mjs';
import { processImages } from './utils/process.mjs';

// Lambda handler
export const handler = async (event) => {
  try {
    const results = await Promise.all(event.Records.map(processRecord));
    return results;
  } catch (error) {
    console.error('Fatal error occurred:', error);
    return [{
      statusCode: 500,
      body: JSON.stringify({
        error: 'Fatal error occurred',
        details: error.message,
      }),
    }];
  }
};

// Process SQS record
async function processRecord(record) {
  try {
    const message = JSON.parse(record.body);    
    const processedImages = await processImages(message);
    
    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Record processed successfully',
        processedImages,
      }),
    };
  } catch (error) {
    console.error('Error processing record:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: 'Failed to process record',
        details: error.message,
      }),
    };
  }
}

// Test code (can be moved to a separate test file)
const SQS_MESSAGE = {
  "booth_id": 2,
  "images": {
    "thumbnail": "https://kiteapp.s3.ap-northeast-2.amazonaws.com/booth/queue/GZdTVY2a8AA9b_x.jpg",
    "article": [
      "https://kiteapp.s3.ap-northeast-2.amazonaws.com/booth/queue/GYzflWKakAAeblS.jpg",
    ],
    "product": [
      "https://kiteapp.s3.ap-northeast-2.amazonaws.com/booth/queue/GZgr4gnacAI34VA.jpg",
      "https://kiteapp.s3.ap-northeast-2.amazonaws.com/booth/queue/GZhPzD3aAAIsyoB.jpg",
      "https://kiteapp.s3.ap-northeast-2.amazonaws.com/booth/queue/GZhYFB-awAAbv8B.jpg"
    ]
  }
};

handler({
  "Records": [
    {
      "messageId": "19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
      "receiptHandle": "MessageReceiptHandle",
      "body": JSON.stringify(SQS_MESSAGE),
      "attributes": {
        "ApproximateReceiveCount": "1",
        "SentTimestamp": "1523232000000",
        "SenderId": "123456789012",
        "ApproximateFirstReceiveTimestamp": "1523232000001"
      },
      "messageAttributes": {},
      "md5OfBody": "{{{md5_of_body}}}",
      "eventSource": "aws:sqs",
      "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:MyQueue",
      "awsRegion": "us-east-1"
    }
  ]
});