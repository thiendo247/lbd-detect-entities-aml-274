from utils.ner_helper import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def extract_financial_entities(text: str) -> List[Dict]:
    """
    Custom logic để trích xuất financial crime entities

    Phát hiện các từ khóa đặc thù cho:
    - Money laundering activities
    - Financial crimes
    - Criminal activities
    - Regulatory violations
    """
    entities = []

    # 1. MONEY LAUNDERING PATTERNS
    ml_patterns = {
        'structuring': [
            r'\bstructuring\b',
            r'\bsmurfing\b',
            r'\bbreaking\s+up\s+transactions\b',
            r'\bmultiple\s+small\s+deposits\b'
        ],
        'layering': [
            r'\blayering\b',
            r'\bcomplex\s+transactions\b',
            r'\bmultiple\s+accounts\b',
            r'\bshell\s+companies\b'
        ],
        'integration': [
            r'\bintegration\b',
            r'\blegitimate\s+business\b',
            r'\breal\s+estate\s+investments\b'
        ],
        'general_ml': [
            r'\bmoney\s+laundering\b',
            r'\banti[- ]money\s+laundering\b',
            r'\baml\b',
            r'\bcash\s+intensive\b',
            r'\bunusual\s+transactions\b'
        ]
    }

    # 2. FINANCIAL CRIME PATTERNS
    crime_patterns = {
        'racketeering': [
            r'\bracketeering\b',
            r'\brico\b',
            r'\borganized\s+crime\b'
        ],
        'fraud': [
            r'\bfraud\b',
            r'\bembezzlement\b',
            r'\bmisappropriation\b',
            r'\bponzi\s+scheme\b',
            r'\bpyramid\s+scheme\b'
        ],
        'tax_crimes': [
            r'\btax\s+evasion\b',
            r'\btax\s+fraud\b',
            r'\bunreported\s+income\b'
        ],
        'other_crimes': [
            r'\bextortion\b',
            r'\bbribery\b',
            r'\bcorruption\b',
            r'\bkickbacks\b',
            r'\billegal\s+gambling\b',
            r'\bdrug\s+trafficking\b'
        ]
    }

    # Combine all patterns
    all_patterns = {**ml_patterns, **crime_patterns}

    # Search for patterns in text
    for category, patterns in all_patterns.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = {
                    'text': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'type': 'FINANCIAL_CRIME',
                    'category': category,
                    'confidence': calculate_entity_confidence(match.group(), text),
                    'context': get_context_window(text, match.start(), match.end()),
                    'source': 'custom_regex'
                }
                entities.append(entity)

    # Remove duplicates and sort by confidence
    entities = remove_duplicate_entities(entities)
    entities.sort(key=lambda x: x['confidence'], reverse=True)

    logger.info(f"Custom extraction found {len(entities)} financial crime entities")
    return entities


def extract_monetary_amounts(text: str) -> List[Dict]:
    """
    Trích xuất các số tiền được đề cập trong text

    Patterns:
    - $1,000 / $1000
    - $1.5 million / $1.5M
    - $2 billion / $2B
    - USD 1,000
    - 1000 dollars
    """
    amounts = []

    # Multiple patterns for different formats
    money_patterns = [
        # Standard format: $1,000.00
        r'\$[\d,]+(?:\.\d{2})?',

        # Million/Billion format: $25 million, $1.5M
        r'\$[\d,.]+\s*(?:million|billion|thousand|M|B|K)\b',

        # USD format: USD 1,000
        r'USD\s*[\d,]+(?:\.\d{2})?',

        # Word format: 1000 dollars
        r'\b\d{1,3}(?:,\d{3})*\s*(?:dollars|USD)\b',

        # Mixed format: 25 million dollars
        r'\b\d+(?:\.\d+)?\s*(?:million|billion|thousand)\s*(?:dollars|USD)?\b'
    ]

    for pattern in money_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Get extended context around the amount
            context_start = max(0, match.start() - 50)
            context_end = min(len(text), match.end() + 50)
            context = text[context_start:context_end]

            # Calculate normalized value for comparison
            normalized_value = normalize_amount(match.group())

            amount_info = {
                'amount': match.group().strip(),
                'start': match.start(),
                'end': match.end(),
                'context': context,
                'normalized_value': normalized_value,
                'risk_level': assess_amount_risk(normalized_value),
                'source': 'regex_extraction'
            }
            amounts.append(amount_info)

    # Remove duplicates and overlapping matches
    amounts = remove_overlapping_amounts(amounts)

    # Sort by normalized value (highest first)
    amounts.sort(key=lambda x: x['normalized_value'], reverse=True)

    logger.info(f"Found {len(amounts)} monetary amounts")
    return amounts


