from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from google.cloud import storage
from datetime import timedelta
import os
import base64
import uuid
import requests
import json
import tempfile
import logging

logging.basicConfig(level=logging.INFO)
logging.info("Starting FastAPI app")

app = FastAPI()


# ENV VARS
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "storry-teller-app-bucket")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")

# ✅ Dynamically set credentials from env variable (base64-encoded JSON or raw JSON)
GCP_SA_KEY = os.getenv("GCP_SA_KEY")

# Validate env vars
if not GCP_BUCKET_NAME:
    raise ValueError("GCP_BUCKET_NAME environment variable is not set.")
if not STABILITY_API_KEY:
    raise ValueError("STABILITY_API_KEY environment variable is not set.")

def get_gcp_credentials():
    try:
        key_data = (
            GCP_SA_KEY if GCP_SA_KEY.strip().startswith("{")
            else base64.b64decode(GCP_SA_KEY).decode("utf-8")
        )
        creds_dict = json.loads(key_data)
        return service_account.Credentials.from_service_account_info(creds_dict)
    except Exception as e:
        raise RuntimeError(f"Invalid GCP_SA_KEY format: {e}")
        
# 📤 Upload image bytes to GCS and return signed URL
def upload_image_to_gcs(image_bytes: bytes, filename: str) -> str:
    try:
        credentials = get_gcp_credentials()
        client = storage.Client(credentials=credentials)
        bucket = client.bucket(GCP_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        signed_url = blob.generate_signed_url(
            credentials=credentials,
            version="v4",
            expiration=timedelta(minutes=15),
            method="GET"
        )
        return signed_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCS upload failed: {e}")

# 🎨 Call Stability API
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

# 🚀 FastAPI endpoint
@app.post("/generate-image")
async def generate_and_upload_image(prompt: str):
    try:
        image_bytes = generate_image(prompt)
        filename = f"generated-images/{uuid.uuid4()}.png"
        image_url = upload_image_to_gcs(image_bytes, filename)
        return JSONResponse({"url": image_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
    
# Health check endpoint
@app.get("/health") 
async def health_check():
    return {"status": "ok"}
