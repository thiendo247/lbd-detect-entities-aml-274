import json
import boto3

from utils.detect import *
from utils.extract import  *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def is_valid_file_for_processing(object_key: str) -> bool:
    """
    Check if the S3 object should be processed

    Valid files:
    - JSON files in raw-data/ folder
    - Article files (not metadata or other files)
    - Not already processed files
    """

    # Must be JSON file
    if not object_key.lower().endswith('.json'):
        return False

    # Must be in raw-data folder
    if not object_key.startswith('raw-data/'):
        return False

    # Skip already processed files
    if 'processed/' in object_key or 'results/' in object_key:
        return False

    # Skip system/metadata files
    skip_patterns = ['_metadata', '_temp', '_backup', '.tmp']
    if any(pattern in object_key.lower() for pattern in skip_patterns):
        return False

    logger.info(f"File {object_key} is valid for processing")
    return True


def download_and_parse_article(s3_client, bucket_name: str, object_key: str) -> Dict:
    """
    Download file from S3 and parse JSON content

    Expected JSON structure:
    {
        "id": "article_id",
        "title": "Article title",
        "content": "Article content text",
        "source": "news_source",
        "publish_date": "2024-01-15",
        "url": "original_url"
    }
    """
    try:
        # Download object from S3
        logger.info(f"Downloading {bucket_name}/{object_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')

        # Parse JSON
        article_data = json.loads(content)

        # Validate required fields
        required_fields = ['content']
        for field in required_fields:
            if field not in article_data:
                raise ValueError(f"Missing required field: {field}")

        # Add metadata if missing
        if 'id' not in article_data:
            article_data['id'] = extract_article_id_from_key(object_key)

        if 'timestamp' not in article_data:
            article_data['timestamp'] = datetime.now().isoformat()

        logger.info(f"Successfully parsed article: {article_data.get('id', 'unknown')}")
        return article_data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error for {object_key}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error downloading/parsing {object_key}: {str(e)}")
        return None


def extract_article_id_from_key(object_key: str) -> str:
    """
    Extract article ID from S3 object key

    Examples:
    raw-data/2024/01/15/article123.json -> article123
    raw-data/news/20240115_villani_case.json -> 20240115_villani_case
    """
    # Get filename without extension
    filename = object_key.split('/')[-1]
    article_id = filename.replace('.json', '')

    return article_id


def process_ner_analysis(comprehend_client, content: str, article_id: str, source: str) -> Dict:
    """
    Process NER analysis (same logic as before, just extracted to separate function)
    """

    # 1. AWS COMPREHEND NER ANALYSIS
    logger.info("Starting AWS Comprehend entity detection...")
    aws_entities = detect_aws_entities(comprehend_client, content)

    # 2. CUSTOM FINANCIAL CRIME ENTITY EXTRACTION
    logger.info("Starting custom entity extraction...")
    custom_entities = extract_financial_entities(content)

    # 3. MONETARY AMOUNT EXTRACTION
    logger.info("Extracting financial amounts...")
    financial_amounts = extract_monetary_amounts(content)

    # 4. TIME REFERENCE EXTRACTION
    logger.info("Extracting time references...")
    time_references = extract_time_references(content)

    # 5. CRIMINAL ORGANIZATION DETECTION
    logger.info("Detecting criminal organizations...")
    criminal_organizations = extract_criminal_orgs(content)

    # 6. ENTITY VALIDATION & SCORING
    validated_entities = validate_and_score_entities(
        aws_entities, custom_entities, content
    )

    # Combine all results
    result = {
        'aws_entities': validated_entities,
        'custom_entities': custom_entities,
        'financial_amounts': financial_amounts,
        'time_references': time_references,
        'criminal_organizations': criminal_organizations,
        'processing_metadata': {
            'article_id': article_id,
            'source': source,
            'processed_at': datetime.now().isoformat(),
            'content_length': len(content),
            'total_entities_found': (
                    len(validated_entities) +
                    len(custom_entities) +
                    len(financial_amounts) +
                    len(criminal_organizations)
            )
        }
    }

    return result


def save_results_to_s3(s3_client, bucket_name: str, original_key: str, ner_results: Dict):
    """
    Save NER results back to S3 in processed folder

    Structure:
    raw-data/2024/01/15/article123.json -> processed-data/2024/01/15/article123_ner.json
    """
    try:
        # Generate output key
        # Replace 'raw-data' with 'processed-data' and add '_ner' suffix
        output_key = original_key.replace('raw-data/', 'processed-data/')
        output_key = output_key.replace('.json', '_ner.json')

        # Add processing timestamp to filename for versioning
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_key = output_key.replace('_ner.json', f'_ner_{timestamp}.json')

        # Convert results to JSON string
        results_json = json.dumps(ner_results, indent=2, default=str)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=results_json,
            ContentType='application/json',
            Metadata={
                'original_file': original_key,
                'processing_type': 'ner_analysis',
                'processed_at': datetime.now().isoformat()
            }
        )

        logger.info(f"Saved NER results to: {bucket_name}/{output_key}")

        # Also save to DynamoDB if table exists
        save_to_dynamodb(ner_results)

    except Exception as e:
        logger.error(f"Error saving results to S3: {str(e)}")
        # Don't raise exception - processing was successful, just saving failed


def save_to_dynamodb(ner_results: Dict):
    """
    Optionally save key results to DynamoDB for quick querying
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table_name = 'aml-analysis-results'  # From environment variable

        table = dynamodb.Table(table_name)

        # Prepare DynamoDB item (only key fields to avoid size limits)
        item = {
            'article_id': ner_results['processing_metadata']['article_id'],
            'timestamp': ner_results['processing_metadata']['processed_at'],
            'source': ner_results['processing_metadata']['source'],
            'total_entities': ner_results['processing_metadata']['total_entities_found'],
            'high_risk_entities': count_high_risk_entities(ner_results),
            'financial_amounts_count': len(ner_results['financial_amounts']),
            'criminal_orgs_count': len(ner_results['criminal_organizations']),
            'processing_status': 'COMPLETED'
        }

        table.put_item(Item=item)
        logger.info(f"Saved summary to DynamoDB for article {item['article_id']}")

    except Exception as e:
        logger.warning(f"Failed to save to DynamoDB: {str(e)}")
        # Don't fail the entire process if DynamoDB save fails


def count_high_risk_entities(ner_results: Dict) -> int:
    """
    Count high-risk entities for summary statistics
    """
    high_risk_count = 0

    # Count financial crime entities
    high_risk_count += len(ner_results['custom_entities'])

    # Count criminal organizations
    high_risk_count += len(ner_results['criminal_organizations'])

    # Count high-value financial amounts
    for amount in ner_results['financial_amounts']:
        if amount.get('risk_level') in ['HIGH', 'CRITICAL']:
            high_risk_count += 1

    return high_risk_count

# Additional error handling for S3 operations
def handle_s3_errors(func):
    """Decorator for S3 error handling"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"S3 object not found: {args}")
                return None
            elif error_code == 'AccessDenied':
                logger.error(f"S3 access denied: {args}")
                return None
            else:
                logger.error(f"S3 error {error_code}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected S3 error: {str(e)}")
            raise

    return wrapper