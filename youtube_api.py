import os
import time
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import random
import isodate
from youtubesearchpython import CustomSearch, VideoSortOrder, Search
import httpx

# --- Monkey Patch for httpx.Client to enforce Japanese Locale ---
try:
    _original_httpx_init = httpx.Client.__init__

    def _patched_httpx_init(self, *args, **kwargs):
        headers = kwargs.get('headers')
        if headers is None: headers = {}
        
        # Enforce Japanese Language Preference & Cookie
        headers['Accept-Language'] = 'ja-JP,ja;q=0.9,en;q=0.8'
        headers['Cookie'] = 'PREF=hl=ja&gl=JP; PREF=f6=40000000&hl=ja&gl=JP' # Force JP interface
        
        kwargs['headers'] = headers
        _original_httpx_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_init
except Exception as e:
    logging.warning(f"Failed to patch httpx headers: {e}")
# -------------------------------------------------------------

class YouTubeClient:
    def __init__(self, api_key):
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    def search_videos_scraping(self, query, max_results=50, region_code=None, published_after_days=0):
        """
        Scrapes YouTube search results to save API quota.
        Returns a list of dicts consistent with API structure: [{'id': {'videoId': '...'}, ...}]
        Preserves Rank order.
        """
        # Map days to upload date filter
        upload_date = None
        if published_after_days > 0:
            if published_after_days <= 1:
                upload_date = "Today"
            elif published_after_days <= 7:
                upload_date = "This week"
            elif published_after_days <= 30:
                upload_date = "This month"
            elif published_after_days <= 365:
                upload_date = "This year"
        
        try:
            # Prefer 'Search' (default) if no date filter is needed. 
            # This returns more natural Japanese titles than CustomSearch restricted params.
            if published_after_days == 0:
                logging.info(f"Using Standard Search for '{query}' (No Date Filter)")
                # Standard Search
                search = Search(query, limit=max_results)
                items = self._fetch_from_search_obj(search, max_results)
                
                # Retry with space suffix on empty
                if not items:
                    logging.info(f"Standard Search empty for '{query}'. Retrying with suffix ' '...")
                    search = Search(query + " ", limit=max_results)
                    items = self._fetch_from_search_obj(search, max_results)
            else:
                # Use CustomSearch for Date Filters (Today/Week/Month/Year)
                logging.info(f"Using CustomSearch for '{query}' with Date Filter: {upload_date}")
                search = CustomSearch(query, VideoSortOrder.relevance, limit=max_results, region=region_code if region_code else 'JP', language='ja')
                if upload_date:
                    search = CustomSearch(query, VideoSortOrder.relevance, uploadDate=upload_date, limit=max_results, region=region_code if region_code else 'JP', language='ja')

                items = self._fetch_from_search_obj(search, max_results)
                
                # Retry with space suffix
                if not items:
                    logging.info(f"CustomSearch empty for '{query}'. Retrying with suffix ' '...")
                    query_spaced = query + " "
                    search = CustomSearch(query_spaced, VideoSortOrder.relevance, limit=max_results, region=region_code if region_code else 'JP', language='ja')
                    if upload_date:
                        search = CustomSearch(query_spaced, VideoSortOrder.relevance, uploadDate=upload_date, limit=max_results, region=region_code if region_code else 'JP', language='ja')
                    items = self._fetch_from_search_obj(search, max_results)

        except Exception as e:
            logging.warning(f"Search failed for '{query}': {e}")
            items = []

        if not items:
            logging.info(f"Attempting Fallback Regex Search for '{query}'")
            items = self._search_params_regex(query, max_results, published_after_days)

        return items

    def _search_params_regex(self, query, max_results, published_after_days):
        """
        Fallback scraping using regex on raw HTML.
        """
        import re
        import urllib.parse
        
        # Determine 'sp' parameter for Date Filter
        sp = None
        if published_after_days > 0:
            if published_after_days <= 1:
                sp = "EgIIAg%3D%3D" # Today
            elif published_after_days <= 7:
                sp = "EgIIAw%3D%3D" # This week
            elif published_after_days <= 30:
                sp = "EgIIBA%3D%3D" # This month
            elif published_after_days <= 365:
                sp = "EgIIBQ%3D%3D" # This year
        
        base_url = "https://www.youtube.com/results"
        params = {"search_query": query}
        if sp:
            params["sp"] = sp
            
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"
        }
        
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                logging.warning(f"Fallback regex failed: Status {resp.status_code}")
                return []
            
            html = resp.text
            
            video_ids = []
            seen = set()
            
            # Regex for watch?v=ID
            # Note: YouTube IDs are 11 chars (Alphanumeric + -_)
            matches = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
            
            for vid in matches:
                if vid not in seen:
                    video_ids.append(vid)
                    seen.add(vid)
                    if len(video_ids) >= max_results:
                        break
            
            # Construct items
            items = []
            for vid in video_ids:
                items.append({
                    'id': {'videoId': vid},
                    'snippet': {
                        'title': 'Unknown (Fallback)', # App will fetch details anyway
                        'channelTitle': '',
                        'description': ''
                    }
                })
            
            logging.info(f"Fallback regex found {len(items)} videos")
            return items
            
        except Exception as e:
            logging.error(f"Fallback regex error: {e}")
            return []

    def _fetch_from_search_obj(self, search, max_results):
        """Helper to iterate search object results"""
        items = []
        seen_ids = set()
        
        while len(items) < max_results:
            result = search.result()
            
            if not result or 'result' not in result or not result['result']:
                break
            
            new_items_found = False
            for item in result['result']:
                if item.get('type') == 'video':
                    vid = item.get('id')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        
                        # Extract description from snippet parts
                        desc_parts = item.get('descriptionSnippet', [])
                        desc_text = ""
                        if isinstance(desc_parts, list):
                            desc_text = "".join([d.get('text', '') for d in desc_parts])
                        elif isinstance(desc_parts, str):
                            desc_text = desc_parts
                            
                        items.append({
                            'id': {'videoId': vid},
                            'snippet': {
                                'title': item.get('title', ''),
                                'channelTitle': item.get('channel', {}).get('name', ''),
                                'description': desc_text
                            } 
                        })
                        new_items_found = True
                        if len(items) >= max_results:
                            break
            
            if not new_items_found:
                break
                
            if len(items) >= max_results:
                break
                
            try:
                search.next()
                time.sleep(0.5) 
            except:
                break
                
        return items




    def _execute_with_retry(self, request, max_retries=5):
        """Executes an API request with exponential backoff."""
        for n in range(max_retries):
            try:
                return request.execute()
            except HttpError as e:
                if e.resp.status in [403, 429, 500, 503]:
                    if e.resp.status == 403 and "quota" in str(e.content).lower():
                         logger.error("Quota exceeded.")
                         raise e
                    
                    wait_time = (2 ** n) + random.random()
                    logger.warning(f"API Error {e.resp.status}. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    raise e
        raise Exception("Max retries exceeded")

    def search_videos(self, keyword, max_results=50, published_after=None, region_code='JP', relevance_language=None):
        """
        Searches for videos and returns list of items.
        Handles pagination to reach max_results.
        """
        videos = []
        next_page_token = None
        
        # Youtube API max results per page is 50
        per_page = min(50, max_results)
        
        fetched_count = 0
        
        while fetched_count < max_results:
            current_limit = min(per_page, max_results - fetched_count)
            
            kwargs = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "maxResults": current_limit,
            }
            if published_after:
                kwargs["publishedAfter"] = published_after
            if next_page_token:
                kwargs["pageToken"] = next_page_token
            if region_code:
                kwargs["regionCode"] = region_code
            if relevance_language:
                kwargs["relevanceLanguage"] = relevance_language

            # Execute without internal try-catch to let caller handle/display errors
            request = self.youtube.search().list(**kwargs)
            response = self._execute_with_retry(request)

            items = response.get('items', [])
            if not items:
                break
                
            videos.extend(items)
            fetched_count += len(items)
            next_page_token = response.get('nextPageToken')
            
            if not next_page_token:
                break
                
        return videos

    def get_channel_details(self, channel_ids):
        """
        Fetches channel statistics for a list of channel IDs.
        Automatically batches requests in groups of 50.
        """
        all_channels = []
        
        # Remove duplicates just in case, though caller should handle
        unique_ids = list(set(channel_ids))
        
        for i in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[i:i+50]
            ids_string = ",".join(batch_ids)
            
            request = self.youtube.channels().list(
                part="snippet,statistics,contentDetails",
                id=ids_string
            )
            
            try:
                response = self._execute_with_retry(request)
                items = response.get('items', [])
                all_channels.extend(items)
            except Exception as e:
                logger.error(f"Failed to get channel details for batch {i}: {e}")
                
        return all_channels

    def get_video_details(self, video_ids):
        """
        Fetches video statistics (viewCount, etc) for a list of video IDs.
        """
        all_videos = []
        unique_ids = list(set(video_ids))
        
        for i in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[i:i+50]
            request = self.youtube.videos().list(
                part="statistics,snippet",
                id=",".join(batch_ids)
            )
            
            try:
                response = self._execute_with_retry(request)
                all_videos.extend(response.get('items', []))
            except Exception as e:
                logger.error(f"Failed to get video details for batch {i}: {e}")
                
        return all_videos

    def get_video_durations(self, video_ids):
        """
        Fetches duration for a list of video IDs.
        Returns a dictionary {videoId: duration_in_seconds}.
        """
        durations = {}
        unique_ids = list(set(video_ids))
        
        for i in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[i:i+50]
            request = self.youtube.videos().list(
                part="contentDetails",
                id=",".join(batch_ids)
            )
            
            try:
                response = self._execute_with_retry(request)
                items = response.get('items', [])
                for item in items:
                    vid = item.get('id')
                    duration_iso = item.get('contentDetails', {}).get('duration')
                    if vid and duration_iso:
                        try:
                            seconds = isodate.parse_duration(duration_iso).total_seconds()
                            durations[vid] = seconds
                        except:
                            durations[vid] = 0
            except Exception as e:
                logger.error(f"Failed to get video durations for batch {i}: {e}")
                
        return durations

    def get_full_video_details(self, video_ids):
        """
        Fetches snippet, statistics, and contentDetails for a list of video IDs in one go.
        Returns list of video objects.
        """
        all_videos = []
        unique_ids = list(set(video_ids))
        
        for i in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[i:i+50]
            request = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch_ids)
            )
            
            try:
                response = self._execute_with_retry(request)
                items = response.get('items', [])
                all_videos.extend(items)
            except Exception as e:
                logger.error(f"Failed to get full video details for batch {i}: {e}")
                
        return all_videos

    def get_channel_recent_video_stats(self, playlist_ids, max_per_channel=50):
        """
        Fetches recent video statistics for a list of Uploads Playlist IDs.
        Returns a dict: {channel_id: [view_count1, view_count2, ...]}
        Cost: 1 unit per channel (PlaylistItems) + 1 unit per 50 videos (Videos.list)
        """
        channel_video_map = {} # channelId -> [view_counts]
        all_video_ids = []
        vid_to_channel = {}
        
        # 1. Get Video IDs from Playlists
        for pid in playlist_ids:
            try:
                request = self.youtube.playlistItems().list(
                    part="snippet",
                    playlistId=pid,
                    maxResults=min(50, max_per_channel)
                )
                response = self._execute_with_retry(request)
                
                for item in response.get('items', []):
                    vid = item.get('snippet', {}).get('resourceId', {}).get('videoId')
                    cid = item.get('snippet', {}).get('channelId')
                    if vid and cid:
                        all_video_ids.append(vid)
                        vid_to_channel[vid] = cid
                        
            except Exception as e:
                logger.error(f"Failed to fetch playlist items for {pid}: {e}")
                
        if not all_video_ids:
            return {}
            
        # 2. Get Statistics for these videos
        # Reuse existing batch function
        video_details = self.get_video_details(all_video_ids)
        
        # 3. Group by Channel
        for v in video_details:
            vid = v.get('id')
            cid = vid_to_channel.get(vid)
            stats = v.get('statistics', {})
            view_count = int(stats.get('viewCount', 0))
            
            if cid:
                if cid not in channel_video_map:
                    channel_video_map[cid] = []
                channel_video_map[cid].append(view_count)
                
        return channel_video_map
