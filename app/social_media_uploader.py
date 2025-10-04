#!/usr/bin/env python3
"""
Social Media Uploader

This script automatically uploads generated videos to:
- YouTube
- Instagram
- TikTok
- Snapchat

Usage:
    python social_media_uploader.py
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

class SocialMediaUploader:
    """Handles uploading videos to various social media platforms."""
    
    def __init__(self):
        self.results = {}
        
    def upload_to_youtube(self, video_path: str, title: str, description: str, 
                         tags: List[str] = None, category_id: str = "22") -> Dict:
        """
        Upload video to YouTube using YouTube Data API v3.
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category (22 = People & Blogs)
        
        Returns:
            Dict with upload result
        """
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            # YouTube API scopes
            SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
            
            # Load credentials
            creds = None
            token_file = 'youtube_token.json'
            credentials_file = 'youtube_credentials.json'
            
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(credentials_file):
                        print("❌ YouTube credentials file not found. Please download from Google Cloud Console.")
                        return {"success": False, "error": "Missing credentials"}
                    
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # Build YouTube service
            youtube = build('youtube', 'v3', credentials=creds)
            
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': 'public'  # or 'private', 'unlisted'
                }
            }
            
            # Upload video
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            
            print(f"📺 Uploading to YouTube: {title}")
            response = request.execute()
            
            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            print(f"✅ YouTube upload successful: {video_url}")
            return {
                "success": True,
                "platform": "YouTube",
                "video_id": video_id,
                "url": video_url
            }
            
        except Exception as e:
            print(f"❌ YouTube upload failed: {e}")
            return {"success": False, "platform": "YouTube", "error": str(e)}
    
    def upload_to_instagram(self, video_path: str, caption: str, 
                           access_token: str = None) -> Dict:
        """
        Upload video to Instagram using Instagram Basic Display API.
        
        Args:
            video_path: Path to video file
            caption: Video caption
            access_token: Instagram access token
        
        Returns:
            Dict with upload result
        """
        try:
            if not access_token:
                access_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
            
            if not access_token:
                print("❌ Instagram access token not found")
                return {"success": False, "error": "Missing access token"}
            
            # Instagram requires a two-step process: create media container, then publish
            base_url = "https://graph.facebook.com/v18.0"
            
            # Step 1: Create media container
            container_url = f"{base_url}/me/media"
            container_data = {
                'media_type': 'VIDEO',
                'video_url': video_path,  # This should be a publicly accessible URL
                'caption': caption,
                'access_token': access_token
            }
            
            print(f"📸 Creating Instagram media container...")
            container_response = requests.post(container_url, data=container_data)
            
            if container_response.status_code != 200:
                print(f"❌ Instagram container creation failed: {container_response.text}")
                return {"success": False, "error": "Container creation failed"}
            
            container_id = container_response.json()['id']
            
            # Step 2: Publish the media
            publish_url = f"{base_url}/{container_id}/media_publish"
            publish_data = {
                'creation_id': container_id,
                'access_token': access_token
            }
            
            print(f"📸 Publishing to Instagram...")
            publish_response = requests.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                media_id = publish_response.json()['id']
                print(f"✅ Instagram upload successful: {media_id}")
                return {
                    "success": True,
                    "platform": "Instagram",
                    "media_id": media_id
                }
            else:
                print(f"❌ Instagram publish failed: {publish_response.text}")
                return {"success": False, "error": "Publish failed"}
                
        except Exception as e:
            print(f"❌ Instagram upload failed: {e}")
            return {"success": False, "platform": "Instagram", "error": str(e)}
    
    def upload_to_tiktok(self, video_path: str, description: str, 
                        access_token: str = None) -> Dict:
        """
        Upload video to TikTok using TikTok for Developers API.
        
        Args:
            video_path: Path to video file
            description: Video description
            access_token: TikTok access token
        
        Returns:
            Dict with upload result
        """
        try:
            if not access_token:
                access_token = os.getenv('TIKTOK_ACCESS_TOKEN')
            
            if not access_token:
                print("❌ TikTok access token not found")
                return {"success": False, "error": "Missing access token"}
            
            # TikTok API endpoints
            base_url = "https://open-api.tiktok.com"
            
            # Step 1: Initialize upload
            init_url = f"{base_url}/share/video/upload/"
            init_data = {
                'source_info': json.dumps({
                    'source': 'FILE_UPLOAD',
                    'video_size': os.path.getsize(video_path),
                    'chunk_size': 10485760,  # 10MB chunks
                    'total_chunk_count': 1
                })
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            print(f"🎵 Initializing TikTok upload...")
            init_response = requests.post(init_url, json=init_data, headers=headers)
            
            if init_response.status_code != 200:
                print(f"❌ TikTok init failed: {init_response.text}")
                return {"success": False, "error": "Init failed"}
            
            upload_url = init_response.json()['data']['upload_url']
            
            # Step 2: Upload video file
            print(f"🎵 Uploading video to TikTok...")
            with open(video_path, 'rb') as video_file:
                upload_response = requests.put(upload_url, data=video_file)
            
            if upload_response.status_code != 200:
                print(f"❌ TikTok upload failed: {upload_response.text}")
                return {"success": False, "error": "Upload failed"}
            
            # Step 3: Publish video
            publish_url = f"{base_url}/share/video/publish/"
            publish_data = {
                'post_info': json.dumps({
                    'title': description,
                    'privacy_level': 'MUTUAL_FOLLOW_FRIEND',
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                    'video_cover_timestamp_ms': 1000
                }),
                'source_info': json.dumps({
                    'source': 'FILE_UPLOAD',
                    'video_size': os.path.getsize(video_path),
                    'chunk_size': 10485760,
                    'total_chunk_count': 1
                })
            }
            
            print(f"🎵 Publishing to TikTok...")
            publish_response = requests.post(publish_url, json=publish_data, headers=headers)
            
            if publish_response.status_code == 200:
                video_id = publish_response.json()['data']['publish_id']
                print(f"✅ TikTok upload successful: {video_id}")
                return {
                    "success": True,
                    "platform": "TikTok",
                    "video_id": video_id
                }
            else:
                print(f"❌ TikTok publish failed: {publish_response.text}")
                return {"success": False, "error": "Publish failed"}
                
        except Exception as e:
            print(f"❌ TikTok upload failed: {e}")
            return {"success": False, "platform": "TikTok", "error": str(e)}
    
    def upload_to_snapchat(self, video_path: str, caption: str, 
                          access_token: str = None) -> Dict:
        """
        Upload video to Snapchat using Snapchat for Developers API.
        
        Args:
            video_path: Path to video file
            caption: Video caption
            access_token: Snapchat access token
        
        Returns:
            Dict with upload result
        """
        try:
            if not access_token:
                access_token = os.getenv('SNAPCHAT_ACCESS_TOKEN')
            
            if not access_token:
                print("❌ Snapchat access token not found")
                return {"success": False, "error": "Missing access token"}
            
            # Snapchat API endpoints
            base_url = "https://adsapi.snapchat.com/v1"
            
            # Create ad account (required for posting)
            ad_account_url = f"{base_url}/adaccounts"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Note: Snapchat's API is primarily for advertising
            # For organic content posting, you might need to use Snapchat's Creator Hub API
            # or consider using a third-party service like Buffer or Hootsuite
            
            print("📱 Snapchat upload requires Creator Hub API or third-party service")
            print("📱 Consider using Buffer, Hootsuite, or Snapchat's official Creator tools")
            
            return {
                "success": False,
                "platform": "Snapchat",
                "error": "Requires Creator Hub API or third-party service"
            }
            
        except Exception as e:
            print(f"❌ Snapchat upload failed: {e}")
            return {"success": False, "platform": "Snapchat", "error": str(e)}
    
    def upload_to_all_platforms(self, video_path: str, title: str, description: str, 
                               tags: List[str] = None) -> Dict:
        """
        Upload video to all supported platforms.
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags
        
        Returns:
            Dict with results from all platforms
        """
        print(f"🚀 Uploading video to all platforms: {title}")
        print("=" * 50)
        
        results = {
            "video_path": video_path,
            "title": title,
            "description": description,
            "tags": tags or [],
            "uploads": {}
        }
        
        # Upload to YouTube
        print("\n📺 Uploading to YouTube...")
        results["uploads"]["youtube"] = self.upload_to_youtube(video_path, title, description, tags)
        
        # Upload to Instagram
        print("\n📸 Uploading to Instagram...")
        results["uploads"]["instagram"] = self.upload_to_instagram(video_path, description)
        
        # Upload to TikTok
        print("\n🎵 Uploading to TikTok...")
        results["uploads"]["tiktok"] = self.upload_to_tiktok(video_path, description)
        
        # Upload to Snapchat
        print("\n📱 Uploading to Snapchat...")
        results["uploads"]["snapchat"] = self.upload_to_snapchat(video_path, description)
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Upload Summary:")
        successful = 0
        failed = 0
        
        for platform, result in results["uploads"].items():
            if result.get("success"):
                print(f"✅ {platform}: Success")
                successful += 1
            else:
                print(f"❌ {platform}: Failed - {result.get('error', 'Unknown error')}")
                failed += 1
        
        print(f"\n📈 Results: {successful} successful, {failed} failed")
        
        return results

def upload_video_from_pipeline(video_path: str, script_data: Dict = None) -> Dict:
    """
    Upload a video generated from the pipeline to all social media platforms.
    
    Args:
        video_path: Path to the video file
        script_data: Data from the pipeline (headline, script, etc.)
    
    Returns:
        Dict with upload results
    """
    uploader = SocialMediaUploader()
    
    # Generate title and description from script data
    if script_data:
        title = f"NFL News: {script_data.get('headline', {}).get('title', 'Latest Updates')}"
        description = f"{script_data.get('script', '')}\n\n#NFL #Football #SportsNews #BreakingNews"
        tags = ["NFL", "Football", "Sports", "News", "Breaking"]
    else:
        title = f"NFL News Update - {datetime.now().strftime('%B %d, %Y')}"
        description = "Latest NFL news and updates. Stay tuned for more sports content!"
        tags = ["NFL", "Football", "Sports", "News"]
    
    return uploader.upload_to_all_platforms(video_path, title, description, tags)

def main():
    """CLI interface for social media uploader."""
    
    print("📱 Social Media Uploader")
    print("=" * 30)
    print("1. Upload single video to all platforms")
    print("2. Upload video from pipeline results")
    print("3. Upload to specific platform")
    print("4. Setup API credentials")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    uploader = SocialMediaUploader()
    
    if choice == "1":
        # Upload single video
        video_path = input("Enter video file path: ").strip()
        if not os.path.exists(video_path):
            print("❌ Video file not found")
            return
        
        title = input("Enter video title: ").strip()
        description = input("Enter video description: ").strip()
        tags_input = input("Enter tags (comma-separated): ").strip()
        tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
        
        results = uploader.upload_to_all_platforms(video_path, title, description, tags)
        
    elif choice == "2":
        # Upload from pipeline
        video_path = input("Enter video file path: ").strip()
        if not os.path.exists(video_path):
            print("❌ Video file not found")
            return
        
        # Try to find corresponding script data
        script_data = None
        # You could implement logic here to find the script data from pipeline results
        
        results = upload_video_from_pipeline(video_path, script_data)
        
    elif choice == "3":
        # Upload to specific platform
        print("Select platform:")
        print("1. YouTube")
        print("2. Instagram")
        print("3. TikTok")
        print("4. Snapchat")
        
        platform_choice = input("Select platform (1-4): ").strip()
        
        video_path = input("Enter video file path: ").strip()
        if not os.path.exists(video_path):
            print("❌ Video file not found")
            return
        
        title = input("Enter video title: ").strip()
        description = input("Enter video description: ").strip()
        
        if platform_choice == "1":
            results = uploader.upload_to_youtube(video_path, title, description)
        elif platform_choice == "2":
            results = uploader.upload_to_instagram(video_path, description)
        elif platform_choice == "3":
            results = uploader.upload_to_tiktok(video_path, description)
        elif platform_choice == "4":
            results = uploader.upload_to_snapchat(video_path, description)
        else:
            print("❌ Invalid platform choice")
            return
        
    elif choice == "4":
        # Setup API credentials
        print("\n🔧 API Credentials Setup")
        print("=" * 30)
        print("You'll need to set up API credentials for each platform:")
        print("\n📺 YouTube:")
        print("  1. Go to Google Cloud Console")
        print("  2. Enable YouTube Data API v3")
        print("  3. Create OAuth 2.0 credentials")
        print("  4. Download credentials as 'youtube_credentials.json'")
        
        print("\n📸 Instagram:")
        print("  1. Go to Facebook Developers")
        print("  2. Create Instagram Basic Display app")
        print("  3. Get access token")
        print("  4. Set INSTAGRAM_ACCESS_TOKEN in .env file")
        
        print("\n🎵 TikTok:")
        print("  1. Go to TikTok for Developers")
        print("  2. Create app and get access token")
        print("  3. Set TIKTOK_ACCESS_TOKEN in .env file")
        
        print("\n📱 Snapchat:")
        print("  1. Go to Snapchat for Developers")
        print("  2. Create app and get access token")
        print("  3. Set SNAPCHAT_ACCESS_TOKEN in .env file")
        
        print("\n📝 Add these to your .env file:")
        print("INSTAGRAM_ACCESS_TOKEN=your_token_here")
        print("TIKTOK_ACCESS_TOKEN=your_token_here")
        print("SNAPCHAT_ACCESS_TOKEN=your_token_here")
        
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
