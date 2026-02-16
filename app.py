import streamlit as st
import re
import pandas as pd
import os
import math
import isodate
from datetime import datetime, timedelta, timezone
from youtube_api import YouTubeClient
from keyword_utils import get_youtube_suggestions, get_related_keywords
from metrics_utils import calculate_keyword_metrics
from metrics_utils import calculate_keyword_metrics
from dotenv import load_dotenv, set_key



def contains_japanese(text):
    # Check for Hiragana, Katakana, or Kanji
    # Ranges: Hiragana (3040-309F), Katakana (30A0-30FF), Kanji (4E00-9FFF)
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))


# Load environment variables
load_dotenv()
ENV_PATH = ".env"

# VERSION
APP_VERSION = "v1.4.0"

# Page Config
st.set_page_config(
    page_title="Keyword Ecosystem Analyzer",
    page_icon="🕸️",
    layout="wide"
)

# Title & Description
st.title("🕸️ YouTube Keyword Analyzer")
st.markdown(f"**バージョン: {APP_VERSION}**")

# Sidebar - Configuration
st.sidebar.header("設定 (Configuration)")

# Search Region (Moved to Main)
# region_option = st.sidebar.radio("検索対象国 (Region)", ["Japan (JP)", "Worldwide"], index=0) ...

# API Key Handling
env_api_key = os.getenv("YOUTUBE_API_KEY", "")
api_key = st.sidebar.text_input("YouTube APIキー", value=env_api_key, type="password", help="Google Cloud Consoleで取得してください")
if st.sidebar.button("APIキーを保存"):
    if api_key:
        try:
            if not os.path.exists(ENV_PATH):
                with open(ENV_PATH, 'w') as f: f.write("")
            set_key(ENV_PATH, "YOUTUBE_API_KEY", api_key)
            st.sidebar.success("保存しました。")
        except:
            st.sidebar.error("保存に失敗しました。")
        



# Helper function for summarization


# Search Parameters (Moved)
# use_suggestions = st.sidebar.checkbox(...)  

st.sidebar.divider()
# st.sidebar.subheader("詳細フィルタ")
# top_n = 50 # Moved to Filter Area

# Main Input
st.subheader("1. キーワード分析")
primary_input = st.text_area("キーワードを入力 (カンマ区切り)", placeholder="例: ビットコイン,BTC", height=68)

# Filters (Main Area)
# st.subheader("フィルタ")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    use_suggestions = st.checkbox("サジェスト含む", value=True, help="YouTubeの検索候補（サジェスト）をキーワードごとに自動取得します（最大20件）")

with col2:
    top_n = st.radio("分析数", [20, 50, 100], index=0, horizontal=True)

with col3:
    period_type = st.radio("集計期間", ["全期間", "指定"], index=0, horizontal=True)
    days_filter = 0
    if period_type == "指定":
        days_filter = st.number_input("日数", min_value=1, value=7)

with col4:
    target_type = st.radio("対象", ["全て", "動画", "ショート"], index=1, horizontal=True)
    min_sec = 0
    max_sec = None
    if target_type == "動画":
        min_sec = 181
    elif target_type == "ショート":
        max_sec = 180

with col5:
    region_option = st.radio("検索対象国", ["Japan (JP)", "Worldwide"], index=0, horizontal=True)
    if region_option == "Japan (JP)":
        region = "JP"
        lang = "ja"
    else:
        region = None
        lang = None

st.divider()

