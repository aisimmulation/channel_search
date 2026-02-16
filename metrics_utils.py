import pandas as pd
import numpy as np
from datetime import datetime, timezone

def calculate_keyword_metrics(videos_data):
    """
    Calculates detailed metrics for a set of videos.
    Based on v1.3.0 requirements:
    - Age: 10, 30, 90, 180, 365 days
    - Volume Tiers: Top 10%, 10-30%, 30-50%
    """
    if not videos_data:
        return {
            "video_count": 0,
            "total_views": 0,
            "max_views": 0,
            "count_10d": 0, "count_30d": 0, "count_90d": 0, "count_180d": 0, "count_365d": 0,
            "avg_top_10": 0, "avg_top_10_30": 0, "avg_top_30_50": 0
        }

    df = pd.DataFrame(videos_data)
    
    # 1. Basic Stats
    total_views = df['viewCount'].sum()
    max_views = df['viewCount'].max()
    video_count = len(df)
    
    # 2. Date Analysis (Inclusive: "within X days")
    now = datetime.now(timezone.utc)
    # Ensure publishedAt is timezone aware (should be if from API)
    # If mixed, coerce to UTC
    if df['publishedAt'].dt.tz is None:
        df['publishedAt'] = df['publishedAt'].dt.tz_localize(timezone.utc)
    
    df['days_old'] = (now - df['publishedAt']).dt.days
    
    count_10d = len(df[df['days_old'] <= 10])
    count_30d = len(df[df['days_old'] <= 30])
    count_90d = len(df[df['days_old'] <= 90])
    count_180d = len(df[df['days_old'] <= 180])
    count_365d = len(df[df['days_old'] <= 365])
    
    # 3. Volume Tier Analysis
    # Sort by views desc
    df_sorted = df.sort_values('viewCount', ascending=False).reset_index(drop=True)
    
    def get_avg_slice(start_pct, end_pct):
        # start_pct=0.0 means top rank (index 0)
        start_idx = int(video_count * start_pct)
        end_idx = int(video_count * end_pct)
        
        # If the slice range is extremely small (e.g. video_count=2, 10-30% range might be 0.2-0.6 -> idx 0 to 0)
        # simplistic checks
        if start_idx == end_idx:
            # If start_idx is valid, just take that one. Or 0.
            # For strictness, if the slice represents < 1 video textually but mathematically exists, 
            # usually implies insufficient data -> 0 or nearest neighbor? 
            # Let's return 0 if < 1 video fits, unless total videos is small and we want to map broadly.
            # User wants "Average of Top X%". 
            return 0
            
        slice_data = df_sorted.iloc[start_idx:end_idx]
        if slice_data.empty:
            return 0
        return slice_data['viewCount'].mean()

    # Handling small sample sizes more gracefully
    # If video_count < 10, these buckets will be very noisy or empty.
    # We apply the slice logic directly.
    
    avg_top_10 = get_avg_slice(0.0, 0.1)
    
    # If video_count is small (e.g. 5), 10% is 0.5 videos -> start=0, end=0 -> returns 0.
    # We should probably force at least the first video into Top 10% if count > 0?
    # But strictly speaking, "Top 10%" of 5 videos is "0.5 videos", which doesn't exist.
    # Let's keep strict slicing. If you have 5 videos, Top 10% is empty. Top 20% starts to encompass 1 video.
    # Actually, for user utility, if top 10% is empty but data exists, maybe fallback?
    # Let's stick to strict logic for now unless user complains about zeros.
    # Correction: If start_idx == end_idx, it means the slice is empty integer-wise.
    # BUT, if we have 1 video. Top 10% (0.1) -> idx 0 to 0. Empty. 
    # Top 10-30% -> idx 0 to 0. Empty.
    # Top 30-50% -> idx 0 to 0. Empty.
    # This means for small N, all detailed metrics are 0.
    # That might be confusing. For top 10%, we usually want "The Best videos".
    # Let's adjust: Top 10% always includes at least the #1 video if N > 0?
    # No, user asked for "Average of Top 10%".
    # I'll implement a helper that handles small N better:
    # "If the calculated slice size is 0 but range is >0 and videos exist, take the single boundary item"?
    # Let's stick to standard slice. If N=100, 0-10 is 0..10. Correct.
    # If N=5, 0-0.5. Empty.
    # I will modify to: `max(1, int(...))` for end index of Top 10? No that changes definition.
    # Leaving as strict slice.
    
    avg_top_10 = get_avg_slice(0.0, 0.1)
    
    avg_top_10_30 = get_avg_slice(0.1, 0.3)
    avg_top_30_50 = get_avg_slice(0.3, 0.5)
    
    # 4. Specific 30-Day Metrics (requested by user)
    df_30d = df[df['days_old'] <= 30]
    if not df_30d.empty:
        total_views_30d = df_30d['viewCount'].sum()
        avg_views_30d = df_30d['viewCount'].mean()
    else:
        total_views_30d = 0
        avg_views_30d = 0

    # 5. Specific 90-Day Metrics (requested by user)
    df_90d = df[df['days_old'] <= 90]
    if not df_90d.empty:
        total_views_90d = df_90d['viewCount'].sum()
        avg_views_90d = df_90d['viewCount'].mean()
    else:
        total_views_90d = 0
        avg_views_90d = 0

    # 6. Count of videos in Top 30% (Global) for recent periods
    # Threshold for Top 30% (70th percentile)
    if not df.empty and video_count > 0:
        threshold_top30 = df['viewCount'].quantile(0.7)
    else:
        threshold_top30 = 0
        
    count_top30_30d = 0
    if not df_30d.empty:
        count_top30_30d = len(df_30d[df_30d['viewCount'] >= threshold_top30])
        
    count_top30_90d = 0
    if not df_90d.empty:
        count_top30_90d = len(df_90d[df_90d['viewCount'] >= threshold_top30])

    return {
        "video_count": video_count,
        "total_views": total_views,
        "max_views": max_views,
        "total_views_30d": total_views_30d,
        "avg_views_30d": int(avg_views_30d),
        "total_views_90d": total_views_90d,
        "avg_views_90d": int(avg_views_90d),
        "count_top30_30d": count_top30_30d, # New
        "count_top30_90d": count_top30_90d, # New
        "count_10d": count_10d,
        "count_30d": count_30d,
        "count_90d": count_90d,
        "count_180d": count_180d,
        "count_365d": count_365d,
        "avg_top_10": int(avg_top_10) if not pd.isna(avg_top_10) else 0,
        "avg_top_10_30": int(avg_top_10_30) if not pd.isna(avg_top_10_30) else 0,
        "avg_top_30_50": int(avg_top_30_50) if not pd.isna(avg_top_30_50) else 0
    }
