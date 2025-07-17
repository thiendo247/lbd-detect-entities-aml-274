# lambda_ner_processor
"""
AWS Lambda Function cho Named Entity Recognition (NER)
Kết hợp AWS Comprehend + Custom Logic cho AML Analysis

Architecture:
- AWS Comprehend: NER cơ bản (PERSON, ORGANIZATION, LOCATION, etc.)
- Custom Logic: Trích xuất entities đặc thù cho Financial Crime
- RegEx Patterns: Phát hiện monetary amounts, time references
- Domain-specific: Criminal organizations, financial crime terms
"""

import boto3
import json
import re
from datetime import datetime
from typing import Dict, List, Any
import logging
from .ultils.detect import *
from .ultils.extract import  *

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Main Lambda handler function

    Input Event Structure:
    {
        "content": "article text content",
        "article_id": "unique_article_id",
        "source": "news_source"
    }

    Output:
    {
        "statusCode": 200,
        "ner_results": {
            "aws_entities": [...],      # AWS Comprehend results
            "custom_entities": [...],   # Custom financial crime entities
            "financial_amounts": [...], # Monetary amounts found
            "time_references": [...],   # Time/date references
            "criminal_organizations": [...] # Criminal org references
        }
    }
    """

    # Initialize AWS Comprehend client
    comprehend = boto3.client('comprehend', region_name='us-east-1')

    try:
        # Extract input data
        content = event.get('content', '')
        article_id = event.get('article_id', 'unknown')

        logger.info(f"Processing NER for article {article_id}, content length: {len(content)}")

        # Validate input
        if not content or len(content.strip()) < 10:
            raise ValueError("Content is empty or too short for analysis")

        # 1. AWS COMPREHEND NER ANALYSIS
        logger.info("Starting AWS Comprehend entity detection...")
        aws_entities = detect_aws_entities(comprehend, content)

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

        logger.info(f"NER processing completed successfully for {article_id}")

        return {
            'statusCode': 200,
            'ner_results': result
        }

    except Exception as e:
        logger.error(f"Error in NER processing: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'error_type': type(e).__name__
        }


