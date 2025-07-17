import re
from datetime import datetime
from typing import Dict, List, Any
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)




# HELPER FUNCTIONS

def calculate_entity_confidence(entity_text: str, full_text: str) -> float:
    """
    Calculate confidence score cho custom entities dựa trên context
    """
    base_confidence = 0.8  # Base confidence for regex matches

    # Boost confidence if entity appears multiple times
    frequency = full_text.lower().count(entity_text.lower())
    frequency_boost = min(frequency * 0.05, 0.15)

    # Boost confidence for longer, more specific terms
    length_boost = min(len(entity_text.split()) * 0.02, 0.1)

    # Context boost - look for supporting keywords around entity
    context_keywords = ['sentenced', 'convicted', 'guilty', 'crime', 'illegal', 'federal']
    context_boost = 0
    for keyword in context_keywords:
        if keyword in full_text.lower():
            context_boost += 0.02

    final_confidence = min(base_confidence + frequency_boost + length_boost + context_boost, 0.98)
    return round(final_confidence, 3)


def get_context_window(text: str, start: int, end: int, window_size: int = 60) -> str:
    """
    Extract context window around entity
    """
    context_start = max(0, start - window_size)
    context_end = min(len(text), end + window_size)
    return text[context_start:context_end].strip()


def normalize_amount(amount_str: str) -> float:
    """
    Convert amount string to normalized numeric value
    """
    try:
        # Remove currency symbols and clean
        cleaned = re.sub(r'[^\d.,a-zA-Z]', '', amount_str).lower()

        # Extract numeric part
        numeric_match = re.search(r'[\d,]+(?:\.\d+)?', cleaned)
        if not numeric_match:
            return 0

        numeric_str = numeric_match.group().replace(',', '')
        base_value = float(numeric_str)

        # Apply multipliers
        if any(x in cleaned for x in ['billion', 'b']):
            return base_value * 1_000_000_000
        elif any(x in cleaned for x in ['million', 'm']):
            return base_value * 1_000_000
        elif any(x in cleaned for x in ['thousand', 'k']):
            return base_value * 1_000
        else:
            return base_value

    except (ValueError, AttributeError):
        return 0


def assess_amount_risk(amount: float) -> str:
    """
    Assess risk level based on amount
    """
    if amount >= 100_000_000:  # $100M+
        return 'CRITICAL'
    elif amount >= 10_000_000:  # $10M+
        return 'HIGH'
    elif amount >= 1_000_000:  # $1M+
        return 'MEDIUM'
    elif amount >= 100_000:  # $100K+
        return 'LOW'
    else:
        return 'MINIMAL'


def assess_org_risk_level(org_type: str) -> str:
    """
    Assess risk level for different organization types
    """
    high_risk_types = ['MAFIA', 'CRIME_FAMILY', 'CARTEL', 'ITALIAN_MAFIA']
    medium_risk_types = ['SYNDICATE', 'GANG', 'ASIAN_ORGANIZED_CRIME']

    if org_type in high_risk_types:
        return 'HIGH'
    elif org_type in medium_risk_types:
        return 'MEDIUM'
    else:
        return 'LOW'


def calculate_time_relevance(time_text: str, full_text: str) -> float:
    """
    Calculate relevance score for time references
    """
    base_score = 0.5

    # Higher score for longer time periods (suggests ongoing criminal enterprise)
    if 'year' in time_text.lower():
        years_match = re.search(r'\d+', time_text)
        if years_match:
            years = int(years_match.group())
            base_score += min(years * 0.05, 0.4)  # Max boost: 0.4

    # Boost for proximity to crime keywords
    crime_keywords = ['investigation', 'operation', 'scheme', 'conspiracy']
    for keyword in crime_keywords:
        if keyword in full_text.lower():
            base_score += 0.1

    return min(base_score, 1.0)


def remove_duplicate_entities(entities: List[Dict]) -> List[Dict]:
    """
    Remove duplicate entities based on text and position overlap
    """
    unique_entities = []

    for entity in entities:
        is_duplicate = False
        for existing in unique_entities:
            # Check for text similarity and position overlap
            if (entity['text'].lower() == existing['text'].lower() or
                    (entity['start'] < existing['end'] and entity['end'] > existing['start'])):
                is_duplicate = True
                # Keep the one with higher confidence
                if entity['confidence'] > existing['confidence']:
                    unique_entities.remove(existing)
                    unique_entities.append(entity)
                break

        if not is_duplicate:
            unique_entities.append(entity)

    return unique_entities