# Execution
if st.button("🚀 分析開始", type="primary"):
    if not api_key or not primary_input:
        st.error("APIキーとキーワードを入力してください。")
        st.stop()
        
    # Parse Keywords
    raw_keywords = [k.strip() for k in primary_input.split(',') if k.strip()]
    if not raw_keywords:
        st.error("有効なキーワードを少なくとも1つ入力してください。")
        st.stop()

    client = YouTubeClient(api_key)
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # 1. Build Keyword List
    tasks = []
    seen_keywords = set()
    
    for pk in raw_keywords:
        if pk not in seen_keywords:
            tasks.append((pk, "Primary"))
            seen_keywords.add(pk)
            
        # Suggestions (if enabled)
        if use_suggestions:
            status_text.text(f"サジェスト取得中: {pk}...")
            suggs = get_youtube_suggestions(pk)
            for s in suggs[:20]: # Limit suggestions per keyword
                if s not in seen_keywords:
                    tasks.append((s, "Suggestion"))
                    seen_keywords.add(s)
                
    st.info(f"合計 {len(tasks)} 個のキーワードを分析中...")
    
    # 2. Analyze Loop
    metrics_results = []
    all_video_details = [] # List for detailed CSV
    
    total = len(tasks)
    
    for i, (kw, ktype) in enumerate(tasks):
        status_text.text(f"処理中: {kw} ({i+1}/{total})")
        progress_bar.progress(i / total)
        
        try:
            # Search (Hybrid: Scraping)
            # using days_filter directly
            
            # Case 3: Priority Search (Deep Scan for JP)
            search_limit = top_n
            if region == "JP":
                # Fetch 1.5x to buffer filtering (User request: 20->30, 50->75, 100->150)
                search_limit = int(top_n * 1.5)
            
            videos = client.search_videos_scraping(
                kw, 
                max_results=search_limit, 
                region_code=region,
                published_after_days=days_filter
            )
            
            if not videos:
                continue
            
            # --- Strict Filtering for JP ---
            if region == "JP":
                filtered_videos = []
                for v in videos:
                    # Check snippet fields
                    snip = v.get('snippet', {})
                    # Strict Filter: Title OR Description (as fallback for translated titles)
                    title_text = snip.get('title', '') or ""
                    desc_text = snip.get('description', '') or ""
                    
                    # Check Title first (most reliable)
                    if contains_japanese(title_text):
                        filtered_videos.append(v)
                    # Fallback: Check Description (if Title is English but Desc is Japanese)
                    elif contains_japanese(desc_text):
                        filtered_videos.append(v)
                    # Fallback for Scraper Regex (Unknown Title)
                    elif title_text == "Unknown (Fallback)":
                        filtered_videos.append(v)
                
                # Update videos to the filtered list
                videos = filtered_videos[:top_n] # Take top N from filtered
            else:
                videos = videos[:top_n]
            
            if not videos:
                 # If usage of "Search Command" (lang:ja) failed, this might return 0
                 # But we reverted that. This is just standard safety.
                 continue
            
            # Create Rank Map (Index 1-based)
            # Filter out non-video items just in case
            vid_rank_map = {}
            rank_counter = 1
            for v in videos:
                if 'videoId' in v['id']:
                    vid_rank_map[v['id']['videoId']] = rank_counter
                    rank_counter += 1
                
                
            # Details
            vids = list(vid_rank_map.keys())
            if not vids: 
                continue
                
            full_details = client.get_full_video_details(vids)
            
            # Filter & Extract
            valid_data = [] # {viewCount, publishedAt} for metrics logic
            
            for v in full_details:
                vid_id = v.get('id')
                snip = v.get('snippet', {})
                title = snip.get('title', "")
                
                # Secondary Language Filter (Strict Japanese Check for details)
                # Appears AFTER fetching full details for "Unknown" items
                if region == "JP":
                     desc = snip.get('description', '') or ""
                     channel_title = snip.get('channelTitle', '') or ""
                     # Check Title, Desc, or Channel for Japanese
                     if not (contains_japanese(title) or contains_japanese(desc) or contains_japanese(channel_title)):
                         continue

                # Language Filter (Strict Japanese Check) - DISABLED as per user request to allow all results
                # Apply only if Region is JP
                if region == "JP":
                     # Check for Hiragana, Katakana, or Kanji in Title, Channel Name, or Description
                     # This ensures we filter out purely foreign content while keeping Japanese content with English titles
                     # text_check = title + (snip.get('channelTitle', '') or "") + (snip.get('description', '') or "")
                     # if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text_check):
                     #     continue
                     pass
                
                # Duration Filter
                dur_iso = v.get('contentDetails', {}).get('duration')
                sec = 0
                if dur_iso:
                    try:
                        sec = isodate.parse_duration(dur_iso).total_seconds()
                    except: pass
                
                # Apply Min/Max Logic
                if min_sec > 0 and sec < min_sec:
                    continue
                if max_sec is not None and sec > max_sec:
                    continue
                    
                # Collect for Metrics
                stats = v.get('statistics', {})
                
                view_count = int(stats.get('viewCount', 0))
                pub_at = pd.to_datetime(snip.get('publishedAt'))
                channel = snip.get('channelTitle', 'Unknown')
                chan_id = snip.get('channelId', '')
                thumb = snip.get('thumbnails', {}).get('medium', {}).get('url', '')
                if not thumb:
                     thumb = snip.get('thumbnails', {}).get('high', {}).get('url', '') # Fallback
                rank = vid_rank_map.get(vid_id, 999) # Rank for this keyword
                
                valid_data.append({
                    'viewCount': view_count,
                    'publishedAt': pub_at,
                    'title': title,
                    'channelTitle': channel,
                    'channelId': chan_id,
                    'videoId': vid_id,
                    'thumbnail': thumb,
                    'rank': rank
                })
                
                # Collect for Detailed List
                rank = vid_rank_map.get(vid_id, 999)
                url = f"https://www.youtube.com/watch?v={vid_id}"
                
                all_video_details.append({
                    "Keyword": kw,

                    "Type": ktype,
                    "Rank": rank,
                    "Title": title,
                    "Channel": channel,
                    "Views": view_count,
                    "Duration(s)": int(sec),
                    "Published": snip.get('publishedAt'),
                    "URL": url
                })
                
            # Calc Metrics
            m = calculate_keyword_metrics(valid_data)
            m['keyword'] = kw
            m['type'] = ktype
            m['details'] = valid_data # Store raw data for graph
            metrics_results.append(m)
            
        except Exception as e:
            st.error(f"エラー発生 ({kw}): {e}")
            
    progress_bar.progress(1.0)
    status_text.success("完了!")
    
    # Save to session_state
    if metrics_results:
        st.session_state['results'] = metrics_results

