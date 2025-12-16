"""
Flask API for Video Generation Pipeline
"""

import os
import json
import base64
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    # Add your Azure frontend URL here
])

# Configuration
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Initialize pipeline (lazy load)
pipeline = None
pipeline_error = None

def get_pipeline():
    global pipeline, pipeline_error
    if pipeline is None and pipeline_error is None:
        try:
            from api.video_generation import VideoGenerationPipeline
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
        'version': '1.0.0',
        'endpoints': {
            '/api/health': 'Health check',
            '/api/generate': 'POST - Generate video from image + script',
            '/api/jobs': 'GET - List completed jobs',
            '/api/download/<job_id>': 'GET - Download generated video'
        }
    })


@app.route('/api/health')
def health():
    pipe = get_pipeline()
    return jsonify({
        'status': 'healthy' if pipe else 'degraded',
        'pipeline': 'ready' if pipe else pipeline_error,
        'runway_configured': bool(os.environ.get('RUNWAYML_API_SECRET')),
        'openai_configured': bool(os.environ.get('OPENAI_API_KEY'))
    })


@app.route('/api/generate', methods=['POST'])
def generate_video():
    """
    Generate video from image + script
    
    Accepts:
    - multipart/form-data with 'image' file and 'script' text
    - JSON with 'image_url' and 'script'
    - JSON with 'image_base64' and 'script'
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
            # File upload
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
            # JSON request
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
                # Save base64 image to file
                img_data = base64.b64decode(data['image_base64'])
                img_format = data.get('image_format', 'png')
                image_path = str(UPLOAD_FOLDER / f"upload_{os.urandom(8).hex()}.{img_format}")
                with open(image_path, 'wb') as f:
                    f.write(img_data)
            else:
                return jsonify({'error': 'No image provided (image_url or image_base64)'}), 400
        
        if not script:
            return jsonify({'error': 'No script provided'}), 400
        
        if duration not in [5, 10]:
            return jsonify({'error': 'Duration must be 5 or 10 seconds'}), 400
        
        # Process video
        print(f"\n{'='*70}")
        print(f"🎬 NEW VIDEO GENERATION REQUEST")
        print(f"   Image: {image_path}")
        print(f"   Script length: {len(script)} chars")
        print(f"   Voice: {voice}")
        print(f"   Duration: {duration}s")
        print(f"{'='*70}\n")
        
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
            'metadata': result['metadata'],
            'files': {
                'video': True,
                'audio': True,
                'script': True
            }
        })
        
    except Exception as e:
        print(f"❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs')
def list_jobs():
    """List all completed jobs"""
    work_dir = Path('video_work')
    jobs = []
    
    if work_dir.exists():
        for job_dir in work_dir.iterdir():
            if job_dir.is_dir() and (job_dir / 'final_video.mp4').exists():
                metadata = {}
                metadata_file = job_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                
                jobs.append({
                    'job_id': job_dir.name,
                    'metadata': metadata,
                    'download_url': f"/api/download/{job_dir.name}"
                })
    
    return jsonify(jobs)


@app.route('/api/download/<job_id>')
def download_video(job_id):
    """Download generated video"""
    video_path = Path('video_work') / job_id / 'final_video.mp4'
    
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
    audio_path = Path('video_work') / job_id / 'commentary.mp3'
    
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
    """List available TTS voices"""
    return jsonify({
        'voices': [
            {'id': 'alloy', 'description': 'Neutral, balanced'},
            {'id': 'echo', 'description': 'Warm, conversational'},
            {'id': 'fable', 'description': 'Expressive, dramatic'},
            {'id': 'onyx', 'description': 'Deep, authoritative'},
            {'id': 'nova', 'description': 'Friendly, upbeat'},
            {'id': 'shimmer', 'description': 'Clear, professional'}
        ],
        'default': 'onyx'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
