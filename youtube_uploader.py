from typing import Optional, Callable, Tuple
import os
import pickle
from datetime import datetime

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class YouTubeUploader:
    """
    Handles authentication and video uploads to YouTube.
    This class is designed to work with specific token files for multi-account support.
    """
    def __init__(self):
        self.CLIENT_SECRETS_FILE = "client_secret.json"
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
        self._service = None

    def authenticate(self, token_file: str) -> Tuple[bool, str]:
        """
        Authenticates with the YouTube API using a specific token file.

        Args:
            token_file (str): The path to the .pickle file containing the user's credentials.

        Returns:
            Tuple[bool, str]: A tuple containing a success flag and a message.
        """
        try:
            creds = None
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    return (False, f"Token file is invalid or expired and cannot be refreshed: {token_file}")
                
                # Re-save the refreshed token to ensure it's up-to-date
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)

            self._service = build('youtube', 'v3', credentials=creds)
            return (True, "Authentication successful.")
        except Exception as e:
            return (False, f"Authentication error for {token_file}: {e}")

    def upload_video(self,
                     video_file: str,
                     config: 'YouTubeConfig',
                     token_file: str,
                     progress_callback: Optional[Callable[[float], None]] = None
                    ) -> Tuple[bool, str]:
        """
        Uploads a video to YouTube using credentials from a specific token file.

        Args:
            video_file (str): Path to the video file to upload.
            config (YouTubeConfig): A dataclass object with title, description, etc.
            token_file (str): The path to the token file for the target YouTube account.
            progress_callback (Optional[Callable[[float], None]]): A function to call with upload progress (0-100).

        Returns:
            Tuple[bool, str]: A tuple containing a success flag and the resulting video URL or an error message.
        """
        auth_ok, auth_msg = self.authenticate(token_file)
        if not auth_ok:
            return (False, auth_msg)
        
        try:
            body = {
                'snippet': {
                    'title': config.title,
                    'description': config.description,
                    'tags': [tag.strip() for tag in config.tags.split(',') if tag.strip()],
                    'categoryId': '22'  # People & Blogs, can be made configurable later
                },
                'status': {
                    'privacyStatus': config.privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            if config.schedule_datetime:
                try:
                    dt = datetime.strptime(config.schedule_datetime, "%d/%m/%Y %H:%M")
                    body['status']['publishAt'] = dt.isoformat() + ".000Z"
                except ValueError:
                    return (False, "Invalid schedule format. Please use DD/MM/YYYY HH:MM.")

            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)

            request = self._service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.progress() * 100)

            video_id = response.get('id')
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return (True, video_url)
        except Exception as e:
            return (False, f"Upload failed: {str(e)}")