# app/services/content_processor.py
import os
import logging
from openai import OpenAI, APIError, APITimeoutError
from app.services import utils
from app.core.config import settings
from app.db import crud
from app.db.base import get_db_session
import json

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

def run_ai_generation(prompt: str, model="gpt-4o-mini", max_tokens=2000, temperature=0.5, expect_json=False):
    """Generate AI content with error handling"""
    if not client: 
        logger.error("OpenAI client not initialized - check API key")
        return None
        
    logger.info(f"Calling OpenAI API for model {model}...")
    try:
        response_format = {"type": "json_object"} if expect_json else {"type": "text"}
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            timeout=30  # 30 second timeout for chat completions
        )
        result_text = response.choices[0].message.content
        
        if expect_json:
            try:
                json.loads(result_text)
            except json.JSONDecodeError:
                logger.warning(f"AI returned invalid JSON. Content: {result_text[:200]}...")
                return None
                
        return result_text
    except (APITimeoutError, APIError) as e:
        logger.error(f"OpenAI API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in AI generation: {e}")
        return None

def ingest_content(user_input: str):
    """Handles ingestion of text, YouTube URLs, or other article URLs."""
    try:
        if utils.is_youtube_url(user_input):
            logger.info("YouTube URL detected. Getting transcript...")
            # Use the correct function name from your utils
            audio_info = utils.download_media(user_input, is_video=False)
            if not audio_info.get('success'):
                raise ValueError(f"Failed to download audio: {audio_info.get('error')}")
            
            # For content processing, we just need the text, not full transcription
            # This is a simplified approach - you could enhance it later
            return f"Content from YouTube video: {audio_info.get('title', 'Unknown video')}"
            
        elif utils.is_valid_url(user_input):
            logger.info("Article URL detected. Scraping content...")
            content = utils.scrape_url(user_input)
            if content.startswith("Error:"):
                raise ValueError(content)
            return content
        else:
            # It's raw text
            return user_input
            
    except Exception as e:
        logger.error(f"Content ingestion failed: {e}")
        raise ValueError(f"Failed to process input: {str(e)}")

def generate_repurpose_content(user_input: str, user_id: int = None):
    """Main logic for the repurposing job with brand voice support."""
    try:
        content_to_process = ingest_content(user_input)
        
        # Get user's brand voice if available
        brand_voice = {}
        if user_id:
            try:
                with get_db_session() as db:  # Fixed: proper database session
                    brand_profile = crud.get_brand_profile(db, user_id)
                    if brand_profile and brand_profile.get('brand_voice'):
                        try:
                            brand_voice = json.loads(brand_profile['brand_voice'])
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"Invalid brand voice JSON for user {user_id}")
                            brand_voice = {}
            except Exception as e:
                logger.warning(f"Failed to get brand profile for user {user_id}: {e}")
        
        # Analyze content
        analysis_prompt = f"""Analyze the provided content in depth. Identify and summarize:

Core message & main themes (the underlying ideas driving the content)

Target audience (demographics, interests, pain points, and motivations)

Tone & voice (formal/informal, playful/serious, authoritative/conversational)

Engagement drivers (specific hooks, emotions, formats, or storytelling techniques that make it compelling)

Then:

Explain why these elements work together to capture attention.

Suggest how they could be adapted for social media to preserve authenticity while maximizing engagement on different platforms.
        
        CONTENT:
        {content_to_process[:4000]}"""
        
        content_analysis = run_ai_generation(analysis_prompt, model="gpt-4o")
        if not content_analysis:
            raise ValueError("Content analysis failed")

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

        # Generate content
        generation_prompt = f"""
You are an expert-level social media content strategist and copywriter with a deep understanding of how creators speak naturally to their audiences. Transform the provided source content into posts that feel like they were written by a real creator, not a brand or marketer.

{voice_instructions}

GUIDELINES:

Make every post platform-native, using formatting, pacing, and language that matches how real creators post there.

Avoid generic marketing speak or overly polished "ad" language—favor authenticity, relatability, and audience connection.

Embed subtle personality quirks, casual language, or creator habits that make posts feel human.

Platform Breakdown:

LinkedIn: Professional but human; thought-provoking with a personal takeaway. Use bullet points or short paragraphs for scanability.

Twitter/X: Concise, hook-first. Use threads where needed. Blend wit, insight, or curiosity gaps to encourage replies.

Instagram: Tell a story in a visual way. Break text for readability. Include 5–10 hashtags relevant to the niche.

TikTok: Write as if scripting a creator's voiceover or caption. Use trending hook styles and natural speech flow.

YouTube: Write engaging, SEO-aware video descriptions that encourage watch time and subscriptions, without feeling keyword-stuffed.

Facebook: Conversational, community-driven, and designed to spark discussion. Reference shared experiences or relatable moments.

SOURCE CONTENT:
{content_to_process[:8000]}

Generate compelling posts for multiple platforms. Use markdown headings for each platform (e.g., ## LinkedIn, ## Twitter, ## YouTube, ## Facebook).
"""
        
        drafts = run_ai_generation(generation_prompt, model="gpt-4o", max_tokens=3000)
        if not drafts:
            raise ValueError("Content generation failed")

        return {
            "analysis": content_analysis, 
            "posts": drafts,
            "brand_voice_used": bool(brand_voice)
        }
        
    except Exception as e:
        logger.error(f"Content repurposing failed: {e}")
        raise ValueError(f"Content processing failed: {str(e)}")

def generate_social_posts(content: str, platforms: list[str], tone: str = "Professional", style: str = "Concise"):
    """Generate platform-specific social media posts"""
    platform_str = ", ".join(platforms)
    
    prompt = f"""You are an expert-level social media content strategist and copywriter with a deep understanding of how creators speak naturally to their audiences. Create engaging social media posts for {platform_str}, ensuring each one feels like it was written by a real creator, not a brand or marketer.
    
    TONE: {tone}
    STYLE: {style}
    
    GUIDELINES:
    
    Make every post platform-native, using formatting, pacing, and language that matches how real creators post there.
    
    Avoid generic marketing speak or overly polished "ad" language—favor authenticity, relatability, and audience connection.
    
    Embed subtle personality quirks, casual language, or creator habits that make posts feel human.
    
    Platform Breakdown:
    
    LinkedIn: Professional but human; thought-provoking with a personal takeaway. Use bullet points or short paragraphs for scanability.
    
    Twitter/X: Concise, hook-first. Use threads where needed. Blend wit, insight, or curiosity gaps to encourage replies.
    
    Instagram: Tell a story in a visual way. Break text for readability. Include 5–10 hashtags relevant to the niche.
    
    TikTok: Write as if scripting a creator's voiceover or caption. Use trending hook styles and natural speech flow.
    
    YouTube: Write engaging, SEO-aware video descriptions that encourage watch time and subscriptions, without feeling keyword-stuffed.
    
    Facebook: Conversational, community-driven, and designed to spark discussion. Reference shared experiences or relatable moments.
    
    CONTENT TO REPURPOSE:
    {content[:6000]}
    
    Create one optimized post for each platform. Use markdown headings (## Platform Name).
    """
    
    return run_ai_generation(prompt, model="gpt-4o", max_tokens=2000)