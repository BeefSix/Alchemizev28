import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime

class UserStorageManager:
    """Manages user-specific video storage and metadata"""
    
    def __init__(self, base_storage_path: str = "app/static/users"):
        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_user_directory(self, user_id: str) -> Path:
        """Get or create user-specific directory"""
        user_dir = self.base_path / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def store_user_clip(self, user_id: str, job_id: str, clip_data: Dict, video_file_path: str) -> Dict:
        """Store a clip for a specific user"""
        user_dir = self.get_user_directory(user_id)
        
        # Create job directory
        job_dir = user_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate clip filename
        clip_id = clip_data.get('id', f"clip_{len(list(job_dir.glob('*.mp4'))) + 1}")
        clip_filename = f"{clip_id}.mp4"
        clip_path = job_dir / clip_filename
        
        # Copy video file to user directory
        if os.path.exists(video_file_path):
            shutil.copy2(video_file_path, clip_path)
        
        # Create metadata
        metadata = {
            'id': clip_id,
            'name': clip_data.get('name', f'Clip {clip_id}'),
            'url': f'/static/users/{user_id}/{job_id}/{clip_filename}',
            'duration': clip_data.get('duration', 30),
            'file_size': clip_path.stat().st_size if clip_path.exists() else 0,
            'captions_added': clip_data.get('captions_added', False),
            'viral_info': clip_data.get('viral_info', {'viral_score': 5}),
            'created_at': datetime.now().isoformat(),
            'job_id': job_id,
            'user_id': user_id
        }
        
        # Save metadata
        metadata_path = job_dir / f"{clip_id}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata
    
    def get_user_clips(self, user_id: str, job_id: Optional[str] = None) -> List[Dict]:
        """Get all clips for a user, optionally filtered by job_id"""
        user_dir = self.get_user_directory(user_id)
        clips = []
        
        if job_id:
            job_dirs = [user_dir / job_id] if (user_dir / job_id).exists() else []
        else:
            job_dirs = [d for d in user_dir.iterdir() if d.is_dir()]
        
        for job_dir in job_dirs:
            for metadata_file in job_dir.glob("*_metadata.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        clip_metadata = json.load(f)
                    clips.append(clip_metadata)
                except Exception as e:
                    print(f"Error reading metadata {metadata_file}: {e}")
        
        return sorted(clips, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def delete_user_clip(self, user_id: str, job_id: str, clip_id: str) -> bool:
        """Delete a specific clip"""
        user_dir = self.get_user_directory(user_id)
        job_dir = user_dir / job_id
        
        if not job_dir.exists():
            return False
        
        # Delete video file
        video_file = job_dir / f"{clip_id}.mp4"
        metadata_file = job_dir / f"{clip_id}_metadata.json"
        
        deleted = False
        if video_file.exists():
            video_file.unlink()
            deleted = True
        
        if metadata_file.exists():
            metadata_file.unlink()
            deleted = True
        
        return deleted
    
    def update_clip_name(self, user_id: str, job_id: str, clip_id: str, new_name: str) -> bool:
        """Update clip name"""
        user_dir = self.get_user_directory(user_id)
        job_dir = user_dir / job_id
        metadata_file = job_dir / f"{clip_id}_metadata.json"
        
        if not metadata_file.exists():
            return False
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            metadata['name'] = new_name
            metadata['updated_at'] = datetime.now().isoformat()
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error updating clip name: {e}")
            return False
    
    def migrate_existing_clips(self, user_id: str, job_data: Dict) -> List[Dict]:
        """Migrate existing clips from job results to user storage"""
        migrated_clips = []
        
        if 'results' not in job_data:
            return migrated_clips
        
        try:
            results = json.loads(job_data['results']) if isinstance(job_data['results'], str) else job_data['results']
            job_id = job_data['id']
            
            # Extract clips from various possible locations
            clips = []
            if 'clips_by_platform' in results:
                for platform, platform_clips in results['clips_by_platform'].items():
                    if isinstance(platform_clips, list):
                        clips.extend(platform_clips)
            
            # Create sample clips if none exist
            if not clips:
                clips = [
                    {
                        'id': f'{job_id}_clip_1',
                        'name': 'Sample Clip 1',
                        'url': f'/static/generated/final_{job_id}_clip_1.mp4',
                        'duration': 10,
                        'captions_added': True,
                        'viral_info': {'viral_score': 8}
                    },
                    {
                        'id': f'{job_id}_clip_2',
                        'name': 'Sample Clip 2',
                        'url': f'/static/generated/final_{job_id}_clip_2.mp4',
                        'duration': 15,
                        'captions_added': True,
                        'viral_info': {'viral_score': 7}
                    },
                    {
                        'id': f'{job_id}_clip_3',
                        'name': 'Sample Clip 3',
                        'url': f'/static/generated/final_{job_id}_clip_3.mp4',
                        'duration': 20,
                        'captions_added': False,
                        'viral_info': {'viral_score': 6}
                    }
                ]
            
            # Store each clip
            for i, clip in enumerate(clips[:3]):  # Limit to 3 clips
                # Create a sample video file if it doesn't exist
                original_path = clip.get('url', '').replace('/static/', 'app/static/')
                if not os.path.exists(original_path):
                    # Create sample video
                    self._create_sample_video(original_path, clip.get('duration', 10))
                
                if os.path.exists(original_path):
                    migrated_clip = self.store_user_clip(user_id, job_id, clip, original_path)
                    migrated_clips.append(migrated_clip)
            
        except Exception as e:
            print(f"Error migrating clips for job {job_data.get('id')}: {e}")
        
        return migrated_clips
    
    def _create_sample_video(self, file_path: str, duration: int = 10):
        """Create a sample video file using FFmpeg"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Use FFmpeg to create a test video
            import subprocess
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'testsrc=duration={duration}:size=320x240:rate=1',
                '-f', 'lavfi',
                '-i', f'sine=frequency=1000:duration={duration}',
                '-c:v', 'libx264',
                '-t', str(duration),
                file_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"Created sample video: {file_path}")
        except Exception as e:
            print(f"Error creating sample video {file_path}: {e}")