# app/services/content_processor.py
import os
from openai import OpenAI, APIError, APITimeoutError
from app.services import utils
from app.core.config import settings
import json

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def run_ai_generation(prompt: str, model="gpt-4o-mini", max_tokens=2000, temperature=0.5, expect_json=False):
    if not client: 
        return None
    print(f"Calling OpenAI API for model {model}...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        result_text = response.choices[0].message.content
        if expect_json:
            try:
                json.loads(result_text)
            except json.JSONDecodeError:
                print(f"⚠️ AI returned invalid JSON. Content: {result_text}")
                return None
        return result_text
    except (APITimeoutError, APIError) as e:
        print(f"Error: AI generation failed: {e}")
        return None

def ingest_content(user_input: str):
    """Handles ingestion of text, YouTube URLs, or other article URLs."""
    if utils.is_youtube_url(user_input):
        print("YouTube URL detected. Getting transcript...")
        transcript_result = utils.get_or_create_transcript_sync(user_input)
        if transcript_result['success']:
            return transcript_result['data']['text']
        else:
            raise ValueError(f"Failed to get transcript: {transcript_result['error']}")
    elif utils.is_valid_url(user_input):
        print("Article URL detected. Scraping content...")
        content = utils.scrape_url(user_input)
        if content.startswith("Error:"):
            raise ValueError(content)
        return content
    else:
        # It's raw text
        return user_input

def generate_repurpose_content(user_input: str, user_id: int = None):
    """Main logic for the repurposing job with brand voice support."""
    content_to_process = ingest_content(user_input)
    
    # Get user's brand voice if available
    brand_voice = {}
    if user_id:
        from app.db import crud
        from app.db.base import get_db
        db = next(get_db())
        brand_profile = crud.get_brand_profile(db, user_id)
        if brand_profile and brand_profile.get('brand_voice'):
            try:
                brand_voice = json.loads(brand_profile['brand_voice'])
            except:
                brand_voice = {}
    
    analysis_prompt = f"Analyze this content and extract key insights, tone, and audience.\n\nCONTENT:\n{content_to_process[:4000]}"
    content_analysis = run_ai_generation(analysis_prompt, model="gpt-4o")

    # Build brand voice prompt if available
    voice_instructions = ""
    if brand_voice:
        voice_instructions = f"""
WRITE IN THIS SPECIFIC BRAND VOICE:
- Tone: {brand_voice.get('tone', 'friendly')}
- Energy: {brand_voice.get('energy_level', 'medium')} energy
- Personality: {', '.join(brand_voice.get('personality_traits', ['helpful']))}
- Target Audience: {brand_voice.get('target_audience', 'general audience')}
- Call-to-Action Style: {brand_voice.get('call_to_action_style', 'Ask a question')}
- Emoji Usage: {brand_voice.get('emoji_usage', 'moderate')}

SAMPLE WRITING STYLE:
{chr(10).join(brand_voice.get('sample_posts', [])[:2])}

IMPORTANT: Match this exact writing style, tone, and voice in all posts.
"""

    generation_prompt = f"""
    You are an expert content strategist. Transform the provided source content into a suite of high-quality social media posts.
    
    {voice_instructions}
    
    - Base all posts on the SOURCE CONTENT.
    - For LinkedIn/Facebook, use bullet points or lists for depth.
    - For Twitter/Instagram, end with an engaging question.

    SOURCE CONTENT:
    ```
    {content_to_process[:12000]}
    ```
    ---
    Generate the posts now. Use markdown headings for each platform (e.g., ### Twitter).
    """
    drafts = run_ai_generation(generation_prompt, model="gpt-4o")

    return {"analysis": content_analysis, "posts": drafts}