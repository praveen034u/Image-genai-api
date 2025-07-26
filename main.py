# requirements.txt (install these)
# fastapi
# uvicorn
# google-cloud-storage
# requests
# python-multipart

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from google.cloud import storage
from datetime import timedelta
import os
import base64
import uuid
import requests

app = FastAPI()

# Environment variables (or load securely)
GCS_BUCKET_NAME = "storry-teller-app-bucket"
GCS_CREDENTIALS_JSON = "storytelling-app-gkey.json"
STABILITY_API_KEY = "sk-BoycXa1AoUjT8HsqF277xOCZXfbtKLbzGOEQEYlQ58mjULxY"

# Set credentials for Google Cloud Storage
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCS_CREDENTIALS_JSON

# Upload image bytes to GCS and return signed URL
def upload_image_to_gcs(image_bytes: bytes, filename: str) -> str:
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        # Generate a signed URL valid for 15 minutes
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="GET"
        )
        return signed_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCS upload failed: {e}")

# Call Stability API and return image bytes
def generate_image(prompt: str) -> bytes:
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"

    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "application/json"
    }

    files = {
        "prompt": (None, prompt),
        "mode": (None, "text-to-image"),
        "output_format": (None, "png")
    }

    response = requests.post(url, files=files, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Stability API failed: {response.text}")

    image_base64 = response.json().get("image")
    if not image_base64:
        raise HTTPException(status_code=500, detail="No image returned from Stability API.")

    return base64.b64decode(image_base64)

# FastAPI endpoint
@app.post("/generate-image")
async def generate_and_upload_image(prompt: str):
    try:
        image_bytes = generate_image(prompt)
        filename = f"generated-images/{uuid.uuid4()}.png"
        image_url = upload_image_to_gcs(image_bytes, filename)
        return JSONResponse({"url": image_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