# 3. Display Results (Persistent State)
if 'results' in st.session_state:
    metrics_results = st.session_state['results']
    
    if metrics_results:
        # A. Keyword Metrics
        df = pd.DataFrame(metrics_results)
        
        cols = [
            'keyword', 'type', 
            'video_count', 'total_views', 'max_views',
            'total_views_30d', 'total_views_90d',
            'avg_views_30d', 'avg_views_90d',
            'count_top30_30d', 'count_top30_90d',
            'avg_top_10', 'avg_top_10_30', 'avg_top_30_50',
            'count_10d', 'count_30d', 'count_90d', 'count_180d', 'count_365d'
        ]
        final_cols = [c for c in cols if c in df.columns]
        df = df[final_cols]

        # --- Aggregation Logic (Total Row) ---
        if not df.empty:
            primary_df = df[df['type'] == 'Primary']
            if not primary_df.empty and len(primary_df) > 1:
                total_row = {
                    'keyword': 'Primary TOTAL',
                    'type': '-',
                    'max_views': primary_df['max_views'].max() if 'max_views' in primary_df else 0
                }
                # Sum columns
                sum_cols = ['video_count', 'total_views', 'total_views_30d', 'total_views_90d', 'count_top30_30d', 'count_top30_90d', 'count_10d', 'count_30d', 'count_90d', 'count_180d', 'count_365d']
                for c in sum_cols:
                    if c in primary_df.columns:
                        total_row[c] = primary_df[c].sum()
                
                # Avg columns (Simple Average of the metrics)
                avg_cols = ['avg_views_30d', 'avg_views_90d', 'avg_top_10', 'avg_top_10_30', 'avg_top_30_50']
                for c in avg_cols:
                    if c in primary_df.columns:
                        total_row[c] = primary_df[c].mean()

                # Prepend Total Row
                df_total = pd.DataFrame([total_row])
                df = pd.concat([df_total, df], ignore_index=True)
        # -------------------------------------
        
        st.subheader("キーワード分析結果")
        
        
        # Prepare MultiIndex DataFrame for Display
        # 1. Define Hierarchical Columns (Group, ShortName)
        multi_cols = []
        # We need to map the current flat columns to (Group, Label)
        
        # Current columns in order:
        # keyword, type, 
        # video_count, total_views, max_views,
        # total_views_30d, total_views_90d, avg_views_30d, avg_views_90d,
        # count_top30_30d, count_top30_90d,
        # count_10d, count_30d, count_90d, count_180d, count_365d,
        # avg_top_10, avg_top_10_30, avg_top_30_50
        
        col_map = {
            'keyword': ('基本', 'KW'),
            'type': ('基本', 'Type'),
            'video_count': ('基本', 'Hit数'),
            'total_views': ('基本', '総再生'),
            'max_views': ('基本', '最大再生'),
            
            'total_views_30d': ('総再生(30/90)', '30日'),
            'total_views_90d': ('総再生(30/90)', '90日'),
            
            'avg_views_30d': ('平均(30/90)', '30日'),
            'avg_views_90d': ('平均(30/90)', '90日'),
            
            'count_top30_30d': ('Top30%(30/90)', '30日'),
            'count_top30_90d': ('Top30%(30/90)', '90日'),
            
            'count_10d': ('投稿後経過日数', '~10日'),
            'count_30d': ('投稿後経過日数', '~30日'),
            'count_90d': ('投稿後経過日数', '~90日'),
            'count_180d': ('投稿後経過日数', '~180日'),
            'count_365d': ('投稿後経過日数', '~365日'),
            
            'avg_top_10': ('上位層平均(再生)', 'Top10%'),
            'avg_top_10_30': ('上位層平均(再生)', '10-30%'),
            'avg_top_30_50': ('上位層平均(再生)', '30-50%')
        }
        
        # Filter map based on actual df columns
        final_col_tuples = []
        for c in df.columns:
            if c in col_map:
                final_col_tuples.append(col_map[c])
            else:
                final_col_tuples.append(('その他', c))
                
        # Create new DF with MultiIndex
        df_display = df.copy()
        df_display.columns = pd.MultiIndex.from_tuples(final_col_tuples)
        
        # Formatting for Display
        def format_metric(val):
            try:
                n = float(val)
                if n >= 10000:
                    n = round(n, -3)
                    return f"{int(n):,}"
                return f"{int(n):,}"
            except:
                return val

        # Identify columns to format (numeric)
        # We need their new (Group, Label) tuples
        fmt_cols_flat = [
            'total_views', 'max_views', 'total_views_30d', 'avg_views_30d', 'total_views_90d', 'avg_views_90d',
            'count_top30_30d', 'count_top30_90d',
            'video_count', 'count_10d', 'count_30d', 'count_90d', 'count_180d', 'count_365d',
            'avg_top_10', 'avg_top_10_30', 'avg_top_30_50'
        ]
        valid_fmt_cols = [col_map[c] for c in fmt_cols_flat if c in df.columns]
        
        styler = df_display.style.format(subset=valid_fmt_cols, formatter=format_metric)
        styler.set_properties(subset=valid_fmt_cols, **{'text-align': 'right'})
        
        # Color Coding Categories (using new tuples)
        # 1. Basic Stats (Blue tint)
        cols_basic = ['video_count', 'total_views', 'max_views']
        target_basic = [col_map[c] for c in cols_basic if c in df.columns]
        styler.set_properties(subset=target_basic, **{'background-color': 'rgba(0, 100, 255, 0.10)'})
        
        # 2. Recent Stats (Green tint - Gradient)
        # A. Total Views (10%)
        cols_recent_total = ['total_views_30d', 'total_views_90d']
        target_recent_total = [col_map[c] for c in cols_recent_total if c in df.columns]
        styler.set_properties(subset=target_recent_total, **{'background-color': 'rgba(0, 200, 0, 0.10)'})
        
        # B. Avg Views (8%)
        cols_recent_avg = ['avg_views_30d', 'avg_views_90d']
        target_recent_avg = [col_map[c] for c in cols_recent_avg if c in df.columns]
        styler.set_properties(subset=target_recent_avg, **{'background-color': 'rgba(0, 200, 0, 0.08)'})
        
        # C. Top 30% Count (6%)
        cols_recent_top30 = ['count_top30_30d', 'count_top30_90d']
        target_recent_top30 = [col_map[c] for c in cols_recent_top30 if c in df.columns]
        styler.set_properties(subset=target_recent_top30, **{'background-color': 'rgba(0, 200, 0, 0.06)'})
        
        # 3. Age Distribution (Orange/Yellow tint)
        cols_age = ['count_10d', 'count_30d', 'count_90d', 'count_180d', 'count_365d']
        target_age = [col_map[c] for c in cols_age if c in df.columns]
        styler.set_properties(subset=target_age, **{'background-color': 'rgba(255, 150, 0, 0.10)'})
        
        # 4. Tier Stats (Purple tint)
        cols_tier = ['avg_top_10', 'avg_top_10_30', 'avg_top_30_50']
        target_tier = [col_map[c] for c in cols_tier if c in df.columns]
        styler.set_properties(subset=target_tier, **{'background-color': 'rgba(128, 0, 128, 0.10)'})
        
        # Toggle for Selection Mode
        use_multi_select = st.toggle("複数行選択モード (グラフ比較用)", value=False)
        sel_mode = "multi-row" if use_multi_select else "single-row"
        
        event = st.dataframe(styler, use_container_width=True, on_select="rerun", selection_mode=sel_mode)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 分析CSVをダウンロード", csv, "ecosystem_analysis.csv", "text/csv")
        
        # Copy for Spreadsheet (TSV)
        with st.expander("📋 スプレッドシート用データ (コピー用)"):
            st.markdown("以下のデータエリアに**マウスを乗せる**と、右上に**コピーボタン**が表示されます。")
            tsv = df_display.to_csv(index=False, sep='\t')
            st.code(tsv, language='text')

        # --- Graph Analysis Section ---
        st.divider()
        st.subheader("2. グラフ分析")
        
        # Determine Graph Data Source
        graph_data_list = [] # List of dicts {date, keyword}
        graph_title = "📅 投稿数の推移 (月次 - 直近1年)"
        graph_subtitle = "対象: 検索キーワード (Primary) 合算"
        
        # Check selection
        selected_rows = event.selection.rows
        
        target_indices = []
        is_breakdown = False # Whether to show breakdown colors
        
        if selected_rows:
            target_indices = selected_rows
            # If multi-select, show names in subtitle (truncated if too many)
            names = []
            for idx in target_indices:
                if idx < len(st.session_state['results']):
                    names.append(st.session_state['results'][idx].get('keyword', '?'))
            
            if len(names) > 3:
                graph_subtitle = f"対象: {', '.join(names[:3])} ...他"
            else:
                graph_subtitle = f"対象: {', '.join(names)}"
            
            is_breakdown = True # Use stacked colors
        else:
            # Default: Aggregate all Primary
            if 'results' in st.session_state:
                for i, res in enumerate(st.session_state['results']):
                    if res['type'] == 'Primary':
                        target_indices.append(i)
            # Default view doesn't breakdown by default (too messy), treats as single "Total"
            is_breakdown = False

        # Extract Data loop
        for idx in target_indices:
            if idx < len(st.session_state['results']):
                res = st.session_state['results'][idx]
                kw_label = res.get('keyword', 'Unknown')
                details = res.get('details', [])
                
                for d in details:
                    p_at = d.get('publishedAt')
                    if p_at is not None:
                        dt_val = None
                        if isinstance(p_at, pd.Timestamp):
                            dt_val = p_at
                        elif isinstance(p_at, str):
                            try:
                                dt_val = pd.to_datetime(p_at)
                            except: pass
                        
                        if dt_val:
                            # Use actual keyword if breakdown on, else "合算"
                            label = kw_label if is_breakdown else "合算"
                            graph_data_list.append({'date': dt_val, 'keyword': label})



        import altair as alt
        chart = None
        
        if graph_data_list:
            # Create DF
            df_dates = pd.DataFrame(graph_data_list)
            # Filter last 1 year
            one_year_ago = pd.Timestamp.now(tz='UTC') - pd.DateOffset(months=12)
            df_dates = df_dates[df_dates['date'] >= one_year_ago]
            
            if not df_dates.empty:
                # Group by Month
                # normalizing to start of month
                df_dates['month'] = df_dates['date'].dt.to_period('M').dt.to_timestamp()
                
                # --- A. Stacked Bar Data (Group by Month + Keyword) ---
                monthly_kw = df_dates.groupby(['month', 'keyword']).size().reset_index(name='count')
                monthly_kw['month_str'] = monthly_kw['month'].dt.strftime('%Y-%m')
                
                # --- B. Total Line Data (Group by Month only) ---
                start_date = one_year_ago.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
                full_range = pd.date_range(start=start_date, periods=13, freq='MS')
                
                monthly_total = df_dates.groupby('month').size().reindex(
                    full_range, fill_value=0
                ).reset_index(name='count')
                monthly_total.rename(columns={'index': 'month'}, inplace=True)
                monthly_total['month_str'] = monthly_total['month'].dt.strftime('%Y-%m')
                
                # Create Altair Chart
                # Base Axis
                x_axis = alt.X('month_str:O', axis=alt.Axis(title='年月', labelAngle=-45))
                
                # 1. Stacked Bar
                bars = alt.Chart(monthly_kw).mark_bar(opacity=0.7).encode(
                    x=x_axis,
                    y=alt.Y('count:Q', axis=alt.Axis(title='投稿数')),
                    color=alt.Color('keyword', title='キーワード') if is_breakdown else alt.value('#1f77b4'),
                    tooltip=['month_str', 'keyword', 'count']
                )
                
                # 2. Total Line
                line = alt.Chart(monthly_total).mark_line(point=True, color='#ff7f0e').encode(
                    x=x_axis,
                    y='count:Q',
                    tooltip=['month_str', 'count']
                )
                
                chart = alt.layer(bars, line).properties(
                    title=f'月別投稿数推移',
                    height=400
                )

                # Layout: Half width using columns
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown(f"##### {graph_title}")
                    st.caption(graph_subtitle)
                    if chart:
                        st.altair_chart(chart, use_container_width=True)
                    else:
                        st.info("直近1年間のデータがありません。")
                    
                with col_g2:
                    # --- Age Distribution Analysis (Top Tiers) ---
                    st.markdown("##### ⏳ 投稿経過日数ごとの分布 (上位層)")
                    st.caption("対象: 上位50%の動画 (再生数ベース)")
                    
                    # 1. Prepare Data
                    age_data = []
                    now = pd.Timestamp.now(tz='UTC')
                    
                    for idx in target_indices:
                        if idx < len(st.session_state['results']):
                            res = st.session_state['results'][idx]
                            details = res.get('details', [])
                            for d in details:
                                p_at = d.get('publishedAt')
                                v_count = d.get('viewCount', 0)
                                
                                if p_at is not None:
                                    dt_val = None
                                    if isinstance(p_at, pd.Timestamp):
                                        dt_val = p_at
                                    elif isinstance(p_at, str):
                                        try:
                                            dt_val = pd.to_datetime(p_at)
                                        except: pass
                                    
                                    if dt_val:
                                        # Force UTC for calc
                                        if dt_val.tzinfo is None:
                                            dt_val = dt_val.tz_localize('UTC')
                                        else:
                                            dt_val = dt_val.tz_convert('UTC')
                                            
                                        days_old = (now - dt_val).days
                                        age_data.append({'days_old': days_old, 'views': v_count})
                                        
                    if age_data:
                        df_age = pd.DataFrame(age_data)
                        
                        # 2. Calculate Tiers
                        if not df_age.empty:
                            q90 = df_age['views'].quantile(0.9)
                            q70 = df_age['views'].quantile(0.7)
                            q50 = df_age['views'].quantile(0.5)
                            
                            def get_tier(v):
                                if v >= q90: return '1. Top 10%'
                                elif v >= q70: return '2. Top 10-30%'
                                elif v >= q50: return '3. Top 30-50%'
                                else: return '4. Others'
                            
                            df_age['Tier'] = df_age['views'].apply(get_tier)
                            df_target = df_age[df_age['Tier'] != '4. Others'].copy()
                            
                            if not df_target.empty:
                                # 3. Binning
                                bins = [0, 30, 60, 90, 120, 150, 180, 360, 99999]
                                labels = ['~30日', '~60日', '~90日', '~120日', '~150日', '~180日', '~360日', '360日+']
                                df_target['AgeGroup'] = pd.cut(df_target['days_old'], bins=bins, labels=labels, right=True)
                                
                                # Aggregate
                                age_counts = df_target.groupby(['AgeGroup', 'Tier']).size().reset_index(name='count')
                                
                                # 4. Sorting Logic
                                # Right is Latest: Oldest -> Newest (360d+ ... ~30d)
                                sort_order = labels[::-1] 
                                
                                # 5. Altair Graph
                                age_chart = alt.Chart(age_counts).mark_bar().encode(
                                    x=alt.X('AgeGroup:O', axis=alt.Axis(title='経過日数', labelAngle=-45), sort=sort_order),
                                    y=alt.Y('count:Q', axis=alt.Axis(title='動画数')),
                                    color=alt.Color('Tier', scale=alt.Scale(
                                        domain=['1. Top 10%', '2. Top 10-30%', '3. Top 30-50%'],
                                        range=['#08519c', '#3182bd', '#6baed6'] # Dark Blue, Medium Blue, Light Blue
                                    ), title='層'),
                                    tooltip=['AgeGroup', 'Tier', 'count']
                                ).properties(
                                    height=400,
                                    title="上位層の経過日数分布"
                                )
                                

                                
                                st.altair_chart(age_chart, use_container_width=True)
                            else:
                                st.info("上位層（Top 50%以上）のデータがありません。")
                    else:
                        st.info("データがありません。")

        # --- Data Insights Section ---
        st.divider()
        st.subheader("3. データインサイト")
        
        col_i1, col_i2 = st.columns(2)
        
        with col_i1:
            st.markdown("#### 🔠 バズワード分析 (人気タイトルの傾向)")
            st.caption("上位30%の動画タイトルに頻出する「名詞」を抽出")
            
            # 1. Extract Titles from High Performing Videos
            # Re-using logic to get all data, then filter
            insight_data = []
            
            # Collect all data first to determine threshold
            all_views = []
            raw_items = []
            
            for idx in target_indices:
                if idx < len(st.session_state['results']):
                    res = st.session_state['results'][idx]
                    details = res.get('details', [])
                    for d in details:
                        tit = d.get('title')
                        v = d.get('viewCount', 0)
                        if tit and v > 0:
                            all_views.append(v)
                            raw_items.append({'title': tit, 'views': v})
            
            if raw_items:
                df_raw = pd.DataFrame(raw_items)
                q70 = df_raw['views'].quantile(0.7) # Top 30% threshold
                
                df_top = df_raw[df_raw['views'] >= q70]
                
                if not df_top.empty:
                    try:
                        from janome.tokenizer import Tokenizer
                        t = Tokenizer()
                        
                        word_stats = {} # {word: [count, total_views]}
                        
                        # Process Titles
                        for _, row in df_top.iterrows():
                            text = row['title']
                            views = row['views']
                            
                            tokens = t.tokenize(text)
                            for token in tokens:
                                pos = token.part_of_speech.split(',')[0]
                                if pos == '名詞':
                                    word = token.surface
                                    if len(word) > 1 and not word.isdigit() and word not in ['動画', '一覧', 'さん', 'こと', 'もの', 'ため', 'よう', 'わけ', 'ほう', 'これ', 'それ', 'あれ', 'どれ', 'どこ', 'いつ', '誰', '彼', '彼女', '私', '自分']:
                                        if word not in word_stats:
                                            word_stats[word] = [0, 0]
                                        word_stats[word][0] += 1
                                        word_stats[word][1] += views
                        
                        # Convert to List
                        ranking = []
                        for w, stat in word_stats.items():
                            freq = stat[0]
                            avg_v = int(stat[1] / freq)
                            # Round to nearest 1000 (lower 3 digits)
                            avg_v_rounded = int(round(avg_v, -3))
                            
                            if freq >= 2: # Min freq filter
                                ranking.append({'単語': w, '出現回数': freq, '平均再生数': avg_v_rounded})
                        
                        if ranking:
                            df_rank = pd.DataFrame(ranking)
                            df_rank = df_rank.sort_values(by=['出現回数', '平均再生数'], ascending=[False, False]).reset_index(drop=True)
                            
                            st.dataframe(
                                df_rank.head(20), 
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "単語": st.column_config.TextColumn("単語"),
                                    "出現回数": st.column_config.ProgressColumn("出現数", format="%d", min_value=0, max_value=int(df_rank['出現回数'].max())),
                                    "平均再生数": st.column_config.NumberColumn("平均再生", format="%d")
                                }
                            )
                        else:
                            st.info("頻出する有意な単語が見つかりませんでした。")
                            
                    except ImportError:
                        st.error("Janomeライブラリが見つかりません。")
                    except Exception as e:
                        st.error(f"解析エラー: {e}")
                else:
                    st.info("分析対象となる上位データが不足しています。")
            else:
                st.info("データがありません。")

        with col_i2:
            st.markdown("#### 🏆 チャンネル分析 (競合)")
            st.caption("指定キーワードでヒットした動画数と、その中の上位動画数")
            
            # Extract Data again for Channels
            ch_items = []
            for idx in target_indices:
                if idx < len(st.session_state['results']):
                    res = st.session_state['results'][idx]
                    details = res.get('details', [])
                    for d in details:
                        ch = d.get('channelTitle')
                        cid = d.get('channelId', '')
                        v = d.get('viewCount', 0)
                        if ch and v > 0:
                            ch_items.append({'channel': ch, 'channelId': cid, 'views': v})
                            
            if ch_items:
                df_ch_raw = pd.DataFrame(ch_items)
                
                # 1. Total Hit Count (All retrieved videos for this channel)
                ch_stats_all = df_ch_raw.groupby(['channel', 'channelId']).size().reset_index(name='hit_count')
                
                # 2. Filter Top 30% views
                q70_ch = df_ch_raw['views'].quantile(0.7)
                df_ch_top = df_ch_raw[df_ch_raw['views'] >= q70_ch]
                
                if not df_ch_top.empty:
                    # 3. Top Stats
                    ch_stats_top = df_ch_top.groupby(['channel', 'channelId']).agg(
                        top_count=('views', 'count'),
                        total_views=('views', 'sum'),
                        avg_views=('views', 'mean')
                    ).reset_index()
                    
                    # Rounding (Lower 3 digits, nearest 1000)
                    ch_stats_top['avg_views'] = ch_stats_top['avg_views'].apply(lambda x: int(round(x, -3)))
                    ch_stats_top['total_views'] = ch_stats_top['total_views'].apply(lambda x: int(round(x, -3)))
                    
                    # Merge
                    merged = pd.merge(ch_stats_top, ch_stats_all[['channel', 'hit_count']], on='channel', how='left')
                    
                    # Create Link
                    merged['link'] = merged['channelId'].apply(lambda x: f"https://www.youtube.com/channel/{x}" if x else None)
                    
                    # Sort
                    merged = merged.sort_values(by=['top_count', 'hit_count', 'total_views'], ascending=[False, False, False])
                    
                    # Format for Display
                    # Reorder columns
                    display_df = merged[['channel', 'link', 'hit_count', 'top_count', 'avg_views', 'total_views']]
                    
                    st.dataframe(
                        display_df.head(20),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "channel": st.column_config.TextColumn("チャンネル名"),
                            "link": st.column_config.LinkColumn("Link", display_text="🔗", width="small"),
                            "hit_count": st.column_config.NumberColumn("ヒット数", format="%d"),
                            "top_count": st.column_config.NumberColumn("TOP入り", format="%d"),
                            "avg_views": st.column_config.NumberColumn("平均再生", format="%d"),
                            "total_views": st.column_config.NumberColumn("総再生", format="%d"),
                        }
                    )
                else:
                    st.info("上位層のデータがありません。")
            else:
                 sample_res = st.session_state['results'][0]['details'][0] if st.session_state['results'] and st.session_state['results'][0].get('details') else {}
                 if 'channelTitle' not in sample_res:
                     st.warning("⚠️ チャンネル情報が見つかりません。分析を再実行してください。")
                 else:
                     st.info("データがありません。")

        # --- Video List Section ---
        st.divider()
        st.subheader("4. 動画リスト")
        
        col_list = st.container() # Full width container for centered layout
        
        with col_list:
            # 1. Aggregate & Deduplicate
            video_map = {} # videoId -> {data, tags: [], min_rank: 999}
            all_views_list = []
            
            for idx in target_indices:
                if idx < len(st.session_state['results']):
                    res = st.session_state['results'][idx]
                    kw = res.get('keyword', '')
                    details = res.get('details', [])
                    
                    for d in details:
                        vid = d.get('videoId')
                        if not vid: continue 
                        
                        rank = d.get('rank', 999)
                        tag_item = {'kw': kw, 'rank': rank}
                        
                        if vid not in video_map:
                            video_map[vid] = {
                                'videoId': vid,
                                'thumbnail': d.get('thumbnail', ''),
                                'title': d.get('title', ''),
                                'viewCount': d.get('viewCount', 0),
                                'publishedAt': d.get('publishedAt'),
                                'channelTitle': d.get('channelTitle', ''),
                                'channelId': d.get('channelId', ''),
                                'tags': [tag_item],
                                'min_rank': rank
                            }
                            all_views_list.append(d.get('viewCount', 0))
                        else:
                            video_map[vid]['tags'].append(tag_item)
                            if rank < video_map[vid]['min_rank']:
                                video_map[vid]['min_rank'] = rank
            
            if video_map:
                # --- Fetch Channel Statistics (Subscribers, Video Count) ---
                channel_data_map = {}
                unique_cids = list(set([d['channelId'] for d in video_map.values() if d.get('channelId')]))
                
                if unique_cids and api_key:
                    try:
                        # Use YouTubeClient for robust batching and retries
                        # Assumes YouTubeClient is imported from youtube_api
                        client_temp = YouTubeClient(api_key.strip())
                        channel_items = client_temp.get_channel_details(unique_cids)
                        
                        if not channel_items:
                            # If no items returned despite having CIDs, likely an API/Quota issue
                            st.warning("⚠️ チャンネル詳細情報の取得に失敗しました (結果0件)。APIキーの権限や割り当てを確認してください。")
                        
                        for item in channel_items:
                            cid = item['id']
                            stats = item.get('statistics', {})
                            
                            channel_data_map[cid] = {
                                'subscriberCount': stats.get('subscriberCount', '0'), 
                                'videoCount': stats.get('videoCount', '0'),
                            }
                            

                        



                            
                    except Exception as e:
                        st.warning(f"チャンネル情報の取得中にエラーが発生しました: {e}")
                            
                elif not api_key:
                    st.warning("登録者数を表示するにはAPIキーが必要です。")
                
                # 2. Tier/Rank Calculation
                df_v = pd.DataFrame(all_views_list, columns=['views'])
                q90 = df_v['views'].quantile(0.9)
                q70 = df_v['views'].quantile(0.7)
                q50 = df_v['views'].quantile(0.5)
                
                def get_tier_data(v, thresholds=None, short_label=False):
                    # Returns: Label, Text Color, Border Color
                    # thresholds: (q90, q70, q50) tuple. If None, uses global search result thresholds.
                    
                    t_q90, t_q70, t_q50 = thresholds if thresholds else (q90, q70, q50)
                    
                    if v >= t_q90: 
                        return ("A" if short_label else "A 10%", "#FFD700", "rgb(255, 215, 11)") # A: Top 10%
                    elif v >= t_q70: 
                        return ("B" if short_label else "B 10-30%", "#FFA500", "#FF8C00") # B: 10-30%
                    elif v >= t_q50: 
                        return ("C" if short_label else "C 30-50%", "#00BFFF", "#00008B") # C: 30-50%
                    else: 
                        return ("D" if short_label else "D 50-100%", "#D3D3D3", "#696969") # D: 50-100%
                
                def fmt_num(n_str):
                    try:
                        n = int(n_str)
                        if n >= 10000:
                            return f"{n/10000:.1f}万"
                        return f"{n:,}"
                    except: return "---"

                # 3. Create List Items
                list_items = []
                for vid, data in video_map.items():
                    # Existing Rank Logic (Search Result Relative)
                    tier_label, tier_color, tier_border = get_tier_data(data['viewCount'], short_label=False)
                    

                    data['tier_label'] = tier_label
                    data['tier_color'] = tier_color
                    data['tier_border'] = tier_border
                    cid = data.get('channelId')
                    # Add Channel Stats
                    c_stats = channel_data_map.get(cid, {})
                    data['sub_count'] = fmt_num(c_stats.get('subscriberCount', '0'))
                    data['total_videos'] = fmt_num(c_stats.get('videoCount', '0'))
                    
                    # --- Date Tag Calculation (10d, 30d...) ---
                    p_at = data.get('publishedAt')
                    date_tag_str = ""
                    if p_at:
                        try:
                            if isinstance(p_at, str):
                                dt = pd.to_datetime(p_at).tz_localize(None)
                            else:
                                dt = p_at.tz_localize(None) if p_at.tzinfo else p_at
                            
                            now_ts = pd.Timestamp.now().floor('D')
                            diff_days = (now_ts - dt).days
                            
                            if diff_days <= 10: date_tag_str = "10日以内"
                            elif diff_days <= 30: date_tag_str = "30日以内"
                            elif diff_days <= 90: date_tag_str = "90日以内"
                            elif diff_days <= 180: date_tag_str = "180日以内"
                            elif diff_days <= 360: date_tag_str = "360日以内"
                            else: date_tag_str = "1年以上"
                        except: pass
                    data['date_tag_str'] = date_tag_str
                    # ------------------------------------------

                    # Sort tags by rank
                    sorted_tags = sorted(data['tags'], key=lambda x: x['rank'])
                    data['sorted_tags'] = sorted_tags
                    list_items.append(data)
                
                df_list = pd.DataFrame(list_items)
                
                # 4. Filters & Sort
                with st.expander("🔍 絞り込み・並替え設定", expanded=True):
                    c_f1, c_f2, c_f3 = st.columns(3)
                    with c_f1:
                        date_filter = st.radio("投稿日", ["すべて", "30日以内", "90日以内", "180日以内"])
                    with c_f2:
                        rank_filter = st.multiselect("ランク", ['A 10%', 'B 10-30%', 'C 30-50%', 'D 50-100%'], default=[])
                    with c_f3:
                        sort_mode = st.radio("並び替え", ["最新投稿順", "検索順位順", "再生数順"])
                        
                # Filter Logic
                now = pd.Timestamp.now(tz=None)
                if date_filter != "すべて":
                    days = int(date_filter.replace("日以内", ""))
                    cutoff = now - pd.Timedelta(days=days)
                    df_list['publishedAt'] = df_list['publishedAt'].dt.tz_localize(None)
                    df_list = df_list[df_list['publishedAt'] >= cutoff]
                
                if rank_filter:
                    df_list = df_list[df_list['tier_label'].isin(rank_filter)]
                    
                # Sort Logic
                if sort_mode == "最新投稿順":
                    df_list = df_list.sort_values('publishedAt', ascending=False)
                elif sort_mode == "検索順位順":
                    df_list = df_list.sort_values('min_rank', ascending=True)
                else:
                    df_list = df_list.sort_values('viewCount', ascending=False)
                    
                # 5. Display (HTML Layout)
                if not df_list.empty:
                    st.markdown("---")
                    for _, row in df_list.iterrows():
                        with st.container():
                            # Centered Layout: Side padding (0.5), Content (2.5 + 4.5), Side padding (0.5)
                            _, c_img, c_detail, _ = st.columns([0.5, 2.5, 4.5, 0.5])
                            
                            with c_img:
                                if row['thumbnail']:
                                    st.image(row['thumbnail'], use_container_width=True)
                                else:
                                    st.text("No Image")
                                    
                            with c_detail:
                                # Data Prep
                                vid_url = f"https://www.youtube.com/watch?v={row['videoId']}"
                                title = row['title']
                                date_str = row['publishedAt'].strftime('%Y/%m/%d')
                                views_val = int(row['viewCount'])
                                channel = row['channelTitle']
                                
                                # Channel Extras
                                sub_cnt = row.get('sub_count', '---')
                                # vid_cnt removed from display as per user request to avoid API impression for frequency
                                
                                # Badges HTML (Rank: Black BG, Colored Text/Border)
                                tier_html = f'<span style="display: inline-flex; align-items: center; height: 32px; background-color: rgb(0, 0, 0); color: {row["tier_color"]}; border: 2px solid {row["tier_border"]}; padding: 0 10px; border-radius: 6px; font-weight: 900; font-size: 0.9em; box-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-right: 5px;">{row["tier_label"]}</span>'
                                
                                # Date Tag HTML (New Styling)
                                date_tag_html = ""
                                if row.get('date_tag_str'):
                                    raw_tag = row["date_tag_str"]
                                    # Split number and text (e.g. "10日以内" -> "10", "日以内")
                                    # Simple regex or string manipulation
                                    num_part = "".join([c for c in raw_tag if c.isdigit()])
                                    text_part = "".join([c for c in raw_tag if not c.isdigit()])
                                    
                                    # Adjusted CSS as requested
                                    # Flattened to single line to prevent Streamlit/Markdown rendering issues
                                    date_tag_html = f'<span style="display: inline-flex; align-items: baseline; height: 32px; background-color: rgb(0, 0, 0); color: rgb(170, 170, 170); border: 2px solid rgb(104, 104, 104); padding: 0 10px; border-radius: 6px; margin-right: 5px; box-shadow: 1px 1px 2px rgba(0,0,0,0.2);"><span style="font-size: 1em; font-weight: 700; color: #ddd; margin-right: 2px;">{num_part}</span><span style="font-size: 0.75em; font-weight: normal;">{text_part}</span></span>'
                                

                                # Tags HTML
                                tags_html = ""
                                for t in row['sorted_tags']:
                                    tags_html += f'<span style="display: inline-block; background-color: rgb(85, 85, 85); color: rgb(229, 229, 229); border: 1px solid rgb(204, 204, 204); padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-right: 6px; margin-bottom: 6px;">{t["kw"]} <span style="font-weight:bold; font-size:1.1em; margin-left:2px;">{t["rank"]}</span><span style="font-size:0.75em">位</span></span>'

                                # Views Badge (Prominent: Dark BG, White Text, Border)
                                views_badge = f'<span style="display: inline-flex; align-items: center; height: 32px; background-color: rgb(24, 24, 24); color: #fff; border: 2px solid rgb(117, 117, 117); padding: 0 12px; border-radius: 6px; font-weight: 600; font-size: 1.1em; box-shadow: 2px 2px 4px rgba(0,0,0,0.2);">👀 {views_val:,}</span>'

                                # Main Content HTML (Metadata Updated)
                                # Format: Channel | Subscribers | Date
                                content_html = f"""
<div style="margin-bottom: 5px;">
    <a href="{vid_url}" target="_blank" style="font-size: 1.25em; font-weight: bold; text-decoration: none; color: inherit; line-height: 1.4;">{title}</a>
</div>
<div style="font-size: 0.9em; color: #666; margin-bottom: 12px;">
    📺 {channel} &nbsp;|&nbsp; 👥 登録者: {sub_cnt} &nbsp;|&nbsp; 📅 {date_str}
</div>
<div style="margin-bottom: 15px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
    {views_badge}
    {tier_html}
    {date_tag_html}
</div>
<div style="margin-bottom: 10px;">
    {tags_html}
</div>
"""
                                st.markdown(content_html, unsafe_allow_html=True)
                                


                        st.markdown("---")
                else:
                    st.info("条件に一致する動画がありません。")
            else:
                st.info("データがありません（再分析が必要です）。")

        # --- Right Column: AI Summary Display ---



    else:
        st.warning("データが見つかりませんでした。")
