"""
Pinterest Downloader Core Module
Extracts highest-resolution images, videos, and multi-media from Pinterest pins.
"""

import re
import json
import os
import sys
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.pinterest.com/",
}

def clean_pinterest_url(url: str) -> str:
    url = url.strip()
    # If user passed text containing the URL, extract the URL
    match = re.search(r"https?://(?:[a-zA-Z0-9-]+\.)?pinterest\.[a-zA-Z.]+(?:/pin/|\S+)|https?://pin\.it/\S+", url)
    if match:
        return match.group(0)
    return url

def extract_pin_id(url: str) -> Optional[str]:
    match = re.search(r"/pin/(\d+)", url)
    if match:
        return match.group(1)
    return None

async def resolve_url(client: httpx.AsyncClient, url: str) -> str:
    """Follow redirects (e.g. pin.it short links) to get the final Pinterest URL."""
    try:
        resp = await client.get(url, follow_redirects=True, headers=HEADERS, timeout=15.0)
        return str(resp.url)
    except Exception:
        return url

def find_best_image_url(pin_dict: Dict[str, Any]) -> Optional[str]:
    """Find the highest resolution image URL from a pin object dictionary."""
    images = pin_dict.get("images", {})
    if not isinstance(images, dict):
        return None
    
    # Priority order for resolution
    for key in ["orig", "originals", "1200x", "736x", "564x", "474x", "236x"]:
        if key in images and isinstance(images[key], dict) and "url" in images[key]:
            url = images[key]["url"]
            # Convert any thumbnail URL to originals URL if possible
            if "i.pinimg.com" in url:
                url = re.sub(r"i\.pinimg\.com/\d+x/", "i.pinimg.com/originals/", url)
            return url

    # Check image_spec
    image_spec = pin_dict.get("image_spec", {})
    if isinstance(image_spec, dict) and "url" in image_spec:
        url = image_spec["url"]
        if "i.pinimg.com" in url:
            url = re.sub(r"i\.pinimg\.com/\d+x/", "i.pinimg.com/originals/", url)
        return url

    return None

def find_best_video_url(pin_dict: Dict[str, Any]) -> Optional[str]:
    """Find the highest resolution video URL from a pin object dictionary."""
    # Check videos -> video_list
    videos = pin_dict.get("videos", {})
    if isinstance(videos, dict):
        video_list = videos.get("video_list", {})
        if isinstance(video_list, dict):
            # Prioritize standard mp4 quality variants over m3u8
            # V_720P, V_1080P, V_EXP7, V_EXP6, V_EXP5, etc.
            best_quality = -1
            best_url = None
            
            # Sort keys prioritizing 1080p, 720p, etc.
            for key, val in video_list.items():
                if not isinstance(val, dict):
                    continue
                v_url = val.get("url")
                if not v_url:
                    continue
                
                # Check height or width
                height = val.get("height", 0)
                width = val.get("width", 0)
                score = max(height, width)

                # Prefer mp4 over m3u8 when available
                if v_url.endswith(".mp4"):
                    score += 10000

                if score > best_quality:
                    best_quality = score
                    best_url = v_url

            if best_url:
                # If it's an m3u8 HLS master playlist, check if there's an MP4 counterpart
                # Pinterest often uses: v.pinimg.com/videos/mc/720p/...mp4 or /hls/...m3u8
                return best_url

    # Check story_pin_data if present
    story_pin = pin_dict.get("story_pin_data")
    if isinstance(story_pin, dict):
        pages = story_pin.get("pages", [])
        for page in pages:
            if isinstance(page, dict):
                blocks = page.get("blocks", [])
                for block in blocks:
                    if isinstance(block, dict) and block.get("video"):
                        vid = block["video"]
                        v_list = vid.get("video_list", {})
                        for v in v_list.values():
                            if isinstance(v, dict) and v.get("url"):
                                return v["url"]

    return None

