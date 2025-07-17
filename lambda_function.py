import boto3
from urllib.parse import unquote_plus

from utils.process_support import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Updated Lambda handler for S3 event notifications

    S3 Event Structure:
    {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "your-bucket"},
                    "object": {"key": "raw-data/2024/01/15/article123.json"}
                }
            }
        ]
    }
    """

    # Initialize AWS clients
    s3 = boto3.client('s3')
    comprehend = boto3.client('comprehend', region_name='us-east-1')

    results = []

    try:
        # Process each S3 record in the event
        for record in event.get('Records', []):
            # Validate this is an S3 event
            if record.get('eventSource') != 'aws:s3':
                logger.warning(f"Skipping non-S3 event: {record.get('eventSource')}")
                continue

            # Extract S3 bucket and object information
            bucket_name = record['s3']['bucket']['name']
            object_key = unquote_plus(record['s3']['object']['key'])
            event_name = record.get('eventName', '')

            logger.info(f"Processing S3 event: {event_name} for {bucket_name}/{object_key}")

            # Only process ObjectCreated events
            if not event_name.startswith('ObjectCreated'):
                logger.info(f"Skipping event type: {event_name}")
                continue

            # Filter by file type/path (only process JSON files in raw-data folder)
            if not is_valid_file_for_processing(object_key):
                logger.info(f"Skipping file: {object_key} (not a valid article file)")
                continue

            # Download and parse file from S3
            article_data = download_and_parse_article(s3, bucket_name, object_key)
            if not article_data:
                logger.error(f"Failed to parse article from {object_key}")
                continue

            # Extract article content and metadata
            content = article_data.get('content', '')
            article_id = article_data.get('id', extract_article_id_from_key(object_key))
            source = article_data.get('source', 'unknown')

            logger.info(f"Processing article {article_id}, content length: {len(content)}")

            # Validate content
            if not content or len(content.strip()) < 10:
                logger.warning(f"Content too short for article {article_id}")
                continue

            # Process NER analysis (same as before)
            ner_result = process_ner_analysis(comprehend, content, article_id, source)

            # Add S3 metadata to results
            ner_result['s3_metadata'] = {
                'bucket': bucket_name,
                'object_key': object_key,
                'event_name': event_name,
                'processed_at': datetime.now().isoformat()
            }

            # Save results back to S3 processed folder
            save_results_to_s3(s3, bucket_name, object_key, ner_result)

            results.append({
                'article_id': article_id,
                'status': 'SUCCESS',
                'object_key': object_key,
                'entities_found': ner_result['processing_metadata']['total_entities_found']
            })

        logger.info(f"Successfully processed {len(results)} articles")

        return {
            'statusCode': 200,
            'message': f'Successfully processed {len(results)} articles',
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in S3 event processing: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'error_type': type(e).__name__
        }

