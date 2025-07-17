# input_validation.py - Add this to your Lambda function

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate_input_file(article_data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate input file structure and content

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # 1. REQUIRED FIELDS VALIDATION
    required_fields = ['id', 'title', 'content']
    for field in required_fields:
        if field not in article_data:
            errors.append(f"Missing required field: {field}")
        elif not article_data[field] or not str(article_data[field]).strip():
            errors.append(f"Required field '{field}' is empty")

    # 2. FIELD TYPE VALIDATION
    if 'id' in article_data:
        if not isinstance(article_data['id'], str):
            errors.append("Field 'id' must be a string")
        elif len(article_data['id']) > 200:
            errors.append("Field 'id' exceeds maximum length (200 characters)")

    if 'title' in article_data:
        if not isinstance(article_data['title'], str):
            errors.append("Field 'title' must be a string")
        elif len(article_data['title']) > 1000:
            errors.append("Field 'title' exceeds maximum length (1000 characters)")

    if 'content' in article_data:
        if not isinstance(article_data['content'], str):
            errors.append("Field 'content' must be a string")
        elif len(article_data['content']) < 50:
            errors.append("Field 'content' too short (minimum 50 characters)")
        elif len(article_data['content']) > 1000000:  # 1MB limit
            errors.append("Field 'content' exceeds maximum length (1MB)")

    # 3. OPTIONAL FIELDS VALIDATION
    if 'publish_date' in article_data:
        if not validate_date_format(article_data['publish_date']):
            errors.append("Field 'publish_date' must be in format YYYY-MM-DD")

    if 'url' in article_data:
        if not validate_url(article_data['url']):
            errors.append("Field 'url' must be a valid URL")

    if 'priority' in article_data:
        if article_data['priority'] not in ['high', 'medium', 'low']:
            errors.append("Field 'priority' must be one of: high, medium, low")

    if 'language' in article_data:
        if not validate_language_code(article_data['language']):
            errors.append("Field 'language' must be a valid language code (e.g., 'en', 'es')")

    if 'region' in article_data:
        if article_data['region'] not in ['US', 'EU', 'APAC', 'MULTI', 'OTHER']:
            errors.append("Field 'region' must be one of: US, EU, APAC, MULTI, OTHER")

    if 'jurisdiction' in article_data:
        if article_data['jurisdiction'] not in ['federal', 'state', 'international', 'local']:
            errors.append("Field 'jurisdiction' must be one of: federal, state, international, local")

    # 4. TAGS VALIDATION
    if 'tags' in article_data:
        if not isinstance(article_data['tags'], list):
            errors.append("Field 'tags' must be a list")
        elif len(article_data['tags']) > 50:
            errors.append("Field 'tags' exceeds maximum count (50)")
        else:
            for tag in article_data['tags']:
                if not isinstance(tag, str) or len(tag) > 100:
                    errors.append("Each tag must be a string with max 100 characters")

    # 5. NESTED OBJECT VALIDATION
    if 'crawl_metadata' in article_data:
        if not isinstance(article_data['crawl_metadata'], dict):
            errors.append("Field 'crawl_metadata' must be an object")

    # 6. BATCH PROCESSING VALIDATION
    if 'batch_id' in article_data and 'articles' in article_data:
        if not isinstance(article_data['articles'], list):
            errors.append("Field 'articles' in batch must be a list")
        elif len(article_data['articles']) > 100:
            errors.append("Batch size exceeds maximum (100 articles)")
        else:
            for i, article in enumerate(article_data['articles']):
                article_valid, article_errors = validate_input_file(article)
                if not article_valid:
                    errors.extend([f"Article {i + 1}: {error}" for error in article_errors])

    return len(errors) == 0, errors


def validate_date_format(date_str: str) -> bool:
    """Validate date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_url(url: str) -> bool:
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def validate_language_code(lang_code: str) -> bool:
    """Validate language code (ISO 639-1)"""
    valid_codes = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko', 'ar']
    return lang_code.lower() in valid_codes


def sanitize_input(article_data: Dict) -> Dict:
    """
    Sanitize input data to prevent injection attacks and normalize values
    """
    sanitized = {}

    for key, value in article_data.items():
        if isinstance(value, str):
            # Remove potentially dangerous characters
            sanitized_value = re.sub(r'[<>"\']', '', value)
            # Normalize whitespace
            sanitized_value = ' '.join(sanitized_value.split())
            sanitized[key] = sanitized_value
        elif isinstance(value, list):
            # Sanitize list items
            sanitized[key] = [sanitize_string(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, dict):
            # Recursively sanitize nested objects
            sanitized[key] = sanitize_input(value)
        else:
            sanitized[key] = value

    return sanitized


def sanitize_string(text: str) -> str:
    """Sanitize individual string values"""
    if not isinstance(text, str):
        return text

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\']', '', text)

    # Normalize whitespace
    text = ' '.join(text.split())

    return text.strip()


def enrich_metadata(article_data: Dict) -> Dict:
    """
    Add default metadata and enrich existing data
    """
    enriched = article_data.copy()

    # Add processing timestamp
    enriched['processing_timestamp'] = datetime.now().isoformat()

    # Add default values for optional fields
    if 'language' not in enriched:
        enriched['language'] = 'en'  # Default to English

    if 'priority' not in enriched:
        # Auto-detect priority based on content
        enriched['priority'] = auto_detect_priority(article_data.get('content', ''))

    if 'region' not in enriched:
        enriched['region'] = auto_detect_region(article_data.get('content', ''))

    if 'tags' not in enriched:
        enriched['tags'] = auto_generate_tags(article_data.get('content', ''))

    # Add content statistics
    if 'content' in enriched:
        enriched['content_stats'] = {
            'character_count': len(enriched['content']),
            'word_count': len(enriched['content'].split()),
            'sentence_count': len(re.findall(r'[.!?]+', enriched['content'])),
            'paragraph_count': len(enriched['content'].split('\n\n'))
        }

    return enriched


def auto_detect_priority(content: str) -> str:
    """Auto-detect priority based on content analysis"""
    content_lower = content.lower()

    # High priority indicators
    high_priority_terms = [
        'sentenced', 'convicted', 'arrested', 'charged', 'indicted',
        'million', 'billion', 'cartel', 'terrorism', 'sanctions',
        'federal', 'fbi', 'treasury', 'fincer'
    ]

    # Medium priority indicators
    medium_priority_terms = [
        'investigation', 'suspicious', 'compliance', 'violation',
        'fine', 'penalty', 'warning', 'advisory'
    ]

    high_count = sum(1 for term in high_priority_terms if term in content_lower)
    medium_count = sum(1 for term in medium_priority_terms if term in content_lower)

    if high_count >= 3:
        return 'high'
    elif high_count >= 1 or medium_count >= 2:
        return 'medium'
    else:
        return 'low'


def auto_detect_region(content: str) -> str:
    """Auto-detect region based on content analysis"""
    content_lower = content.lower()

    us_indicators = ['united states', 'u.s.', 'federal', 'fbi', 'treasury', 'fincer', 'doj']
    eu_indicators = ['europe', 'european', 'eu', 'euro', 'brexit', 'gdpr']
    apac_indicators = ['asia', 'china', 'japan', 'singapore', 'hong kong', 'australia']

    us_count = sum(1 for term in us_indicators if term in content_lower)
    eu_count = sum(1 for term in eu_indicators if term in content_lower)
    apac_count = sum(1 for term in apac_indicators if term in content_lower)

    if us_count > eu_count and us_count > apac_count:
        return 'US'
    elif eu_count > apac_count:
        return 'EU'
    elif apac_count > 0:
        return 'APAC'
    else:
        return 'OTHER'


def auto_generate_tags(content: str) -> List[str]:
    """Auto-generate tags based on content analysis"""
    content_lower = content.lower()
    tags = []

    # Financial crime terms
    crime_terms = {
        'money laundering': ['money laundering', 'laundering', 'aml'],
        'fraud': ['fraud', 'fraudulent', 'scam'],
        'terrorism financing': ['terrorism', 'terrorist', 'financing'],
        'sanctions': ['sanctions', 'sanctioned', 'ofac'],
        'cybercrime': ['cyber', 'hacking', 'ransomware'],
        'drug trafficking': ['drug', 'narcotics', 'trafficking'],
        'organized crime': ['mafia', 'cartel', 'organized crime'],
        'corruption': ['corruption', 'bribery', 'kickback'],
        'tax evasion': ['tax evasion', 'tax fraud'],
        'cryptocurrency': ['bitcoin', 'crypto', 'blockchain']
    }

    for tag, terms in crime_terms.items():
        if any(term in content_lower for term in terms):
            tags.append(tag)

    # Regulatory terms
    regulatory_terms = {
        'compliance': ['compliance', 'regulatory'],
        'investigation': ['investigation', 'investigating'],
        'enforcement': ['enforcement', 'penalty', 'fine'],
        'suspicious activity': ['suspicious', 'sar', 'ctr']
    }

    for tag, terms in regulatory_terms.items():
        if any(term in content_lower for term in terms):
            tags.append(tag)

    return tags[:10]  # Limit to 10 tags


# Updated download_and_parse_article function with validation
def download_and_parse_article(s3_client, bucket_name: str, object_key: str) -> Optional[Dict]:
    """
    Download file from S3 and parse JSON content with validation
    """
    try:
        # Download object from S3
        logger.info(f"Downloading {bucket_name}/{object_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')

        # Parse JSON
        article_data = json.loads(content)

        # Validate input structure
        is_valid, errors = validate_input_file(article_data)
        if not is_valid:
            logger.error(f"Validation errors for {object_key}: {errors}")
            return None

        # Sanitize input
        sanitized_data = sanitize_input(article_data)

        # Enrich metadata
        enriched_data = enrich_metadata(sanitized_data)

        logger.info(f"Successfully parsed and validated article: {enriched_data.get('id', 'unknown')}")
        return enriched_data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error for {object_key}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error downloading/parsing {object_key}: {str(e)}")
        return None