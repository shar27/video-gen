"""
Flask API for Video Generation Pipeline
Two-step workflow: Generate video preview first, then add commentary
"""

import os
import json
import base64
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
WORK_DIR = Path('video_work')
WORK_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Initialize pipeline (lazy load)
pipeline = None
pipeline_error = None

def get_pipeline():
    global pipeline, pipeline_error
    if pipeline is None and pipeline_error is None:
        try:
            from video_generation import VideoGenerationPipeline
            pipeline = VideoGenerationPipeline()
        except Exception as e:
            pipeline_error = str(e)
    return pipeline

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def home():
    return jsonify({
        'service': 'Video Generation API',
        'version': '2.0.0',
        'workflow': 'Two-step: Generate preview, then add commentary',
        'endpoints': {
            '/api/health': 'GET - Health check',
            '/api/generate-video': 'POST - Step 1: Generate video from image + motion prompt',
            '/api/preview/<job_id>': 'GET - Stream preview video',
            '/api/add-commentary': 'POST - Step 2: Add script commentary to video',
            '/api/generate': 'POST - Legacy: Full pipeline in one request',
            '/api/jobs': 'GET - List completed jobs',
            '/api/download/<job_id>': 'GET - Download final video',
            '/api/voices': 'GET - List available TTS voices'
        }
    })


@app.route('/api/health')
def health():
    pipe = get_pipeline()
    return jsonify({
        'status': 'healthy' if pipe else 'degraded',
        'pipeline': 'ready' if pipe else pipeline_error,
        'kling_configured': bool(os.environ.get('KLING_ACCESS_KEY') and os.environ.get('KLING_SECRET_KEY')),
        'openai_configured': bool(os.environ.get('OPENAI_API_KEY'))
    })


