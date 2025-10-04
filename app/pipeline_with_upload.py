#!/usr/bin/env python3
"""
Complete Pipeline with Social Media Upload

This script runs the full news-to-video pipeline and automatically uploads
the generated videos to social media platforms.

Usage:
    python pipeline_with_upload.py
"""

import os
import sys
from datetime import datetime

# Import our modules
from full_pipeline import run_full_pipeline, run_single_article_pipeline
from social_media_uploader import upload_video_from_pipeline, SocialMediaUploader

def run_pipeline_with_upload(max_articles: int = 3, upload_to_platforms: list = None, 
                            output_name: str = None, ref_audio_path: str = "assets/voice_08.wav"):
    """
    Run the complete pipeline and upload videos to social media.
    
    Args:
        max_articles: Maximum number of articles to process
        upload_to_platforms: List of platforms to upload to ['youtube', 'instagram', 'tiktok', 'snapchat']
        output_name: Custom name for output files
        ref_audio_path: Path to reference audio for voice cloning
    
    Returns:
        dict: Complete results including upload status
    """
    
    print("🚀 Starting Complete Pipeline with Social Media Upload")
    print("=" * 60)
    
    # Default to all platforms if none specified
    if upload_to_platforms is None:
        upload_to_platforms = ['youtube', 'instagram', 'tiktok', 'snapchat']
    
    # Run the video generation pipeline
    print("📹 Step 1: Running video generation pipeline...")
    pipeline_results = run_full_pipeline(max_articles=max_articles, output_name=output_name, ref_audio_path=ref_audio_path)
    
    if not pipeline_results:
        print("❌ Pipeline failed, skipping uploads")
        return None
    
    # Upload videos to social media
    print(f"\n📱 Step 2: Uploading to social media platforms: {', '.join(upload_to_platforms)}")
    upload_results = []
    
    uploader = SocialMediaUploader()
    
    for i, (script_data, video_files) in enumerate(zip(pipeline_results['scripts'], 
                                                      [pipeline_results['video_files'][i:i+3] for i in range(0, len(pipeline_results['video_files']), 3)])):
        
        print(f"\n--- Uploading Article {i+1} Videos ---")
        
        # Use the burned video (with subtitles) for upload
        burned_video = None
        for video_file in video_files:
            if 'burned' in video_file:
                burned_video = video_file
                break
        
        if not burned_video:
            print(f"❌ No burned video found for article {i+1}")
            continue
        
        # Generate title and description
        headline = script_data['headline']['title']
        script = script_data['script']
        
        title = f"NFL News: {headline}"
        description = f"{script}\n\n#NFL #Football #SportsNews #BreakingNews #ESPN"
        tags = ["NFL", "Football", "Sports", "News", "Breaking", "ESPN"]
        
        # Upload to specified platforms
        article_upload_results = {
            "article": i+1,
            "headline": headline,
            "video_file": burned_video,
            "uploads": {}
        }
        
        for platform in upload_to_platforms:
            print(f"  📤 Uploading to {platform.title()}...")
            
            try:
                if platform == 'youtube':
                    result = uploader.upload_to_youtube(burned_video, title, description, tags)
                elif platform == 'instagram':
                    result = uploader.upload_to_instagram(burned_video, description)
                elif platform == 'tiktok':
                    result = uploader.upload_to_tiktok(burned_video, description)
                elif platform == 'snapchat':
                    result = uploader.upload_to_snapchat(burned_video, description)
                else:
                    result = {"success": False, "error": f"Unknown platform: {platform}"}
                
                article_upload_results["uploads"][platform] = result
                
                if result.get("success"):
                    print(f"    ✅ {platform.title()}: Success")
                else:
                    print(f"    ❌ {platform.title()}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"    ❌ {platform.title()}: {e}")
                article_upload_results["uploads"][platform] = {"success": False, "error": str(e)}
        
        upload_results.append(article_upload_results)
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 Complete Pipeline with Upload Finished!")
    print(f"📊 Final Summary:")
    print(f"  - Articles processed: {len(pipeline_results['scripts'])}")
    print(f"  - Videos generated: {len(pipeline_results['video_files'])}")
    print(f"  - Upload attempts: {len(upload_results)}")
    
    # Count successful uploads
    total_uploads = 0
    successful_uploads = 0
    
    for result in upload_results:
        for platform, upload_result in result["uploads"].items():
            total_uploads += 1
            if upload_result.get("success"):
                successful_uploads += 1
    
    print(f"  - Successful uploads: {successful_uploads}/{total_uploads}")
    
    # Show upload results
    print(f"\n📱 Upload Results:")
    for result in upload_results:
        print(f"\n  Article {result['article']}: {result['headline']}")
        for platform, upload_result in result["uploads"].items():
            status = "✅" if upload_result.get("success") else "❌"
            print(f"    {status} {platform.title()}: {upload_result.get('url', upload_result.get('error', 'Unknown'))}")
    
    return {
        "pipeline_results": pipeline_results,
        "upload_results": upload_results,
        "summary": {
            "articles_processed": len(pipeline_results['scripts']),
            "videos_generated": len(pipeline_results['video_files']),
            "total_uploads": total_uploads,
            "successful_uploads": successful_uploads
        }
    }

def main():
    """CLI interface for the complete pipeline with upload."""
    
    print("🎬 Complete News-to-Video Pipeline with Social Media Upload")
    print("=" * 60)
    print("1. Full pipeline with upload to all platforms")
    print("2. Full pipeline with upload to specific platforms")
    print("3. Single article pipeline with upload")
    print("4. Upload existing videos only")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        # Full pipeline with all platforms
        max_articles = input("Max articles to process (default 3): ").strip()
        max_articles = int(max_articles) if max_articles.isdigit() else 3
        
        output_name = input("Output name (optional): ").strip() or None
        
        print(f"\n🚀 Starting full pipeline with upload to all platforms...")
        results = run_pipeline_with_upload(max_articles=max_articles, output_name=output_name)
        
    elif choice == "2":
        # Full pipeline with specific platforms
        max_articles = input("Max articles to process (default 3): ").strip()
        max_articles = int(max_articles) if max_articles.isdigit() else 3
        
        print("Available platforms: youtube, instagram, tiktok, snapchat")
        platforms_input = input("Enter platforms (comma-separated): ").strip()
        platforms = [p.strip() for p in platforms_input.split(",")] if platforms_input else ['youtube']
        
        output_name = input("Output name (optional): ").strip() or None
        
        print(f"\n🚀 Starting full pipeline with upload to: {', '.join(platforms)}")
        results = run_pipeline_with_upload(max_articles=max_articles, upload_to_platforms=platforms, output_name=output_name)
        
    elif choice == "3":
        # Single article pipeline with upload
        article_url = input("Enter article URL: ").strip()
        if not article_url:
            print("❌ URL is required")
            return
        
        print("Available platforms: youtube, instagram, tiktok, snapchat")
        platforms_input = input("Enter platforms (comma-separated): ").strip()
        platforms = [p.strip() for p in platforms_input.split(",")] if platforms_input else ['youtube']
        
        output_name = input("Output name (optional): ").strip() or None
        
        print(f"\n🚀 Starting single article pipeline with upload...")
        
        # Run single article pipeline
        pipeline_results = run_single_article_pipeline(article_url, output_name=output_name)
        
        if pipeline_results:
            # Upload the generated video
            uploader = SocialMediaUploader()
            burned_video = None
            for video_file in pipeline_results['video_files']:
                if 'burned' in video_file:
                    burned_video = video_file
                    break
            
            if burned_video:
                title = f"NFL News: {pipeline_results.get('script', 'Latest Updates')[:50]}..."
                description = f"{pipeline_results.get('script', '')}\n\n#NFL #Football #SportsNews"
                
                print(f"📤 Uploading to platforms: {', '.join(platforms)}")
                for platform in platforms:
                    if platform == 'youtube':
                        uploader.upload_to_youtube(burned_video, title, description)
                    elif platform == 'instagram':
                        uploader.upload_to_instagram(burned_video, description)
                    elif platform == 'tiktok':
                        uploader.upload_to_tiktok(burned_video, description)
                    elif platform == 'snapchat':
                        uploader.upload_to_snapchat(burned_video, description)
        
    elif choice == "4":
        # Upload existing videos only
        from social_media_uploader import main as uploader_main
        uploader_main()
        
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
