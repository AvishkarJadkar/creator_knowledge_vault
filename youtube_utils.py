import re
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

def extract_video_id(url: str):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?]+)",
    ]
    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)
    return None

def get_youtube_transcript(url: str):
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    try:
        # 1️⃣ Prefer English (manual or auto)
        transcript = transcript_list.find_transcript(["en"])
    except:
        try:
            # 2️⃣ Fallback: auto-generated English
            transcript = transcript_list.find_generated_transcript(["en"])
        except:
            raise Exception("No English transcript available")

    transcript_data = transcript.fetch()
    return " ".join(item.text for item in transcript_data)

def get_youtube_title(url: str) -> str:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title", "YouTube Video")