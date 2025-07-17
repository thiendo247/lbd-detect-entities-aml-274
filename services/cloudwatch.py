import boto3

cloudwatch = boto3.client('cloudwatch')


def publish_metrics(article_id, processing_time, entities_found, status):
    """Publish custom metrics to CloudWatch"""

    metrics = [
        {
            'MetricName': 'ProcessingTime',
            'Value': processing_time,
            'Unit': 'Seconds',
            'Dimensions': [
                {'Name': 'FunctionName', 'Value': 'aml-ner-processor'}
            ]
        },
        {
            'MetricName': 'EntitiesFound',
            'Value': entities_found,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'EntityType', 'Value': 'Total'}
            ]
        },
        {
            'MetricName': 'ProcessingStatus',
            'Value': 1 if status == 'SUCCESS' else 0,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'Status', 'Value': status}
            ]
        }
    ]

    cloudwatch.put_metric_data(
        Namespace='AML/NLP',
        MetricData=metrics
    )