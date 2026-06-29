import uuid
import os
from pathlib import Path
from fastapi import HTTPException
from app.core.config import settings
from app.core.enums import StorageProvider

def get_storage_path(
    provider: StorageProvider = StorageProvider.LOCAL
) -> Path:
    """Get the storage path directory and ensure it exists."""
    if provider == StorageProvider.LOCAL:
        path = Path(settings.LOCAL_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path
    raise HTTPException(status_code=400, detail=f"Unsupported storage provider: {provider}")

def generate_filename(
    user_id: uuid.UUID,
    original_filename: str
) -> str:
    """Generate a collision-free and sanitized filename using the user_id and a random UUID."""
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower().strip(".")
    # Ensure extension is valid; default to pdf if empty for security/consistency
    if not ext:
        ext = "pdf"
    
    unique_id = uuid.uuid4()
    return f"{user_id}_{unique_id}.{ext}"

async def save_file(
    file_content: bytes,
    stored_filename: str,
    provider: StorageProvider = StorageProvider.LOCAL
) -> tuple[str, int]:
    """Save the file content to storage and return its absolute path and size."""
    file_size_bytes = len(file_content)
    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    storage_path = get_storage_path(provider)
    file_path = storage_path / stored_filename
    
    try:
        # Write content to local file
        with open(file_path, "wb") as f:
            f.write(file_content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
        
    return str(file_path.resolve().absolute()), file_size_bytes

def delete_file(
    file_path: str,
    provider: StorageProvider = StorageProvider.LOCAL
) -> bool:
    """Delete a file from the filesystem. Returns True on success, False if file not found or deletion failed."""
    if provider == StorageProvider.LOCAL:
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception:
            return False
    return False