def extract_time_references(text: str) -> List[Dict]:
    """
    Trích xuất references về thời gian liên quan đến financial crimes

    Important cho AML vì:
    - Thời gian hoạt động của criminal enterprise
    - Timeline của investigation
    - Statute of limitations
    """
    time_refs = []

    time_patterns = [
        # Year ranges: 2019-2023, 1998-2020
        (r'\b\d{4}-\d{4}\b', 'YEAR_RANGE'),

        # Specific dates: January 1, 2020 / 01/01/2020
        (
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        'SPECIFIC_DATE'),
        (r'\b\d{1,2}/\d{1,2}/\d{4}\b', 'SPECIFIC_DATE'),

        # Duration phrases: "over the past 25 years", "for 10 years"
        (r'over\s+the\s+past\s+\d+\s+(?:years?|months?|days?)', 'DURATION'),
        (r'for\s+(?:the\s+)?(?:past\s+)?\d+\s+(?:years?|months?|days?)', 'DURATION'),
        (r'during\s+the\s+(?:past\s+)?\d+\s+(?:years?|months?)', 'DURATION'),

        # Between dates: "between 2019 and 2020"
        (r'between\s+\d{4}\s+and\s+\d{4}', 'DATE_RANGE'),
        (r'from\s+\d{4}\s+to\s+\d{4}', 'DATE_RANGE'),

        # Relative time: "last year", "two months ago"
        (r'(?:last|this|next)\s+(?:year|month|week)', 'RELATIVE_TIME'),
        (r'\b\d+\s+(?:years?|months?|weeks?|days?)\s+ago\b', 'RELATIVE_TIME')
    ]

    for pattern, time_type in time_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            context_start = max(0, match.start() - 30)
            context_end = min(len(text), match.end() + 30)

            time_ref = {
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
                'type': time_type,
                'context': text[context_start:context_end],
                'relevance_score': calculate_time_relevance(match.group(), text),
                'source': 'regex_extraction'
            }
            time_refs.append(time_ref)

    # Sort by relevance score
    time_refs.sort(key=lambda x: x['relevance_score'], reverse=True)

    logger.info(f"Found {len(time_refs)} time references")
    return time_refs


def extract_criminal_orgs(text: str) -> List[Dict]:
    """
    Phát hiện references đến criminal organizations

    Rất quan trọng cho AML vì organized crime là high-risk indicator
    """
    orgs = []

    # Patterns for criminal organizations
    org_patterns = [
        # General terms
        (r'\b(?:mafia|cosa\s+nostra)\b', 'MAFIA'),
        (r'\b\w+\s+crime\s+family\b', 'CRIME_FAMILY'),
        (r'\b(?:cartel|drug\s+cartel)\b', 'CARTEL'),
        (r'\b(?:syndicate|criminal\s+syndicate)\b', 'SYNDICATE'),
        (r'\b(?:gang|criminal\s+gang)\b', 'GANG'),

        # Specific known organizations (có thể customize)
        (r'\b(?:lucchese|gambino|genovese|bonanno|colombo)\s+(?:crime\s+)?family\b', 'ITALIAN_MAFIA'),
        (r'\b(?:yakuza|triad)\b', 'ASIAN_ORGANIZED_CRIME'),
        (r'\b(?:russian\s+mafia|bratva)\b', 'EASTERN_EUROPEAN_CRIME'),

        # Business fronts often used by criminals
        (r'\b(?:shell\s+company|front\s+company)\b', 'BUSINESS_FRONT'),
        (r'\b(?:money\s+service\s+business|msb)\b', 'FINANCIAL_ENTITY')
    ]

    for pattern, org_type in org_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            context_start = max(0, match.start() - 40)
            context_end = min(len(text), match.end() + 40)

            org_info = {
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
                'type': 'CRIMINAL_ORGANIZATION',
                'subtype': org_type,
                'context': text[context_start:context_end],
                'risk_level': assess_org_risk_level(org_type),
                'source': 'custom_patterns'
            }
            orgs.append(org_info)

    logger.info(f"Found {len(orgs)} criminal organization references")
    return orgs
