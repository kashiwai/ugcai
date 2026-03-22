"""
UGC Engine - Auto Posting Module
==================================
Posts completed videos to TikTok / Instagram / X.

TikTok: Uses TikTok Content Posting API (requires Business Account)
Instagram: Uses Meta Graph API (requires Business Account + Meta App)
X: Uses X API v2 (requires Developer Account)

For initial setup, use Buffer/Later as a simpler alternative.
This module is for full automation at scale.
"""

import os
import json
import time
import requests
from pathlib import Path
from config import CHARACTERS

# ---- TikTok Posting ----

class TikTokPoster:
    """Post videos to TikTok via Content Posting API"""

    def __init__(self, access_token):
        self.token = access_token
        self.base_url = "https://open.tiktokapis.com/v2"

    def init_upload(self, video_size):
        """Initialize video upload to get upload URL"""
        resp = requests.post(
            f"{self.base_url}/post/publish/inbox/video/init/",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,
                    "total_chunk_count": 1,
                }
            },
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return data["publish_id"], data["upload_url"]

    def upload_video(self, upload_url, video_path):
        """Upload video file to TikTok"""
        video_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            resp = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{video_size-1}/{video_size}",
                    "Content-Type": "video/mp4",
                },
                data=f,
            )
        resp.raise_for_status()
        return True

    def publish(self, publish_id, caption, hashtags=None):
        """Publish uploaded video with caption"""
        title = caption
        if hashtags:
            title += " " + hashtags

        resp = requests.post(
            f"{self.base_url}/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={
                "post_info": {
                    "title": title[:2200],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": 0,
                },
            },
        )
        resp.raise_for_status()
        return resp.json()

    def post_video(self, video_path, caption, hashtags=None):
        """Full flow: init → upload → publish"""
        video_size = os.path.getsize(video_path)
        publish_id, upload_url = self.init_upload(video_size)
        self.upload_video(upload_url, video_path)
        return self.publish(publish_id, caption, hashtags)


# ---- Instagram Posting (via Meta Graph API) ----

class InstagramPoster:
    """Post Reels to Instagram via Meta Graph API"""

    def __init__(self, access_token, ig_user_id):
        self.token = access_token
        self.user_id = ig_user_id
        self.base_url = "https://graph.facebook.com/v19.0"

    def create_reel(self, video_url, caption):
        """
        Create Instagram Reel.
        Note: video_url must be a publicly accessible URL (use R2 presigned URL)
        """
        resp = requests.post(
            f"{self.base_url}/{self.user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "access_token": self.token,
            },
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]

        # Wait for processing
        for _ in range(30):
            status = requests.get(
                f"{self.base_url}/{container_id}",
                params={"fields": "status_code", "access_token": self.token},
            ).json()
            if status.get("status_code") == "FINISHED":
                break
            time.sleep(5)

        # Publish
        pub_resp = requests.post(
            f"{self.base_url}/{self.user_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.token},
        )
        pub_resp.raise_for_status()
        return pub_resp.json()

    def create_carousel(self, image_urls, caption):
        """Create carousel post (for comparison/info content)"""
        children = []
        for url in image_urls:
            resp = requests.post(
                f"{self.base_url}/{self.user_id}/media",
                data={
                    "image_url": url,
                    "is_carousel_item": True,
                    "access_token": self.token,
                },
            )
            resp.raise_for_status()
            children.append(resp.json()["id"])

        # Create carousel container
        resp = requests.post(
            f"{self.base_url}/{self.user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "caption": caption[:2200],
                "children": ",".join(children),
                "access_token": self.token,
            },
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]

        # Publish
        pub_resp = requests.post(
            f"{self.base_url}/{self.user_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.token},
        )
        pub_resp.raise_for_status()
        return pub_resp.json()


# ---- X (Twitter) Posting ----

