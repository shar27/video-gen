#!/usr/bin/env python3
import os
import re
from pathlib import Path
from datetime import datetime
import psycopg
from dotenv import load_dotenv
import youtube_transcript_api
from openai import OpenAI
import yt_dlp

load_dotenv()

class VideoCommentaryPipeline:
    def __init__(self):
        self.openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.db_url = os.getenv('DATABASE_URL')
        self.work_dir = Path('video_work')
        self.output_dir = Path('video_output')
        
        self.work_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
    def extract_video_id(self, url):
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([^&\n?#]+)',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError('Invalid YouTube URL format')
    
    def download_transcript(self, video_url):
        try:
            video_id = self.extract_video_id(video_url)
            print(f"📝 Fetching transcript for video ID: {video_id}")
            
            # Create instance and use list method
            api = youtube_transcript_api.YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            # Get first available transcript
            for transcript in transcript_list:
                fetched = transcript.fetch()
                # The fetched object has a .snippets attribute which is a list
                transcript_data = fetched.snippets
                break
            
            full_text = ' '.join([entry.text for entry in transcript_data])
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            return {
                'video_id': video_id,
                'transcript': full_text,
                'timestamped': [{'text': s.text, 'start': s.start, 'duration': s.duration} for s in transcript_data]
            }
        except Exception as e:
            print(f"❌ Error downloading transcript: {e}")
            raise
    
    def generate_commentary_script(self, transcript, context=None):
        try:
            print("🤖 Generating commentary script with AI...")
            
            context = context or {}
            incident_info = ""
            
            if context.get('incident'):
                inc = context['incident']
                incident_info = f"""
Incident Context:
- Location: {inc.get('location', 'UK')}
- Type: {inc.get('incident_type', 'Unknown')}
- Severity: {inc.get('severity', 'Unknown')}
- Description: {inc.get('description', '')}
"""
            
            prompt = f"""You are creating a critical commentary script for a video about Islamophobia in the UK.

Original Video Transcript:
{transcript}

{incident_info}

Context:
- Platform: Islamophobia UK (islamophobiauk.co.uk)
- Purpose: Educational commentary and criticism (Fair Use)
- Audience: General public, educators, activists

Create a commentary script that:
1. Provides critical analysis and context
2. Educates about Islamophobia and its impacts
3. Maintains a professional, informative tone
4. Is suitable for voice narration (natural speaking style)
5. Is concise and matches the video length - no longer than needed
6. NO headers or section titles - just natural flowing speech
7. Offers constructive perspectives

Format as natural speech with clear paragraphs for pacing.
DO NOT quote the original transcript directly - analyze and contextualize it.
IMPORTANT: Keep it natural and conversational. No headers like [INTRODUCTION], no sections - just flowing speech ready for voice narration. Match the length to the original video."""

            system_prompt = 'You are an expert analyst on Islamophobia and social justice. Create insightful, educational commentary scripts.'
            
            # Try OpenAI GPT-4o-mini first
            try:
                print("  Trying OpenAI GPT-4o-mini...")
                response = self.openai.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                script = response.choices[0].message.content
                print(f"  ✅ Generated script with OpenAI: {len(script.split())} words")
                return script
            except Exception as e:
                print(f"  ⚠️ OpenAI failed: {e}")
            
            # Try Claude (Anthropic) as fallback
            try:
                print("  Trying Claude (Anthropic)...")
                import anthropic
                
                claude_key = os.getenv('ANTHROPIC_API_KEY')
                if not claude_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in .env")
                
                client = anthropic.Anthropic(api_key=claude_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": f"{system_prompt}\n\n{prompt}"}
                    ]
                )
                script = response.content[0].text
                print(f"  ✅ Generated script with Claude: {len(script.split())} words")
                return script
            except Exception as e:
                print(f"  ⚠️ Claude failed: {e}")
            
            # Try Groq as final fallback
            try:
                print("  Trying Groq...")
                from groq import Groq
                
                groq_key = os.getenv('GROQ_API_KEY')
                if not groq_key:
                    raise ValueError("GROQ_API_KEY not found in .env")
                
                client = Groq(api_key=groq_key)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                script = response.choices[0].message.content
                print(f"  ✅ Generated script with Groq: {len(script.split())} words")
                return script
            except Exception as e:
                print(f"  ⚠️ Groq failed: {e}")
            
            # All providers failed
            raise Exception("All AI providers failed. Please add API keys to .env file.")
            
        except Exception as e:
            print(f"❌ Error generating script: {e}")
            raise
    
    def convert_to_speech(self, script, output_path, voice='onyx'):
        try:
            print(f"🎙️ Converting script to speech (voice: {voice})...")
            
            response = self.openai.audio.speech.create(
                model="tts-1-hd",
                voice=voice,
                input=script,
                speed=1.0
            )
            
            response.stream_to_file(str(output_path))
            print(f"✅ Audio saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error converting to speech: {e}")
            raise
    
    def download_video(self, video_id, output_path):
        try:
            print(f"📥 Downloading video {video_id}...")
            
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': str(output_path),
                'quiet': False,
                'no_warnings': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            print(f"✅ Video downloaded: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error downloading video: {e}")
            raise
    
    def merge_video_audio(self, video_path, audio_path, output_path, logo_path=None, cover_path=None):
        """Automatically merge video + audio using FFmpeg with background and overlays"""
        try:
            import subprocess
            
            print(f"🎬 Merging video and audio with FFmpeg...")
            
            # Check if cover background exists
            if cover_path and Path(cover_path).exists():
                print(f"   Using background: {cover_path}")
                has_cover = True
            else:
                print(f"   No cover.png found, video will be full screen")
                has_cover = False
            
            # Check if logo exists
            if logo_path and Path(logo_path).exists():
                print(f"   Adding logo overlays")
                has_logo = True
            else:
                has_logo = False
            
            if has_cover:
                # Split screen layout: website on left, video on right
                filter_complex = (
                    # Audio mixing
                    '[0:a]volume=0.2[original];'
                    '[1:a]volume=1.0[commentary];'
                    '[original][commentary]amix=inputs=2:duration=longest[aout];'
                    # Create split screen: background image on left, video on right
                    # Scale cover to fit left half (540x1920)
                    '[2:v]scale=540:1920:force_original_aspect_ratio=increase,crop=540:1920[left];'
                    # Scale video to fit right half (540x1920)
                    '[0:v]scale=540:1920:force_original_aspect_ratio=increase,crop=540:1920[right];'
                    # Combine side by side
                    '[left][right]hstack=inputs=2[combined];'
                )
                
                # Add logos if available (on the combined output)
                if has_logo:
                    filter_complex += (
                        f'[3:v]scale=100:100[logo];'
                        '[combined][logo]overlay=20:20[v1];'
                        '[v1][logo]overlay=W-w-20:20[v2];'
                        '[v2][logo]overlay=20:H-h-20[v3];'
                        '[v3][logo]overlay=W-w-20:H-h-20[v4];[v4]'
                    )
                else:
                    filter_complex += '[combined]'
                
                # Add text watermarks at bottom center
                filter_complex += (
                    'drawtext='
                    'text=@IslamophobiaUK:'
                    'fontsize=40:'
                    'fontcolor=white:'
                    'x=(w-tw)/2:y=h-th-70:'
                    'box=1:'
                    'boxcolor=black@0.7:'
                    'boxborderw=8,'
                    'drawtext='
                    'text=islamophobiauk.co.uk:'
                    'fontsize=28:'
                    'fontcolor=white:'
                    'x=(w-tw)/2:y=h-th-25:'
                    'box=1:'
                    'boxcolor=black@0.7:'
                    'boxborderw=8[vout]'
                )
                
                # Build command
                cmd = [
                    'ffmpeg',
                    '-i', str(video_path),
                    '-i', str(audio_path),
                    '-loop', '1', '-i', str(cover_path),
                ]
                
                if has_logo:
                    cmd.extend(['-i', str(logo_path)])
                
                cmd.extend([
                    '-filter_complex', filter_complex,
                    '-map', '[vout]',
                    '-map', '[aout]',
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest',
                    '-y',
                    str(output_path)
                ])
            else:
                # No cover - fullscreen video with overlays
                if has_logo:
                    filter_complex = (
                        '[0:a]volume=0.2[original];'
                        '[1:a]volume=1.0[commentary];'
                        '[original][commentary]amix=inputs=2:duration=longest[aout];'
                        f'[2:v]scale=150:150[logo];'
                        '[0:v][logo]overlay=20:20[v1];'
                        '[v1][logo]overlay=W-w-20:20[v2];'
                        '[v2][logo]overlay=20:H-h-20[v3];'
                        '[v3][logo]overlay=W-w-20:H-h-20[v4];'
                        '[v4]'
                        'drawtext='
                        'text=@IslamophobiaUK:'
                        'fontsize=48:'
                        'fontcolor=white:'
                        'x=(w-tw)/2:y=h-th-80:'
                        'box=1:'
                        'boxcolor=black@0.7:'
                        'boxborderw=10,'
                        'drawtext='
                        'text=islamophobiauk.co.uk:'
                        'fontsize=32:'
                        'fontcolor=white:'
                        'x=(w-tw)/2:y=h-th-30:'
                        'box=1:'
                        'boxcolor=black@0.7:'
                        'boxborderw=10[vout]'
                    )
                    
                    cmd = [
                        'ffmpeg',
                        '-i', str(video_path),
                        '-i', str(audio_path),
                        '-i', str(logo_path),
                        '-filter_complex', filter_complex,
                        '-map', '[vout]',
                        '-map', '[aout]',
                        '-c:v', 'libx264',
                        '-preset', 'fast',
                        '-crf', '23',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-shortest',
                        '-y',
                        str(output_path)
                    ]
                else:
                    filter_complex = (
                        '[0:a]volume=0.2[original];'
                        '[1:a]volume=1.0[commentary];'
                        '[original][commentary]amix=inputs=2:duration=longest[aout];'
                        '[0:v]'
                        'drawtext='
                        'text=@IslamophobiaUK:'
                        'fontsize=48:'
                        'fontcolor=white:'
                        'x=w-tw-30:y=h-th-80:'
                        'box=1:'
                        'boxcolor=black@0.7:'
                        'boxborderw=10,'
                        'drawtext='
                        'text=islamophobiauk.co.uk:'
                        'fontsize=32:'
                        'fontcolor=white:'
                        'x=w-tw-30:y=h-th-30:'
                        'box=1:'
                        'boxcolor=black@0.7:'
                        'boxborderw=10[vout]'
                    )
                    
                    cmd = [
                        'ffmpeg',
                        '-i', str(video_path),
                        '-i', str(audio_path),
                        '-filter_complex', filter_complex,
                        '-map', '[vout]',
                        '-map', '[aout]',
                        '-c:v', 'libx264',
                        '-preset', 'fast',
                        '-crf', '23',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-shortest',
                        '-y',
                        str(output_path)
                    ]
            
            subprocess.run(cmd, check=True, capture_output=False)
            print(f"✅ Final video created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg merge failed")
            return False
        except Exception as e:
            print(f"❌ Merge error: {e}")
            return False
    
    def get_incident_from_db(self, incident_id):
        try:
            with psycopg.connect(self.db_url) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT * FROM incidents 
                        WHERE id = %s AND is_approved = 'approved'
                    """, (incident_id,))
                    
                    columns = [desc[0] for desc in cursor.description]
                    row = cursor.fetchone()
                    
                    if row:
                        return dict(zip(columns, row))
                    return None
            
        except Exception as e:
            print(f"❌ Error fetching incident: {e}")
            return None
    
    def get_youtube_url_from_incident(self, incident):
        # Check source_url field
        if incident.get('source_url'):
            url = incident['source_url']
            if 'youtube.com' in url or 'youtu.be' in url:
                return url
        
        # Check media_files array
        media_files = incident.get('media_files', [])
        if isinstance(media_files, list):
            for item in media_files:
                if isinstance(item, str):
                    # If it's a full URL
                    if 'youtube.com' in item or 'youtu.be' in item:
                        return item
                    # If it's just a video ID (11 characters, alphanumeric with _ and -)
                    elif len(item) == 11 and item.replace('_', '').replace('-', '').isalnum():
                        return f'https://www.youtube.com/watch?v={item}'
        
        return None
    
    def create_obs_project_file(self, video_id, video_path, audio_path, output_dir):
        instructions = f"""
╔══════════════════════════════════════════════════════════════╗
║          OBS STUDIO RECORDING INSTRUCTIONS                    ║
╚══════════════════════════════════════════════════════════════╝

Video ID: {video_id}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

FILES PREPARED:
├── Original Video: {video_path.name}
├── Commentary Audio: {audio_path.name}
└── Script: {video_id}_script.txt

OBS SETUP STEPS:
════════════════════════════════════════════════════════════════

1. OPEN OBS STUDIO

2. CREATE NEW SCENE: "{video_id}_commentary"

3. ADD VIDEO SOURCE:
   - Click "+" in Sources
   - Select "Media Source"
   - Name: "Original Video"
   - Browse to: {video_path.absolute()}
   - Uncheck "Restart playback when source becomes active"
   - Check "Close file when inactive"

4. ADD COMMENTARY AUDIO:
   - Click "+" in Sources
   - Select "Media Source"
   - Name: "Commentary Audio"
   - Browse to: {audio_path.absolute()}
   - Uncheck "Restart playback when source becomes active"

5. ADJUST AUDIO LEVELS:
   - In Audio Mixer:
     • Original Video: -20dB to -25dB (lower the original)
     • Commentary Audio: 0dB (full volume)

6. ADD TEXT OVERLAY (Optional):
   - Click "+" in Sources
   - Select "Text (GDI+)"
   - Add: "Commentary by Islamophobia UK"
   - Position bottom right

7. START RECORDING:
   - Click "Start Recording"
   - Play both sources simultaneously
   - Monitor audio levels
   - Stop when complete

8. SAVE OUTPUT:
   - File will be in: {output_dir.absolute()}
   - Rename to: {video_id}_final_commentary.mp4

════════════════════════════════════════════════════════════════

ALTERNATIVE: CAPCUT METHOD
════════════════════════════════════════════════════════════════

1. Open CapCut
2. Import both files:
   - {video_path.name}
   - {audio_path.name}

3. Drag video to timeline
4. Drag commentary audio to audio track
5. Adjust original video audio to 20%
6. Keep commentary audio at 100%
7. Add text: "Commentary by Islamophobia UK"
8. Export as MP4

════════════════════════════════════════════════════════════════
"""
        
        instructions_path = output_dir / f"{video_id}_OBS_INSTRUCTIONS.txt"
        instructions_path.write_text(instructions, encoding='utf-8')
        print(f"📋 Instructions saved: {instructions_path}")
        
        return instructions_path
    
    def process_video(self, youtube_url=None, incident_id=None, auto_download=True):
        try:
            print("\n" + "="*70)
            print("🎬 STARTING VIDEO COMMENTARY PIPELINE")
            print("="*70 + "\n")
            
            incident_data = None
            if incident_id:
                print(f"📂 Fetching incident: {incident_id}")
                incident_data = self.get_incident_from_db(incident_id)
                if incident_data:
                    print(f"✅ Incident loaded: {incident_data['title']}")
                    youtube_url = self.get_youtube_url_from_incident(incident_data) or youtube_url
                    if not youtube_url:
                        raise ValueError(f"No YouTube URL found for incident {incident_id}")
            
            if not youtube_url:
                raise ValueError("Must provide either youtube_url or incident_id")
            
            # Extract video ID first
            video_id = self.extract_video_id(youtube_url)
            
            print("\n" + "-"*70)
            print("STEP 1: DOWNLOADING TRANSCRIPT")
            print("-"*70)
            
            # Create working directory for this video
            video_work_dir = self.work_dir / video_id
            video_work_dir.mkdir(exist_ok=True)
            
            transcript_path = video_work_dir / f"{video_id}_transcript.txt"
            
            # Check if transcript already exists
            if transcript_path.exists():
                print(f"✅ Using cached transcript: {transcript_path}")
                transcript_text = transcript_path.read_text(encoding='utf-8')
                transcript_data = {
                    'video_id': video_id,
                    'transcript': transcript_text,
                    'timestamped': []
                }
            else:
                transcript_data = self.download_transcript(youtube_url)
                transcript_path.write_text(transcript_data['transcript'], encoding='utf-8')
                print(f"💾 Transcript saved: {transcript_path}")
            
            print("\n" + "-"*70)
            print("STEP 2: GENERATING COMMENTARY SCRIPT")
            print("-"*70)
            
            script_path = video_work_dir / f"{video_id}_script.txt"
            
            # Check if script already exists
            if script_path.exists():
                print(f"✅ Using cached script: {script_path}")
                script = script_path.read_text(encoding='utf-8')
            else:
                context = {'incident': incident_data} if incident_data else {}
                script = self.generate_commentary_script(transcript_data['transcript'], context)
                script_path.write_text(script, encoding='utf-8')
                print(f"💾 Script saved: {script_path}")
            
            print("\n" + "-"*70)
            print("STEP 3: CONVERTING TO SPEECH")
            print("-"*70)
            audio_path = video_work_dir / f"{video_id}_commentary.mp3"
            
            # Check if audio already exists
            if audio_path.exists():
                print(f"✅ Using cached audio: {audio_path}")
            else:
                self.convert_to_speech(script, audio_path)
            
            video_path = None
            if auto_download:
                print("\n" + "-"*70)
                print("STEP 4: DOWNLOADING ORIGINAL VIDEO")
                print("-"*70)
                video_path = video_work_dir / f"{video_id}_original.mp4"
                
                # Check if video already exists
                if video_path.exists():
                    print(f"✅ Using cached video: {video_path}")
                else:
                    self.download_video(video_id, video_path)
            else:
                print("\n⏭️ Skipping video download (auto_download=False)")
                video_path = video_work_dir / f"{video_id}_original.mp4"
                print(f"📝 Please download video manually to: {video_path}")
            
            print("\n" + "-"*70)
            print("STEP 5: CREATING OBS/CAPCUT INSTRUCTIONS")
            print("-"*70)
            self.create_obs_project_file(video_id, video_path, audio_path, self.output_dir)
            
            print("\n" + "-"*70)
            print("STEP 6: MERGING VIDEO + AUDIO (AUTOMATED)")
            print("-"*70)
            final_video_path = self.output_dir / f"{video_id}_final_commentary.mp4"
            
            if final_video_path.exists():
                print(f"✅ Final video already exists: {final_video_path}")
            else:
                # Look for logo and cover files
                logo_path = Path('logo.png')
                if not logo_path.exists():
                    logo_path = Path('assets/logo.png')
                if not logo_path.exists():
                    logo_path = None
                
                cover_path = Path('cover.png')
                if not cover_path.exists():
                    cover_path = Path('assets/cover.png')
                if not cover_path.exists():
                    cover_path = None
                
                success = self.merge_video_audio(video_path, audio_path, final_video_path, logo_path, cover_path)
                if not success:
                    print("⚠️  Auto-merge failed. Use OBS/CapCut manually (see instructions)")
            
            print("\n" + "="*70)
            print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
            print("="*70)
            print(f"\n📂 Working Directory: {video_work_dir.absolute()}")
            print(f"\n📹 FINAL VIDEO: {final_video_path.absolute()}")
            print(f"\nFiles Created:")
            print(f"  1. Transcript: {transcript_path.name}")
            print(f"  2. Script: {script_path.name}")
            print(f"  3. Commentary Audio: {audio_path.name}")
            if auto_download:
                print(f"  4. Original Video: {video_path.name}")
            print(f"  5. OBS Instructions: {video_id}_OBS_INSTRUCTIONS.txt")
            print(f"  6. FINAL COMMENTARY VIDEO: {final_video_path.name}")
            
            print(f"\n🎬 NEXT STEPS:")
            print(f"  1. Watch the video: {final_video_path}")
            print(f"  2. If good → Upload to YouTube")
            print(f"  3. If not good → Edit script and re-run")
            
            return {
                'success': True,
                'video_id': video_id,
                'work_dir': str(video_work_dir),
                'files': {
                    'transcript': str(transcript_path),
                    'script': str(script_path),
                    'audio': str(audio_path),
                    'video': str(video_path) if auto_download else None
                }
            }
            
        except Exception as e:
            print(f"\n❌ PIPELINE FAILED: {e}")
            raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Video Commentary Pipeline for Islamophobia UK',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process by YouTube URL
  python video_commentary.py --url "https://youtube.com/watch?v=abc123"
  python video_commentary.py -u "https://youtube.com/watch?v=abc123"
  
  # Process by incident ID from database
  python video_commentary.py --id "cd0cdc60-9db6-4f1b-89f5-570605a86f4a"
  python video_commentary.py -i "cd0cdc60-9db6-4f1b-89f5-570605a86f4a"
  
  # Skip video download (if you already have it)
  python video_commentary.py --id "abc123" --no-download
        """
    )
    
    # URL argument (with short alias -u)
    parser.add_argument(
        '--url', '-u', '--youtube-url',
        dest='youtube_url',
        help='YouTube video URL'
    )
    
    # ID argument (with short alias -i)
    parser.add_argument(
        '--id', '-i', '--incident-id',
        dest='incident_id',
        help='Incident ID from database'
    )
    
    parser.add_argument(
        '--no-download',
        action='store_true',
        help='Skip video download (use cached video)'
    )
    
    args = parser.parse_args()
    
    if not args.youtube_url and not args.incident_id:
        parser.error("Must provide either --url/-u or --id/-i")
    
    pipeline = VideoCommentaryPipeline()
    pipeline.process_video(
        youtube_url=args.youtube_url,
        incident_id=args.incident_id,
        auto_download=not args.no_download
    )


if __name__ == '__main__':
    main()