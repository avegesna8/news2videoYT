#!/usr/bin/env python3
"""
Complete News-to-Video Pipeline

This script performs the full workflow:
1. Scrape NFL news headlines
2. Select top 3 most important headlines
3. Generate comedic script from article content
4. Generate audio from script
5. Generate video with subtitles

Usage:
    python full_pipeline.py
"""

import os
import sys
from datetime import datetime

# Import all our modules
from get_news_links import get_nfl_links
from espn_scraper import get_link, parse_espn_article_html
from llm_functions import select_top_three_headlines, generate_comedic_script
from audio_generator import generate_audio_from_runpod
from video_generator import generate_video
from srt_generator import generate_srt_from_audio

def run_full_pipeline(max_articles: int = 3, output_name: str = None, ref_audio_path: str = "assets/voice_08.wav"):
    """
    Run the complete news-to-video pipeline.
    
    Args:
        max_articles: Maximum number of articles to process (default: 3)
        output_name: Custom name for output files (optional)
        ref_audio_path: Path to reference audio for voice cloning
    
    Returns:
        dict: Results containing all generated file paths
    """
    
    print("🚀 Starting News-to-Video Pipeline")
    print("=" * 50)
    
    # Generate output name if not provided
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"news_video_{timestamp}"
    
    results = {
        "output_name": output_name,
        "headlines": [],
        "scripts": [],
        "audio_files": [],
        "video_files": [],
        "srt_files": []
    }
    
    try:
        # Step 1: Get NFL news headlines
        print("\n📰 Step 1: Fetching NFL news headlines...")
        news_items = get_nfl_links()
        print(f"Found {len(news_items)} news items")
        
        if not news_items:
            raise Exception("No news items found")
        
        # Step 2: Select top headlines
        print("\n🎯 Step 2: Selecting top headlines...")
        top_headlines = select_top_three_headlines(news_items)
        print(f"Selected {len(top_headlines)} top headlines:")
        
        for i, item in enumerate(top_headlines, 1):
            print(f"  {i}. {item['title']}")
            results["headlines"].append(item)
        
        # Step 3: Process each headline
        print(f"\n📝 Step 3: Processing top {min(max_articles, len(top_headlines))} articles...")
        
        for i, headline in enumerate(top_headlines[:max_articles], 1):
            print(f"\n--- Processing Article {i}/{min(max_articles, len(top_headlines))} ---")
            print(f"Title: {headline['title']}")
            print(f"URL: {headline['url']}")
            
            try:
                # Get article content
                print("  📖 Scraping article content...")
                response = get_link(headline['url'])
                article_data = parse_espn_article_html(response.text, response.url)
                
                # Generate comedic script
                print("  ✍️  Generating comedic script...")
                script_result = generate_comedic_script(article_data)
                
                if script_result['is_too_long']:
                    print("  ⚠️  Article too long, skipping...")
                    continue
                
                script = script_result['script']
                print(f"  📄 Script: {script[:100]}...")
                results["scripts"].append({
                    "headline": headline,
                    "script": script,
                    "article_data": article_data
                })
                
                # Generate audio
                print("  🎵 Generating audio...")
                audio_path = generate_audio_from_runpod(script, ref_audio_path)
                print(f"  🎧 Audio saved: {audio_path}")
                results["audio_files"].append(audio_path)
                
                # Generate video with subtitles
                print("  🎬 Generating video with subtitles...")
                video_output_name = f"{output_name}_article_{i}"
                generate_video(audio_path, script, video_output_name)
                
                # Get the generated video files
                from video_generator import OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT, OUT_SRT
                video_files = [OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT]
                results["video_files"].extend(video_files)
                results["srt_files"].append(OUT_SRT)
                
                print(f"  ✅ Video generated: {video_output_name}")
                
            except Exception as e:
                print(f"  ❌ Error processing article {i}: {e}")
                continue
        
        # Summary
        print("\n" + "=" * 50)
        print("🎉 Pipeline Complete!")
        print(f"📊 Results Summary:")
        print(f"  - Headlines processed: {len(results['headlines'])}")
        print(f"  - Scripts generated: {len(results['scripts'])}")
        print(f"  - Audio files: {len(results['audio_files'])}")
        print(f"  - Video files: {len(results['video_files'])}")
        print(f"  - SRT files: {len(results['srt_files'])}")
        
        print(f"\n📁 Output Files:")
        for audio in results['audio_files']:
            print(f"  🎧 Audio: {audio}")
        for video in results['video_files']:
            print(f"  🎬 Video: {video}")
        for srt in results['srt_files']:
            print(f"  📝 Subtitles: {srt}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        return None

def run_single_article_pipeline(article_url: str, output_name: str = None, ref_audio_path: str = "assets/voice_08.wav"):
    """
    Run pipeline for a single article URL.
    
    Args:
        article_url: URL of the article to process
        output_name: Custom name for output files (optional)
        ref_audio_path: Path to reference audio for voice cloning
    
    Returns:
        dict: Results containing all generated file paths
    """
    
    print("🚀 Starting Single Article Pipeline")
    print("=" * 50)
    
    # Generate output name if not provided
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"single_article_{timestamp}"
    
    results = {
        "output_name": output_name,
        "article_url": article_url,
        "script": None,
        "audio_file": None,
        "video_files": [],
        "srt_file": None
    }
    
    try:
        # Get article content
        print(f"📖 Scraping article: {article_url}")
        response = get_link(article_url)
        article_data = parse_espn_article_html(response.text, response.url)
        
        # Generate comedic script
        print("✍️  Generating comedic script...")
        script_result = generate_comedic_script(article_data)
        
        if script_result['is_too_long']:
            raise Exception("Article is too long for script generation")
        
        script = script_result['script']
        print(f"📄 Script: {script[:100]}...")
        results["script"] = script
        
        # Generate audio
        print("🎵 Generating audio...")
        audio_path = generate_audio_from_runpod(script, ref_audio_path)
        print(f"🎧 Audio saved: {audio_path}")
        results["audio_file"] = audio_path
        
        # Generate video with subtitles
        print("🎬 Generating video with subtitles...")
        generate_video(audio_path, script, output_name)
        
        # Get the generated files
        from video_generator import OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT, OUT_SRT
        results["video_files"] = [OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT]
        results["srt_file"] = OUT_SRT
        
        print("\n" + "=" * 50)
        print("🎉 Single Article Pipeline Complete!")
        print(f"📁 Output Files:")
        print(f"  🎧 Audio: {results['audio_file']}")
        for video in results['video_files']:
            print(f"  🎬 Video: {video}")
        print(f"  📝 Subtitles: {results['srt_file']}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        return None

def main():
    """CLI interface for the pipeline."""
    
    print("🎬 News-to-Video Pipeline")
    print("=" * 30)
    print("1. Full pipeline (scrape headlines → select top 3 → generate videos)")
    print("2. Single article pipeline (process one specific article)")
    print("3. Test with existing audio file")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        # Full pipeline
        max_articles = input("Max articles to process (default 3): ").strip()
        max_articles = int(max_articles) if max_articles.isdigit() else 3
        
        output_name = input("Output name (optional): ").strip() or None
        
        print(f"\n🚀 Starting full pipeline with {max_articles} articles...")
        results = run_full_pipeline(max_articles=max_articles, output_name=output_name)
        
    elif choice == "2":
        # Single article pipeline
        article_url = input("Enter article URL: ").strip()
        if not article_url:
            print("❌ URL is required")
            return
        
        output_name = input("Output name (optional): ").strip() or None
        
        print(f"\n🚀 Starting single article pipeline...")
        results = run_single_article_pipeline(article_url, output_name=output_name)
        
    elif choice == "3":
        # Test with existing audio
        from video_generator import get_audio_file_by_name, generate_video
        
        try:
            audio_filename = input("Enter audio filename (e.g., audio_20251004_132034.wav): ").strip()
            if not audio_filename:
                print("❌ Audio filename is required")
                return
            
            audio_path = get_audio_file_by_name(audio_filename)
            script_text = input("Enter script text for subtitles: ").strip()
            
            if not script_text:
                print("❌ Script text is required")
                return
            
            output_name = input("Output name (optional): ").strip() or "test_video"
            
            print(f"\n🚀 Generating video from existing audio...")
            generate_video(audio_path, script_text, output_name)
            print("✅ Video generation complete!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
