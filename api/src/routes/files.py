from fastapi import APIRouter, UploadFile, File, HTTPException
from uuid import uuid4
from ..services.database import DatabaseService
from ..services.storage import StorageService
from ..models.file import FileMetadata

router = APIRouter()
db = DatabaseService()
storage = StorageService()

@router.post("/files/", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = None
):
    file_id = uuid4()
    try:
        size = await storage.store_file(
            file_id=file_id,
            file_data=file.file,
            file_name=file.filename,
            file_type='input'
        )
        # Create database entry
        # Implementation coming in next step
        return {"message": "File uploaded successfully", "file_id": str(file_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/test-encryption")
async def test_encryption():
    try:
        storage = StorageService()
        test_data = "Hello, encryption test!"
        encrypted = await storage.encryption.encrypt_data(test_data)
        decrypted = await storage.encryption.decrypt_data(encrypted)
        return {
            "status": "success",
            "original": test_data,
            "decrypted": decrypted.decode(),
            "encryption_working": test_data == decrypted.decode()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))