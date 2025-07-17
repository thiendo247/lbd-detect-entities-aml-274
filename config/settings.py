import os


class Config:
    """Configuration for Lambda function with S3 structure"""

    # S3 Bucket and path structure
    # <mft-data-serving-bucket> / <project_id> / write|read / <table or report name> / data|metadata / <date=yyyy-mm-dd> / <file>

    BUCKET_NAME = os.environ.get('MFT_DATA_SERVING_BUCKET', 'mft-data-serving-fss-to-client')

    # Path templates - will be filled with actual values
    # Format: {project_id}/{stage}/{table_name}/{data_type}/{date}/{filename}
    WRITE_DATA_PATH_TEMPLATE = "{project_id}/write/{table_name}/data/date={date}/"
    WRITE_METADATA_PATH_TEMPLATE = "{project_id}/write/{table_name}/metadata/date={date}/"
    READ_DATA_PATH_TEMPLATE = "{project_id}/read/{table_name}/data/date={date}/"
    READ_METADATA_PATH_TEMPLATE = "{project_id}/read/{table_name}/metadata/date={date}/"

    # Default values (can be overridden by environment variables or metadata)
    DEFAULT_PROJECT_ID = os.environ.get('DEFAULT_PROJECT_ID', 'default_project')
    DEFAULT_TABLE_NAME = os.environ.get('DEFAULT_TABLE_NAME', 'default_table')

    # Supported file extensions
    SUPPORTED_DATA_EXTENSIONS = ['.csv', '.txt']
    METADATA_EXTENSION = '.json'

    # Logging level
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # AWS Region
    AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'ap-southeast-1')

    # Processing settings
    MAX_RETRY_ATTEMPTS = 3
    BATCH_SIZE = 10

    @staticmethod
    def get_write_data_path(project_id: str, table_name: str, date: str) -> str:
        """Generate write data path for given parameters"""
        return Config.WRITE_DATA_PATH_TEMPLATE.format(
            project_id=project_id,
            table_name=table_name,
            date=date
        )

    @staticmethod
    def get_write_metadata_path(project_id: str, table_name: str, date: str) -> str:
        """Generate write metadata path for given parameters"""
        return Config.WRITE_METADATA_PATH_TEMPLATE.format(
            project_id=project_id,
            table_name=table_name,
            date=date
        )

    @staticmethod
    def get_read_data_path(project_id: str, table_name: str, date: str) -> str:
        """Generate read data path for given parameters"""
        return Config.READ_DATA_PATH_TEMPLATE.format(
            project_id=project_id,
            table_name=table_name,
            date=date
        )

    @staticmethod
    def get_read_metadata_path(project_id: str, table_name: str, date: str) -> str:
        """Generate read metadata path for given parameters"""
        return Config.READ_METADATA_PATH_TEMPLATE.format(
            project_id=project_id,
            table_name=table_name,
            date=date
        )

    @staticmethod
    def extract_path_components(s3_key: str) -> dict:
        """
        Extract components from S3 key
        Example: project1/write/user_events/metadata/date=2025-05-29/manifest.json
        Returns: {
            'project_id': 'project1',
            'stage': 'write',
            'table_name': 'user_events',
            'data_type': 'metadata',
            'date': '2025-05-29',
            'filename': 'manifest.json'
        }
        """
        parts = s3_key.split('/')

        if len(parts) < 6:
            raise ValueError(f"Invalid S3 key format: {s3_key}")

        # Extract date from date=yyyy-mm-dd format
        date_part = parts[4]  # date=yyyy-mm-dd
        if date_part.startswith('date='):
            date = date_part.replace('date=', '')
        else:
            date = date_part

        return {
            'project_id': parts[0],
            'stage': parts[1],  # write or read
            'table_name': parts[2],
            'data_type': parts[3],  # data or metadata
            'date': date,
            'filename': parts[5] if len(parts) > 5 else ''
        }