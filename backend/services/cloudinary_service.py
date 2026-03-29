import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os

load_dotenv()

cloudinary.config(url=os.getenv("CLOUDINARY_URL"), secure=True)

async def upload_image(file_bytes: bytes, folder: str = "junglegap", public_id: str = None) -> str:
    options = { "folder": folder, "overwrite": True }
    if public_id:
        options["public_id"] = public_id
    result = cloudinary.uploader.upload(file_bytes, **options)
    return result["secure_url"]

async def delete_image(public_id: str):
    cloudinary.uploader.destroy(public_id)