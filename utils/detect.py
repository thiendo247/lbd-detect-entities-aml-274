from typing import Dict, List, Any

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def detect_aws_entities(comprehend_client, text: str) -> List[Dict]:
    """
    Sử dụng AWS Comprehend để detect entities cơ bản

    AWS Comprehend có thể phát hiện:
    - PERSON: Tên người
    - ORGANIZATION: Tên tổ chức
    - LOCATION: Địa điểm
    - COMMERCIAL_ITEM: Sản phẩm/dịch vụ
    - EVENT: Sự kiện
    - DATE: Ngày tháng
    - QUANTITY: Số lượng
    - TITLE: Chức danh

    Limit: AWS Comprehend giới hạn 5000 characters per request
    """
    try:
        # truncate text if too long (AWS Comprehend limit)
        text_to_analyze = text[:5000] if len(text) > 5000 else text

        # call AWS Comprehend
        response = comprehend_client.detect_entities(
            Text=text_to_analyze,
            LanguageCode='en'  # English language
        )

        # process và filter results
        entities = []
        for entity in response['Entities']:
            # chỉ lấy entities có confidence score cao
            if entity['Score'] >= 0.7:  # Threshold: 70% confidence
                processed_entity = {
                    'text': entity['Text'],
                    'type': entity['Type'],
                    'confidence': round(entity['Score'], 4),
                    'start_offset': entity['BeginOffset'],
                    'end_offset': entity['EndOffset'],
                    'source': 'aws_comprehend'
                }
                entities.append(processed_entity)

        # sort by confidence score (highest first)
        entities.sort(key=lambda x: x['confidence'], reverse=True)

        logger.info(f"AWS Comprehend found {len(entities)} high-confidence entities")
        return entities

    except Exception as e:
        logger.error(f"AWS Comprehend error: {str(e)}")
        return []