async def extract_media_from_pin(url: str, client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    """
    Given any Pinterest URL (short link or full link), extracts:
    - title
    - media_type ('video' or 'image')
    - media_url (highest available resolution)
    - fallback_urls (if any)
    - filename
    """
    should_close = False
    if client is None:
        client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20.0)
        should_close = True

    try:
        clean_url = clean_pinterest_url(url)
        final_url = await resolve_url(client, clean_url)
        pin_id = extract_pin_id(final_url)

        resp = await client.get(final_url, headers=HEADERS)
        html_text = resp.text

        title = "pinterest_pin"
        media_url = None
        media_type = "image"

        # 1. Parse OpenGraph / meta tags first for title and fallback media
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Title extraction
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Sanitize title
        title = re.sub(r'[\\/*?:"<>|]', "", title)
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) > 60:
            title = title[:60].strip()

        # Check OpenGraph video first
        og_video = soup.find("meta", property="og:video") or soup.find("meta", property="og:video:secure_url")
        if og_video and og_video.get("content"):
            media_url = og_video["content"]
            media_type = "video"

        # 2. Try to parse __PWS_DATA__ JSON embedded script
        pws_script = soup.find("script", id="__PWS_DATA__")
        if pws_script and pws_script.string:
            try:
                data = json.loads(pws_script.string)
                props = data.get("props", {}).get("initialReduxState", {})
                pins = props.get("pins", {})
                
                # If pin_id is known, look directly; otherwise inspect all pins in props
                target_pin = None
                if pin_id and pin_id in pins:
                    target_pin = pins[pin_id]
                elif pins:
                    target_pin = next(iter(pins.values()))

                if target_pin and isinstance(target_pin, dict):
                    # Check for video first
                    video_url = find_best_video_url(target_pin)
                    if video_url:
                        media_url = video_url
                        media_type = "video"
                    else:
                        img_url = find_best_image_url(target_pin)
                        if img_url:
                            media_url = img_url
                            media_type = "image"
            except Exception:
                pass

        # 3. If no media found yet, check API resource endpoint directly
        if not media_url and pin_id:
            try:
                api_url = "https://www.pinterest.com/resource/PinResource/get/"
                api_params = {
                    "source_url": f"/pin/{pin_id}/",
                    "data": json.dumps({"options": {"id": pin_id, "field_set_key": "detailed"}}),
                }
                api_headers = {
                    **HEADERS,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                }
                api_resp = await client.get(api_url, params=api_params, headers=api_headers)
                if api_resp.status_code == 200:
                    api_json = api_resp.json()
                    pin_data = api_json.get("resource_response", {}).get("data", {})
                    if pin_data:
                        vid_url = find_best_video_url(pin_data)
                        if vid_url:
                            media_url = vid_url
                            media_type = "video"
                        else:
                            img_url = find_best_image_url(pin_data)
                            if img_url:
                                media_url = img_url
                                media_type = "image"
            except Exception:
                pass

        # 4. Fallback: regex search in page HTML
        if not media_url:
            # Look for 720p or mp4 video
            video_matches = re.findall(r'https?://v\.pinimg\.com/videos/[^\s"\'<>]+\.mp4', html_text)
            if video_matches:
                # Pick highest quality (720p preferred)
                best_v = [v for v in video_matches if "720p" in v]
                media_url = best_v[0] if best_v else video_matches[0]
                media_type = "video"
            else:
                # Look for originals image
                orig_matches = re.findall(r'https?://i\.pinimg\.com/originals/[^\s"\'<>]+\.(?:jpg|png|gif|webp)', html_text)
                if orig_matches:
                    media_url = orig_matches[0]
                    media_type = "image"
                else:
                    # Look for og:image
                    og_img = soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        raw_img = og_img["content"]
                        # Boost resolution to originals
                        media_url = re.sub(r"i\.pinimg\.com/\d+x/", "i.pinimg.com/originals/", raw_img)
                        media_type = "image"

        if not media_url:
            raise ValueError(f"Could not extract any media from pin: {url}")

        # Determine extension and filename
        parsed_media = urlparse(media_url)
        path = parsed_media.path
        ext = os.path.splitext(path)[1]
        if not ext or len(ext) > 5:
            ext = ".mp4" if media_type == "video" else ".jpg"

        id_suffix = f"_{pin_id}" if pin_id else ""
        safe_title = title if title and title != "pinterest_pin" else "pinterest"
        filename = f"{safe_title}{id_suffix}{ext}"

        return {
            "pin_id": pin_id,
            "title": title,
            "media_type": media_type,
            "media_url": media_url,
            "filename": filename,
            "final_url": final_url,
        }

    finally:
        if should_close:
            await client.aclose()


async def download_file_parallel(
    url: str,
    dest_path: str,
    client: Optional[httpx.AsyncClient] = None,
    progress_callback = None,
    num_chunks: int = 4
) -> str:
    """
    Downloads a media file rapidly using parallel chunk streaming if supported,
    or streaming chunks directly.
    """
    should_close = False
    if client is None:
        client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=60.0)
        should_close = True

    try:
        # Check Content-Length and Accept-Ranges
        head_resp = await client.head(url)
        content_length = int(head_resp.headers.get("content-length", 0))
        accept_ranges = "bytes" in head_resp.headers.get("accept-ranges", "").lower()

        # If file is larger than 2MB and server supports ranges, use parallel chunk download
        if accept_ranges and content_length > 2 * 1024 * 1024 and num_chunks > 1:
            chunk_size = content_length // num_chunks
            ranges = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = (start + chunk_size - 1) if i < num_chunks - 1 else (content_length - 1)
                ranges.append((start, end, i))

            chunks_data = [None] * num_chunks
            downloaded_bytes = 0

            async def download_part(start: int, end: int, index: int):
                nonlocal downloaded_bytes
                r_headers = {**HEADERS, "Range": f"bytes={start}-{end}"}
                async with client.stream("GET", url, headers=r_headers) as resp:
                    resp.raise_for_status()
                    part_bytes = bytearray()
                    async for chunk in resp.aiter_bytes(chunk_size=32 * 1024):
                        part_bytes.extend(chunk)
                        downloaded_bytes += len(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), content_length)
                    chunks_data[index] = bytes(part_bytes)

            await asyncio.gather(*(download_part(s, e, idx) for s, e, idx in ranges))

            os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
            with open(dest_path, "wb") as f:
                for part in chunks_data:
                    if part:
                        f.write(part)
        else:
            # Standard fast streaming download
            os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
                        if progress_callback:
                            progress_callback(len(chunk), total)

        return dest_path

    finally:
        if should_close:
            await client.aclose()
