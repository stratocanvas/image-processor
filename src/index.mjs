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
    console.log(record.body)
    const message = JSON.parse(record.body);    
    console.log(message)
    const processedImages = await processImages(message);
    
    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Record processed successfully'
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
