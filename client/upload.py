"""
UGC Engine - R2 Storage Module
================================
Upload/download files to Cloudflare R2 (S3-compatible).
"""

import os
import boto3
from botocore.config import Config
from config import R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

def upload_file_to_r2(r2_client, local_path, r2_key, content_type=None):
    """Upload a file to R2"""
    if content_type is None:
        ext = os.path.splitext(local_path)[1].lower()
        ct_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".json": "application/json",
        }
        content_type = ct_map.get(ext, "application/octet-stream")

    r2_client.upload_file(
        local_path, R2_BUCKET, r2_key,
        ExtraArgs={"ContentType": content_type},
    )
    return r2_key

def download_file_from_r2(r2_client, r2_key, local_path):
    """Download a file from R2"""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    r2_client.download_file(R2_BUCKET, r2_key, local_path)
    return local_path

def list_files(r2_client, prefix=""):
    """List files in R2 bucket"""
    resp = r2_client.list_objects_v2(Bucket=R2_BUCKET, Prefix=prefix, MaxKeys=100)
    return [obj["Key"] for obj in resp.get("Contents", [])]

def get_presigned_url(r2_client, r2_key, expires=3600):
    """Get presigned download URL"""
    return r2_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET, "Key": r2_key},
        ExpiresIn=expires,
    )


if __name__ == "__main__":
    r2 = get_r2_client()
    print("R2 Connection test:")
    try:
        files = list_files(r2)
        print(f"  Bucket '{R2_BUCKET}' has {len(files)} files")
        for f in files[:10]:
            print(f"    {f}")
    except Exception as e:
        print(f"  Error: {e}")
        print("  Check your R2 credentials in config.py")
