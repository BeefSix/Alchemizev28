# app/services/magic_editor.py - REPLACE WITH THIS SIMPLE VERSION

import json
import logging
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

class MagicVideoEditor:
    """Simple AI video editor"""
    
    def __init__(self):
        self.client = client
        
    def process_magic_command(self, transcript_data: dict, command: str, video_duration: float) -> dict:
        """Process a magic command and return segments to edit"""
        if not self.client:
            return {
                "action": "extract",
                "segments": [],
                "explanation": "OpenAI not configured",
                "confidence": 0.0
            }
        
        # Format transcript for AI
        transcript_text = self._format_transcript(transcript_data)
        
        # Create AI prompt
        prompt = f"""Find video segments for this command: "{command}"

TRANSCRIPT:
{transcript_text}

Return JSON with segments:
{{
    "action": "extract",
    "segments": [
        {{"start": 10.5, "end": 20.3, "reason": "matches command"}}
    ],
    "explanation": "Found matching segments",
    "confidence": 0.8
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=30  # 30 second timeout for chat completions
            )
            
            result = json.loads(response.choices[0].message.content)
            return self._clean_result(result, video_duration)
            
        except Exception as e:
            logger.error(f"Magic command failed: {e}")
            return {
                "action": "extract",
                "segments": [],
                "explanation": f"Error: {str(e)}",
                "confidence": 0.0
            }
    
    def _format_transcript(self, transcript_data: dict) -> str:
        """Format transcript for AI"""
        words = transcript_data.get('words', [])
        if not words:
            return transcript_data.get('text', 'No transcript available')
        
        # Simple sentence grouping
        sentences = []
        current_words = []
        
        for word_data in words:
            word = word_data.get('word', '').strip()
            start_time = word_data.get('start', 0)
            
            current_words.append(word)
            
            # End sentence every 10 words or on punctuation
            if len(current_words) >= 10 or word.endswith(('.', '!', '?')):
                sentence = ' '.join(current_words)
                sentences.append(f"[{start_time:.1f}s]: {sentence}")
                current_words = []
        
        return '\n'.join(sentences[:20])  # Limit to first 20 sentences
    
    def _clean_result(self, result: dict, video_duration: float) -> dict:
        """Clean and validate AI result"""
        # Set defaults
        if 'action' not in result:
            result['action'] = 'extract'
        if 'segments' not in result:
            result['segments'] = []
        if 'explanation' not in result:
            result['explanation'] = 'No explanation'
        if 'confidence' not in result:
            result['confidence'] = 0.5
        
        # Clean segments
        clean_segments = []
        for segment in result.get('segments', []):
            if 'start' in segment and 'end' in segment:
                start = max(0, min(float(segment['start']), video_duration))
                end = max(start + 1, min(float(segment['end']), video_duration))
                
                clean_segments.append({
                    'start': start,
                    'end': end,
                    'reason': segment.get('reason', 'AI selected'),
                    'duration': end - start
                })
        
        result['segments'] = clean_segments
        return result