# =============================================================================
# STEP 1: Generate Video Preview (no audio)
# =============================================================================
@app.route('/api/generate-video', methods=['POST'])
def generate_video_preview():
    """
    Step 1: Generate video from image + motion prompt
    Returns preview URL for user to review before adding commentary
    
    Accepts:
    - multipart/form-data with 'image' file and 'motion_prompt' text
    - JSON with 'image_url' or 'image_base64' and 'motion_prompt'
    """
    pipe = get_pipeline()
    if pipe is None:
        return jsonify({'error': f'Pipeline not available: {pipeline_error}'}), 500
    
    try:
        image_path = None
        motion_prompt = None
        duration = 10
        
        # Handle different content types
        if request.content_type and 'multipart/form-data' in request.content_type:
            # File upload
            if 'image' not in request.files:
                return jsonify({'error': 'No image file provided'}), 400
            
            file = request.files['image']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': f'Invalid file type. Allowed: {ALLOWED_EXTENSIONS}'}), 400
            
            filename = secure_filename(file.filename)
            image_path = str(UPLOAD_FOLDER / f"{uuid.uuid4().hex[:8]}_{filename}")
            file.save(image_path)
            
            motion_prompt = request.form.get('motion_prompt')
            duration = int(request.form.get('duration', 10))
            
        else:
            # JSON request
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            motion_prompt = data.get('motion_prompt')
            duration = data.get('duration', 10)
            
            if 'image_url' in data:
                image_path = data['image_url']
            elif 'image_base64' in data:
                # Save base64 image to file
                img_data = base64.b64decode(data['image_base64'])
                img_format = data.get('image_format', 'png')
                image_path = str(UPLOAD_FOLDER / f"upload_{uuid.uuid4().hex[:8]}.{img_format}")
                with open(image_path, 'wb') as f:
                    f.write(img_data)
            else:
                return jsonify({'error': 'No image provided (image_url or image_base64)'}), 400
        
        if not motion_prompt:
            return jsonify({'error': 'No motion_prompt provided'}), 400
        
        if duration not in [5, 10]:
            return jsonify({'error': 'Duration must be 5 or 10 seconds'}), 400
        
        # Create job directory
        job_id = str(uuid.uuid4())[:8]
        job_dir = WORK_DIR / job_id
        job_dir.mkdir(exist_ok=True)
        
        # Save job metadata
        job_meta = {
            'job_id': job_id,
            'status': 'generating_video',
            'image_path': image_path,
            'motion_prompt': motion_prompt,
            'duration': duration
        }
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"🎬 STEP 1: GENERATING VIDEO PREVIEW")
        print(f"   Job ID: {job_id}")
        print(f"   Image: {image_path}")
        print(f"   Motion: {motion_prompt}")
        print(f"   Duration: {duration}s")
        print(f"{'='*70}\n")
        
        # Generate video only (no audio)
        video_path = pipe.generate_video_from_image(
            image_path=image_path,
            motion_prompt=motion_prompt,
            duration=duration
        )
        
        # Copy video to job directory as preview
        import shutil
        preview_path = str(job_dir / 'preview.mp4')
        shutil.copy(video_path, preview_path)
        
        # Update job status
        job_meta['status'] = 'preview_ready'
        job_meta['preview_path'] = preview_path
        with open(job_dir / 'job.json', 'w') as f:
            json.dump(job_meta, f, indent=2)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'preview_ready',
            'preview_url': f"/api/preview/{job_id}",
            'next_step': 'POST /api/add-commentary with job_id, script, and voice'
        })
        
    except Exception as e:
        print(f"❌ Video generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/preview/<job_id>')
def get_preview(job_id):
    """Stream preview video for playback"""
    preview_path = WORK_DIR / job_id / 'preview.mp4'
    
    if not preview_path.exists():
        return jsonify({'error': 'Preview not found'}), 404
    
    return send_file(
        preview_path,
        mimetype='video/mp4',
        as_attachment=False
    )


@app.route('/api/job/<job_id>/status')
def get_job_status(job_id):
    """Get current job status"""
    job_file = WORK_DIR / job_id / 'job.json'
    
    if not job_file.exists():
        return jsonify({'error': 'Job not found'}), 404
    
    with open(job_file) as f:
        job_meta = json.load(f)
    
    return jsonify(job_meta)


# =============================================================================
# STEP 2: Add Commentary to Video
# =============================================================================
@app.route('/api/add-commentary', methods=['POST'])
def add_commentary():
    """
    Step 2: Add script commentary to previously generated video
    
    Requires:
    - job_id: The job ID from step 1
    - script: The commentary text
    - voice: TTS voice (optional, default: onyx)
    """
    pipe = get_pipeline()
    if pipe is None:
        return jsonify({'error': f'Pipeline not available: {pipeline_error}'}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        job_id = data.get('job_id')
        script = data.get('script')
        voice = data.get('voice', 'onyx')
        
        if not job_id:
            return jsonify({'error': 'No job_id provided'}), 400
        if not script:
            return jsonify({'error': 'No script provided'}), 400
        
        # Load job metadata
        job_dir = WORK_DIR / job_id
        job_file = job_dir / 'job.json'
        
        if not job_file.exists():
            return jsonify({'error': 'Job not found'}), 404
        
        with open(job_file) as f:
            job_meta = json.load(f)
        
        if job_meta.get('status') != 'preview_ready':
            return jsonify({'error': f"Job not ready for commentary. Status: {job_meta.get('status')}"}), 400
        
        preview_path = job_meta.get('preview_path')
        if not preview_path or not Path(preview_path).exists():
            return jsonify({'error': 'Preview video not found'}), 404
        
        print(f"\n{'='*70}")
        print(f"🎙️ STEP 2: ADDING COMMENTARY")
        print(f"   Job ID: {job_id}")
        print(f"   Script length: {len(script)} chars")
        print(f"   Voice: {voice}")
        print(f"{'='*70}\n")
        
        # Update job status
        job_meta['status'] = 'adding_commentary'
        job_meta['script'] = script
        job_meta['voice'] = voice
        with open(job_file, 'w') as f:
            json.dump(job_meta, f, indent=2)
        
        # Generate TTS audio
        print("-"*70)
        print("CONVERTING SCRIPT TO SPEECH")
        print("-"*70)
        audio_path = str(job_dir / 'commentary.mp3')
        pipe.convert_script_to_speech(script, audio_path, voice=voice)
        
        # Merge video and audio
        print("-"*70)
        print("MERGING VIDEO AND AUDIO")
        print("-"*70)
        final_video = str(job_dir / 'final_video.mp4')
        pipe.merge_video_audio(preview_path, audio_path, final_video)
        
        # Generate YouTube metadata
        print("-"*70)
        print("GENERATING YOUTUBE METADATA")
        print("-"*70)
        metadata = pipe.generate_youtube_metadata(script)
        
        # Save everything
        with open(job_dir / 'script.txt', 'w') as f:
            f.write(script)
        
        with open(job_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update job status
        job_meta['status'] = 'complete'
        job_meta['final_video'] = final_video
        job_meta['audio_path'] = audio_path
        job_meta['metadata'] = metadata
        with open(job_file, 'w') as f:
            json.dump(job_meta, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"✅ PIPELINE COMPLETE!")
        print(f"{'='*70}\n")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'complete',
            'download_url': f"/api/download/{job_id}",
            'metadata': metadata
        })
        
    except Exception as e:
        print(f"❌ Commentary error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Legacy: Full Pipeline (kept for backwards compatibility)
# =============================================================================
@app.route('/api/generate', methods=['POST'])
def generate_full():
    """
    Legacy endpoint: Full pipeline in one request
    Kept for backwards compatibility
    """
    pipe = get_pipeline()
    if pipe is None:
        return jsonify({'error': f'Pipeline not available: {pipeline_error}'}), 500
    
    try:
        image_path = None
        script = None
        motion_prompt = None
        voice = 'onyx'
        duration = 10
        
        # Handle different content types
        if request.content_type and 'multipart/form-data' in request.content_type:
            if 'image' not in request.files:
                return jsonify({'error': 'No image file provided'}), 400
            
            file = request.files['image']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': f'Invalid file type. Allowed: {ALLOWED_EXTENSIONS}'}), 400
            
            filename = secure_filename(file.filename)
            image_path = str(UPLOAD_FOLDER / filename)
            file.save(image_path)
            
            script = request.form.get('script')
            motion_prompt = request.form.get('motion_prompt')
            voice = request.form.get('voice', 'onyx')
            duration = int(request.form.get('duration', 10))
            
        else:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            script = data.get('script')
            motion_prompt = data.get('motion_prompt')
            voice = data.get('voice', 'onyx')
            duration = data.get('duration', 10)
            
            if 'image_url' in data:
                image_path = data['image_url']
            elif 'image_base64' in data:
                img_data = base64.b64decode(data['image_base64'])
                img_format = data.get('image_format', 'png')
                image_path = str(UPLOAD_FOLDER / f"upload_{os.urandom(8).hex()}.{img_format}")
                with open(image_path, 'wb') as f:
                    f.write(img_data)
            else:
                return jsonify({'error': 'No image provided'}), 400
        
        if not script:
            return jsonify({'error': 'No script provided'}), 400
        
        if duration not in [5, 10]:
            return jsonify({'error': 'Duration must be 5 or 10 seconds'}), 400
        
        result = pipe.process(
            image_path=image_path,
            script=script,
            motion_prompt=motion_prompt,
            voice=voice,
            duration=duration
        )
        
        return jsonify({
            'success': True,
            'job_id': result['job_id'],
            'download_url': f"/api/download/{result['job_id']}",
            'metadata': result['metadata']
        })
        
    except Exception as e:
        print(f"❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Download & Utility Endpoints
# =============================================================================
@app.route('/api/jobs')
def list_jobs():
    """List all jobs with their status"""
    jobs = []
    
    if WORK_DIR.exists():
        for job_dir in WORK_DIR.iterdir():
            if job_dir.is_dir():
                job_file = job_dir / 'job.json'
                if job_file.exists():
                    with open(job_file) as f:
                        job_meta = json.load(f)
                    jobs.append({
                        'job_id': job_dir.name,
                        'status': job_meta.get('status', 'unknown'),
                        'has_preview': (job_dir / 'preview.mp4').exists(),
                        'has_final': (job_dir / 'final_video.mp4').exists(),
                        'preview_url': f"/api/preview/{job_dir.name}" if (job_dir / 'preview.mp4').exists() else None,
                        'download_url': f"/api/download/{job_dir.name}" if (job_dir / 'final_video.mp4').exists() else None
                    })
    
    return jsonify(jobs)


@app.route('/api/download/<job_id>')
def download_video(job_id):
    """Download final video"""
    video_path = WORK_DIR / job_id / 'final_video.mp4'
    
    if not video_path.exists():
        return jsonify({'error': 'Video not found'}), 404
    
    return send_file(
        video_path,
        mimetype='video/mp4',
        as_attachment=True,
        download_name=f'generated_video_{job_id}.mp4'
    )


@app.route('/api/download/<job_id>/audio')
def download_audio(job_id):
    """Download audio commentary"""
    audio_path = WORK_DIR / job_id / 'commentary.mp3'
    
    if not audio_path.exists():
        return jsonify({'error': 'Audio not found'}), 404
    
    return send_file(
        audio_path,
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name=f'commentary_{job_id}.mp3'
    )


@app.route('/api/voices')
def list_voices():
    """List available TTS voices (ElevenLabs)"""
    return jsonify({
        'voices': [
            # Documentary / Narrator voices (recommended)
            {'id': 'george', 'name': 'George', 'description': 'British, warm, raspy - Perfect for nature documentaries', 'recommended': True},
            {'id': 'daniel', 'name': 'Daniel', 'description': 'British, authoritative - Great for factual content', 'recommended': True},
            {'id': 'bill', 'name': 'Bill', 'description': 'Older male, trustworthy - Classic narrator voice', 'recommended': True},
            {'id': 'clyde', 'name': 'Clyde', 'description': 'War veteran character - Deep, gravelly'},
            # Additional voices
            {'id': 'adam', 'name': 'Adam', 'description': 'Deep, narrative - American male'},
            {'id': 'antoni', 'name': 'Antoni', 'description': 'Well-rounded narrator - Young male'},
            {'id': 'drew', 'name': 'Drew', 'description': 'News reader - Middle-aged male'},
            {'id': 'rachel', 'name': 'Rachel', 'description': 'Calm, young female - American'},
        ],
        'default': 'george',
        'provider': 'ElevenLabs'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)