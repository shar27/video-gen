"""
Video Generation Pipeline
- Takes an image + script
- Uses Kling AI to generate video from image
- Converts script to speech using ElevenLabs TTS
- Merges video + audio with FFmpeg
- Outputs YouTube-ready video
"""

import os
import base64
import time
import jwt
import requests
from pathlib import Path
from openai import OpenAI


# ElevenLabs voice options - British/Documentary style voices
ELEVENLABS_VOICES = {
    # Premium documentary voices
    'george': {
        'id': 'JBFqnCBsd6RMkjVDRZzb',
        'name': 'George',
        'description': 'British, warm, raspy - Perfect for nature documentaries'
    },
    'daniel': {
        'id': 'onwK4e9ZLuTAKqWW03F9',
        'name': 'Daniel',
        'description': 'British, authoritative - Great for factual content'
    },
    'bill': {
        'id': 'pqHfZKP75CvOlQylNhV4',
        'name': 'Bill',
        'description': 'Older male, trustworthy - Classic narrator voice'
    },
    'clyde': {
        'id': '2EiwWnXFnvU5JabPnv8n',
        'name': 'Clyde',
        'description': 'War veteran character - Deep, gravelly'
    },
    # Additional voices
    'adam': {
        'id': 'pNInz6obpgDQGcFmaJgB',
        'name': 'Adam',
        'description': 'Deep, narrative - American male'
    },
    'antoni': {
        'id': 'ErXwobaYiN019PkySvjV',
        'name': 'Antoni',
        'description': 'Well-rounded narrator - Young male'
    },
    'rachel': {
        'id': '21m00Tcm4TlvDq8ikWAM',
        'name': 'Rachel',
        'description': 'Calm, young female - American'
    },
    'drew': {
        'id': '29vD33N1CtxCmqQRPOHJ',
        'name': 'Drew',
        'description': 'News reader - Middle-aged male'
    },
}


