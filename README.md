# lbd-detect-entities-aml-274

----

## Deployment
- Severless local: 
> serverless offline
- Serverless build lambda function: 
> serverless deploy --stage dev --verbose


---
# lambda_function.py
"""
AWS Lambda Function cho Named Entity Recognition (NER)
Kết hợp AWS Comprehend + Custom Logic cho AML Analysis

Architecture:
- AWS Comprehend: NER cơ bản (PERSON, ORGANIZATION, LOCATION, etc.)
- Custom Logic: Trích xuất entities đặc thù cho Financial Crime
- RegEx Patterns: Phát hiện monetary amounts, time references
- Domain-specific: Criminal organizations, financial crime terms
"""
