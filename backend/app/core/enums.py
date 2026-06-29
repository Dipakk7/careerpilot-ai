from enum import Enum

class StorageProvider(str, Enum):
    LOCAL = "LOCAL"
    AWS_S3 = "AWS_S3"
    AZURE_BLOB = "AZURE_BLOB"
    GCS = "GCS"

class ResumeStatus(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"