class VideoGenerationPipeline:
    def __init__(self):
        self.openai = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.kling_access_key = os.environ.get('KLING_ACCESS_KEY')
        self.kling_secret_key = os.environ.get('KLING_SECRET_KEY')
        self.kling_api_base = os.environ.get('KLING_API_BASE', 'https://api.klingai.com')
        self.elevenlabs_api_key = os.environ.get('ELEVEN_LABS_API')
        self.work_dir = Path('video_work')
        self.work_dir.mkdir(exist_ok=True)
        
        if not self.kling_access_key or not self.kling_secret_key:
            raise ValueError("KLING_ACCESS_KEY and KLING_SECRET_KEY environment variables are required")
        
        if not self.elevenlabs_api_key:
            print("⚠️ Warning: ELEVEN_LABS_API not set, falling back to OpenAI TTS")
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Kling AI API authentication"""
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }
        payload = {
            "iss": self.kling_access_key,  # Issuer is the Access Key
            "exp": int(time.time()) + 1800,  # Token expires in 30 minutes
            "nbf": int(time.time()) - 5  # Token valid from 5 seconds ago
        }
        token = jwt.encode(payload, self.kling_secret_key, algorithm="HS256", headers=headers)
        return token
    
    def generate_video_from_image(self, image_path: str, motion_prompt: str, duration: int = 10) -> str:
        """
        Generate video from image using Kling AI
        
        Args:
            image_path: Path to source image or URL
            motion_prompt: Text describing the desired motion/animation
            duration: Video duration in seconds (5 or 10)
            
        Returns:
            Path to downloaded video file
        """
        print(f"🎬 Generating video from image with Kling AI...")
        print(f"   Motion prompt: {motion_prompt}")
        print(f"   Duration: {duration}s")
        
        # Generate JWT token
        token = self._generate_jwt_token()
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Prepare image - either URL or raw base64 (no data URI prefix)
        if image_path.startswith('http'):
            image_value = image_path
        else:
            # For Kling AI, send raw base64 without data URI prefix
            with open(image_path, 'rb') as f:
                image_data = f.read()
            image_value = base64.b64encode(image_data).decode('utf-8')
        
        try:
            payload = {
                "model_name": "kling-v1-6",  # Using Kling v1.6 model
                "image": image_value,
                "prompt": motion_prompt,
                "mode": "pro",  # Use professional mode for better quality
                "duration": str(duration),  # Duration as string
                "aspect_ratio": "16:9"  # 16:9 for YouTube
            }
            
            # Submit the task
            response = requests.post(
                f"{self.kling_api_base}/v1/videos/image2video",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Kling API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if result.get('code') != 0:
                raise Exception(f"Kling API error: {result.get('message', 'Unknown error')}")
            
            task_id = result['data']['task_id']
            print(f"   Task created: {task_id}")
            print(f"   Waiting for generation (this may take 2-5 minutes)...")
            
            # Poll for completion
            video_url = None
            max_attempts = 120  # 10 minutes max (5 second intervals)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)
                attempt += 1
                
                # Check task status
                status_response = requests.get(
                    f"{self.kling_api_base}/v1/videos/image2video/{task_id}",
                    headers=headers,
                    timeout=30
                )
                
                if status_response.status_code != 200:
                    print(f"   Warning: Status check failed: {status_response.status_code}")
                    continue
                
                status_result = status_response.json()
                
                if status_result.get('code') != 0:
                    continue
                
                task_status = status_result['data']['task_status']
                
                if task_status == 'succeed':
                    videos = status_result['data']['task_result']['videos']
                    if videos and len(videos) > 0:
                        video_url = videos[0]['url']
                        print(f"   ✅ Video generated successfully!")
                        break
                elif task_status == 'failed':
                    error_msg = status_result['data'].get('task_status_msg', 'Unknown error')
                    raise Exception(f"Kling generation failed: {error_msg}")
                else:
                    # Still processing
                    if attempt % 6 == 0:  # Print status every 30 seconds
                        print(f"   Status: {task_status}... ({attempt * 5}s elapsed)")
            
            if not video_url:
                raise Exception("Video generation timed out")
            
            # Download the video
            video_filename = self.work_dir / f"kling_video_{task_id}.mp4"
            
            print(f"   Downloading video...")
            video_response = requests.get(video_url, timeout=120)
            
            if video_response.status_code != 200:
                raise Exception(f"Failed to download video: {video_response.status_code}")
            
            with open(video_filename, 'wb') as f:
                f.write(video_response.content)
            
            print(f"   ✅ Video saved: {video_filename}")
            return str(video_filename)
            
        except Exception as e:
            print(f"   ❌ Error generating video: {e}")
            raise
    
    def convert_script_to_speech(self, script: str, output_path: str, voice: str = 'george') -> str:
        """
        Convert script to speech using ElevenLabs TTS (falls back to OpenAI if unavailable)
        
        Args:
            script: The commentary script text
            output_path: Where to save the audio file
            voice: ElevenLabs voice name (george, daniel, bill, clyde, adam, etc.)
            
        Returns:
            Path to audio file
        """
        output_path = Path(output_path)
        
        # Use ElevenLabs if API key is available
        if self.elevenlabs_api_key:
            return self._convert_with_elevenlabs(script, output_path, voice)
        else:
            print("⚠️ ElevenLabs not configured, using OpenAI TTS...")
            return self._convert_with_openai(script, output_path, voice)
    
    def _convert_with_elevenlabs(self, script: str, output_path: Path, voice: str) -> str:
        """Convert script to speech using ElevenLabs API"""
        import subprocess
        
        # Get voice ID from our mapping, or use as-is if it looks like an ID
        voice_lower = voice.lower()
        if voice_lower in ELEVENLABS_VOICES:
            voice_id = ELEVENLABS_VOICES[voice_lower]['id']
            voice_name = ELEVENLABS_VOICES[voice_lower]['name']
        else:
            # Assume it's a voice ID directly
            voice_id = voice
            voice_name = voice
        
        print(f"🎙️ Converting script to speech with ElevenLabs (voice: {voice_name})...")
        
        # ElevenLabs has a 5000 character limit per request
        MAX_CHARS = 4500
        
        if len(script) <= MAX_CHARS:
            # Single request
            audio_data = self._elevenlabs_tts_request(script, voice_id)
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            print(f"   ✅ Audio saved: {output_path}")
            return str(output_path)
        
        # Split long scripts into chunks
        print(f"   Script is {len(script)} chars, splitting into chunks...")
        chunks = self._split_script_into_chunks(script, MAX_CHARS)
        print(f"   Split into {len(chunks)} chunks")
        
        temp_files = []
        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            temp_path = output_path.parent / f"{output_path.stem}_chunk_{i}.mp3"
            
            audio_data = self._elevenlabs_tts_request(chunk, voice_id)
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            temp_files.append(temp_path)
        
        # Concatenate audio files using ffmpeg
        print(f"   Concatenating {len(temp_files)} audio chunks...")
        
        list_file = output_path.parent / f"{output_path.stem}_filelist.txt"
        with open(list_file, 'w') as f:
            for temp_file in temp_files:
                f.write(f"file '{temp_file.name}'\n")
        
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', str(list_file),
            '-c', 'copy',
            '-y', str(output_path)
        ], check=True, capture_output=True)
        
        # Cleanup temp files
        for temp_file in temp_files:
            temp_file.unlink()
        list_file.unlink()
        
        print(f"   ✅ Audio saved: {output_path}")
        return str(output_path)
    
    def _elevenlabs_tts_request(self, text: str, voice_id: str) -> bytes:
        """Make a single TTS request to ElevenLabs API"""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True
            }
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=120)
        
        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")
        
        return response.content
    
    def _convert_with_openai(self, script: str, output_path: Path, voice: str) -> str:
        """Fallback: Convert script to speech using OpenAI TTS"""
        import subprocess
        
        # Map to OpenAI voices if using ElevenLabs voice names
        openai_voice = 'onyx'  # Default
        if voice.lower() in ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']:
            openai_voice = voice.lower()
        
        print(f"🎙️ Converting script to speech with OpenAI (voice: {openai_voice})...")
        
        MAX_CHARS = 4000
        
        if len(script) <= MAX_CHARS:
            response = self.openai.audio.speech.create(
                model="tts-1-hd",
                voice=openai_voice,
                input=script,
                speed=1.0
            )
            response.stream_to_file(str(output_path))
            print(f"   ✅ Audio saved: {output_path}")
            return str(output_path)
        
        # Split and process chunks
        print(f"   Script is {len(script)} chars, splitting into chunks...")
        chunks = self._split_script_into_chunks(script, MAX_CHARS)
        print(f"   Split into {len(chunks)} chunks")
        
        temp_files = []
        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            temp_path = output_path.parent / f"{output_path.stem}_chunk_{i}.mp3"
            
            response = self.openai.audio.speech.create(
                model="tts-1-hd",
                voice=openai_voice,
                input=chunk,
                speed=1.0
            )
            response.stream_to_file(str(temp_path))
            temp_files.append(temp_path)
        
        # Concatenate
        list_file = output_path.parent / f"{output_path.stem}_filelist.txt"
        with open(list_file, 'w') as f:
            for temp_file in temp_files:
                f.write(f"file '{temp_file.name}'\n")
        
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', str(list_file),
            '-c', 'copy',
            '-y', str(output_path)
        ], check=True, capture_output=True)
        
        for temp_file in temp_files:
            temp_file.unlink()
        list_file.unlink()
        
        print(f"   ✅ Audio saved: {output_path}")
        return str(output_path)
    
    def _split_script_into_chunks(self, script: str, max_chars: int) -> list:
        """Split script into chunks respecting sentence boundaries"""
        chunks = []
        current_chunk = ""
        
        paragraphs = script.split('\n\n')
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk += para + '\n\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                if len(para) > max_chars:
                    # Split by sentences
                    sentences = para.replace('. ', '.|').split('|')
                    current_chunk = ""
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 1 <= max_chars:
                            current_chunk += sentence + ' '
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + ' '
                else:
                    current_chunk = para + '\n\n'
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def merge_video_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """
        Merge video with audio commentary using FFmpeg
        
        Args:
            video_path: Path to source video
            audio_path: Path to audio commentary
            output_path: Where to save final video
            
        Returns:
            Path to final video
        """
        import subprocess
        
        print(f"🎬 Merging video and audio...")
        
        # Get durations
        video_duration = self._get_media_duration(video_path)
        audio_duration = self._get_media_duration(audio_path)
        
        print(f"   Video duration: {video_duration:.2f}s")
        print(f"   Audio duration: {audio_duration:.2f}s")
        
        # Choose strategy based on durations
        if abs(video_duration - audio_duration) < 0.5:
            # Durations are similar, simple merge
            print(f"   Strategy: Simple merge")
            cmd = [
                'ffmpeg', '-i', video_path, '-i', audio_path,
                '-c:v', 'copy', '-c:a', 'aac',
                '-map', '0:v:0', '-map', '1:a:0',
                '-shortest',
                '-y', output_path
            ]
        elif audio_duration > video_duration:
            # Audio is longer, loop video
            print(f"   Strategy: Loop video to match audio length")
            cmd = [
                'ffmpeg',
                '-stream_loop', '-1', '-i', video_path,
                '-i', audio_path,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-map', '0:v:0', '-map', '1:a:0',
                '-shortest',
                '-y', output_path
            ]
        else:
            # Video is longer, trim to audio
            print(f"   Strategy: Trim video to audio length")
            cmd = [
                'ffmpeg', '-i', video_path, '-i', audio_path,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-map', '0:v:0', '-map', '1:a:0',
                '-shortest',
                '-y',
                output_path
            ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"   ✅ Final video saved: {output_path}")
        return output_path
    
    def _get_media_duration(self, file_path: str) -> float:
        """Get duration of media file in seconds"""
        import subprocess
        import json
        
        result = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            file_path
        ], capture_output=True, text=True)
        
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    
    def generate_youtube_metadata(self, script: str, topic: str = None) -> dict:
        """
        Generate YouTube title, description and tags using AI
        
        Args:
            script: The commentary script
            topic: Optional topic/theme
            
        Returns:
            Dictionary with title, description, tags
        """
        print(f"📝 Generating YouTube metadata...")
        
        prompt = f"""Based on this video commentary script, generate YouTube metadata.