def remove_overlapping_amounts(amounts: List[Dict]) -> List[Dict]:
    """
    Remove overlapping monetary amount matches
    """
    amounts.sort(key=lambda x: x['start'])
    filtered_amounts = []

    for amount in amounts:
        is_overlapping = False
        for existing in filtered_amounts:
            if (amount['start'] < existing['end'] and amount['end'] > existing['start']):
                is_overlapping = True
                # Keep the one with higher normalized value
                if amount['normalized_value'] > existing['normalized_value']:
                    filtered_amounts.remove(existing)
                    filtered_amounts.append(amount)
                break

        if not is_overlapping:
            filtered_amounts.append(amount)

    return filtered_amounts


def validate_and_score_entities(aws_entities: List[Dict], custom_entities: List[Dict], text: str) -> List[Dict]:
    """
    Validate và enhance AWS Comprehend entities với additional scoring
    """
    validated_entities = []

    for entity in aws_entities:
        # Add additional AML-specific scoring
        aml_relevance = calculate_aml_relevance(entity, text)

        enhanced_entity = {
            **entity,
            'aml_relevance': aml_relevance,
            'risk_indicators': identify_risk_indicators(entity, text),
            'validation_status': 'VALIDATED' if entity['confidence'] > 0.8 else 'NEEDS_REVIEW'
        }

        validated_entities.append(enhanced_entity)

    return validated_entities


def calculate_aml_relevance(entity: Dict, text: str) -> float:
    """
    Calculate AML relevance score for AWS Comprehend entities
    """
    entity_text = entity['text'].lower()
    entity_type = entity['type']

    # Base relevance by entity type
    type_relevance = {
        'PERSON': 0.7,  # People involved in crimes
        'ORGANIZATION': 0.8,  # Companies/organizations
        'LOCATION': 0.6,  # Geographic relevance
        'DATE': 0.5,  # Timeline relevance
        'QUANTITY': 0.4,  # Numbers/amounts
        'EVENT': 0.7,  # Criminal events
        'TITLE': 0.6  # Job titles/positions
    }

    base_score = type_relevance.get(entity_type, 0.3)

    # Boost for crime-related keywords in proximity
    crime_context_keywords = [
        'sentenced', 'convicted', 'guilty', 'plea', 'charges', 'investigation',
        'fraud', 'laundering', 'criminal', 'illegal', 'conspiracy', 'racketeering'
    ]

    context_boost = 0
    for keyword in crime_context_keywords:
        if keyword in text.lower():
            context_boost += 0.05

    # Boost for financial crime indicators
    if any(term in entity_text for term in ['bank', 'financial', 'money', 'cash', 'account']):
        context_boost += 0.1

    final_score = min(base_score + context_boost, 1.0)
    return round(final_score, 3)


def identify_risk_indicators(entity: Dict, text: str) -> List[str]:
    """
    Identify specific risk indicators associated with entity
    """
    indicators = []
    entity_text = entity['text'].lower()

    # Check for various risk patterns
    if entity['type'] == 'PERSON':
        if any(term in text.lower() for term in ['defendant', 'accused', 'suspect']):
            indicators.append('CRIMINAL_SUBJECT')
        if any(term in text.lower() for term in ['judge', 'prosecutor', 'attorney']):
            indicators.append('LEGAL_OFFICIAL')

    elif entity['type'] == 'ORGANIZATION':
        if any(term in entity_text for term in ['crime', 'family', 'cartel']):
            indicators.append('CRIMINAL_ORGANIZATION')
        if any(term in entity_text for term in ['bank', 'financial', 'investment']):
            indicators.append('FINANCIAL_INSTITUTION')

    elif entity['type'] == 'LOCATION':
        # High-risk jurisdictions could be flagged here
        high_risk_locations = ['offshore', 'cayman', 'bermuda', 'panama']
        if any(term in entity_text for term in high_risk_locations):
            indicators.append('HIGH_RISK_JURISDICTION')

    return indicators