class XPoster:
    """Post to X (Twitter) via API v2"""

    def __init__(self, bearer_token, api_key, api_secret,
                 access_token, access_token_secret):
        self.bearer = bearer_token
        # For media upload, need OAuth 1.0a
        from requests_oauthlib import OAuth1
        self.auth = OAuth1(api_key, api_secret, access_token, access_token_secret)

    def upload_media(self, video_path):
        """Upload video to X media endpoint (chunked upload)"""
        video_size = os.path.getsize(video_path)

        # INIT
        resp = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            auth=self.auth,
            data={
                "command": "INIT",
                "total_bytes": video_size,
                "media_type": "video/mp4",
                "media_category": "tweet_video",
            },
        )
        resp.raise_for_status()
        media_id = resp.json()["media_id_string"]

        # APPEND (chunked)
        chunk_size = 5 * 1024 * 1024  # 5MB chunks
        with open(video_path, "rb") as f:
            segment = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                resp = requests.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    auth=self.auth,
                    data={"command": "APPEND", "media_id": media_id, "segment_index": segment},
                    files={"media_data": chunk},
                )
                resp.raise_for_status()
                segment += 1

        # FINALIZE
        resp = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            auth=self.auth,
            data={"command": "FINALIZE", "media_id": media_id},
        )
        resp.raise_for_status()

        # Wait for processing
        processing = resp.json().get("processing_info")
        while processing and processing.get("state") != "succeeded":
            wait = processing.get("check_after_secs", 5)
            time.sleep(wait)
            resp = requests.get(
                "https://upload.twitter.com/1.1/media/upload.json",
                auth=self.auth,
                params={"command": "STATUS", "media_id": media_id},
            )
            processing = resp.json().get("processing_info")

        return media_id

    def post_tweet(self, text, media_id=None):
        """Post a tweet with optional video"""
        payload = {"text": text[:280]}
        if media_id:
            payload["media"] = {"media_ids": [media_id]}

        resp = requests.post(
            "https://api.twitter.com/2/tweets",
            headers={
                "Authorization": f"Bearer {self.bearer}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def post_thread(self, tweets):
        """Post a thread (list of tweet texts)"""
        previous_id = None
        results = []
        for tweet_text in tweets:
            payload = {"text": tweet_text[:280]}
            if previous_id:
                payload["reply"] = {"in_reply_to_tweet_id": previous_id}

            resp = requests.post(
                "https://api.twitter.com/2/tweets",
                headers={
                    "Authorization": f"Bearer {self.bearer}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            previous_id = data["id"]
            results.append(data)

        return results


# ---- Scheduler: Distribute posts across time slots ----

def schedule_posts(videos, platform_accounts, time_slots=None):
    """
    Create a posting schedule for multiple videos across accounts and time slots.

    Args:
        videos: List of {"path": str, "caption": str, "hashtags": str, "character": str}
        platform_accounts: {"tiktok": [...], "instagram": [...], "x": [...]}
        time_slots: List of hours [7, 12, 18, 21] (default)

    Returns:
        List of {"video": ..., "platform": ..., "account": ..., "time": ...}
    """
    if time_slots is None:
        time_slots = [7, 12, 18, 21]  # Japanese golden times

    schedule = []
    vid_idx = 0

    for video in videos:
        char = video.get("character", "default")

        # Determine primary platform for this character
        char_info = CHARACTERS.get(char, {})
        primary_pf = "tiktok"  # default

        # Round-robin across time slots and accounts
        slot = time_slots[vid_idx % len(time_slots)]
        minute = (vid_idx * 7) % 60  # Spread within the hour

        schedule.append({
            "video_path": video["path"],
            "caption": video.get("caption", ""),
            "hashtags": video.get("hashtags", ""),
            "character": char,
            "scheduled_time": f"{slot:02d}:{minute:02d}",
            "platform": primary_pf,
        })
        vid_idx += 1

    return schedule


if __name__ == "__main__":
    # Test schedule generation
    test_videos = [
        {"path": "v1.mp4", "caption": "test", "character": "miku"},
        {"path": "v2.mp4", "caption": "test", "character": "kenta"},
        {"path": "v3.mp4", "caption": "test", "character": "ayaka"},
    ]
    schedule = schedule_posts(test_videos, {})
    for s in schedule:
        print(f"  {s['scheduled_time']} | {s['character']} | {s['platform']}")