Script:
{script[:2000]}

Generate:
1. An engaging YouTube title (max 100 chars, include emoji)
2. A compelling description (include call to action, hashtags)
3. 10-15 relevant tags for SEO

Format your response as:
TITLE: [title here]
DESCRIPTION: [description here]
TAGS: tag1, tag2, tag3, ...
"""
        
        response = self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        # Parse response
        metadata = {'title': '', 'description': '', 'tags': []}
        
        for line in content.split('\n'):
            if line.startswith('TITLE:'):
                metadata['title'] = line.replace('TITLE:', '').strip()
            elif line.startswith('DESCRIPTION:'):
                metadata['description'] = line.replace('DESCRIPTION:', '').strip()
            elif line.startswith('TAGS:'):
                tags_str = line.replace('TAGS:', '').strip()
                metadata['tags'] = [t.strip() for t in tags_str.split(',')]
        
        print(f"   ✅ Metadata generated")
        return metadata
    
    def process(self, image_path: str, script: str, motion_prompt: str = None, 
                voice: str = 'onyx', duration: int = 10) -> dict:
        """
        Full pipeline: image + script -> YouTube-ready video
        
        Args:
            image_path: Path to source image (local or URL)
            script: Commentary script to narrate
            motion_prompt: Prompt describing video motion (optional, generated if not provided)
            voice: TTS voice to use
            duration: Kling video duration (5 or 10 seconds)
            
        Returns:
            Dictionary with file paths and metadata
        """
        print("\n" + "="*70)
        print("🎬 STARTING VIDEO GENERATION PIPELINE (Kling AI)")
        print("="*70 + "\n")
        
        # Create job directory
        import uuid
        job_id = str(uuid.uuid4())[:8]
        job_dir = self.work_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        try:
            # Step 1: Generate motion prompt if not provided
            if not motion_prompt:
                print("Step 1: Generating motion prompt from script...")
                motion_prompt = self._generate_motion_prompt(script)
            else:
                print("Step 1: Using provided motion prompt")
            print(f"   Motion: {motion_prompt}\n")
            
            # Step 2: Generate video from image
            print("-"*70)
            print("Step 2: GENERATING VIDEO FROM IMAGE (Kling AI)")
            print("-"*70)
            video_path = self.generate_video_from_image(
                image_path, 
                motion_prompt, 
                duration=duration
            )
            print()
            
            # Step 3: Convert script to speech
            print("-"*70)
            print("Step 3: CONVERTING SCRIPT TO SPEECH")
            print("-"*70)
            audio_path = str(job_dir / "commentary.mp3")
            self.convert_script_to_speech(script, audio_path, voice=voice)
            print()
            
            # Step 4: Merge video and audio
            print("-"*70)
            print("Step 4: MERGING VIDEO AND AUDIO")
            print("-"*70)
            final_video = str(job_dir / "final_video.mp4")
            self.merge_video_audio(video_path, audio_path, final_video)
            print()
            
            # Step 5: Generate YouTube metadata
            print("-"*70)
            print("Step 5: GENERATING YOUTUBE METADATA")
            print("-"*70)
            metadata = self.generate_youtube_metadata(script)
            print()
            
            # Save script and metadata
            with open(job_dir / "script.txt", 'w') as f:
                f.write(script)
            
            import json
            with open(job_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print("="*70)
            print("✅ PIPELINE COMPLETE!")
            print("="*70)
            
            return {
                'job_id': job_id,
                'video_path': final_video,
                'audio_path': audio_path,
                'script_path': str(job_dir / "script.txt"),
                'metadata': metadata,
                'files': {
                    'video': final_video,
                    'audio': audio_path,
                    'script': str(job_dir / "script.txt"),
                    'metadata': str(job_dir / "metadata.json")
                }
            }
            
        except Exception as e:
            print(f"\n❌ PIPELINE FAILED: {e}")
            raise
    
    def _generate_motion_prompt(self, script: str) -> str:
        """Generate a motion prompt based on the script content"""
        prompt = f"""Based on this commentary script, generate a short motion/animation prompt for AI video generation.

Script:
{script[:1000]}

Generate a concise prompt (max 50 words) describing subtle, professional motion that would complement this narration. Focus on:
- Gentle camera movements (slow pan, slight zoom)
- Ambient motion (particles, light shifts, subtle animations)
- Professional documentary style

Return ONLY the motion prompt, nothing else."""

        response = self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()


# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    pipeline = VideoGenerationPipeline()
    
    # Example usage
    if len(sys.argv) >= 3:
        image_path = sys.argv[1]
        script = sys.argv[2]
        motion_prompt = sys.argv[3] if len(sys.argv) > 3 else None
        
        result = pipeline.process(
            image_path=image_path,
            script=script,
            motion_prompt=motion_prompt
        )
        
        print(f"\nOutput files:")
        for key, path in result['files'].items():
            print(f"  {key}: {path}")
    else:
        print("Usage: python video_generation.py <image_path> <script> [motion_prompt]")