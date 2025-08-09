import re
import html
import logging
from typing import Dict, List, Set, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class HTMLSanitizer:
    """Secure HTML sanitizer for Streamlit content"""
    
    # Allowed HTML tags for basic formatting
    ALLOWED_TAGS = {
        'div', 'span', 'p', 'br', 'hr',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'b', 'em', 'i', 'u',
        'ul', 'ol', 'li',
        'small', 'code', 'pre'
    }
    
    # Allowed attributes for specific tags
    ALLOWED_ATTRIBUTES = {
        'div': {'class', 'style'},
        'span': {'class', 'style'},
        'p': {'class', 'style'},
        'h1': {'class', 'style'},
        'h2': {'class', 'style'},
        'h3': {'class', 'style'},
        'h4': {'class', 'style'},
        'h5': {'class', 'style'},
        'h6': {'class', 'style'},
        'code': {'class'},
        'pre': {'class'},
    }
    
    # Allowed CSS properties for style attributes
    ALLOWED_CSS_PROPERTIES = {
        'color', 'background-color', 'background',
        'font-size', 'font-weight', 'font-family', 'font-style',
        'text-align', 'text-decoration', 'text-transform',
        'margin', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right',
        'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
        'border', 'border-radius', 'border-width', 'border-style', 'border-color',
        'width', 'height', 'max-width', 'max-height', 'min-width', 'min-height',
        'display', 'position', 'top', 'bottom', 'left', 'right',
        'opacity', 'visibility', 'overflow', 'z-index'
    }
    
    # Dangerous patterns to remove
    DANGEROUS_PATTERNS = [
        r'javascript:', r'vbscript:', r'data:', r'file:',
        r'on\w+\s*=', r'<script', r'</script>',
        r'<iframe', r'</iframe>', r'<object', r'</object>',
        r'<embed', r'</embed>', r'<form', r'</form>',
        r'<input', r'<button', r'<select', r'<textarea',
        r'expression\s*\(', r'@import', r'url\s*\(',
        r'<link', r'<meta', r'<base', r'<style', r'</style>'
    ]
    
    @classmethod
    def sanitize_html(cls, html_content: str) -> str:
        """Sanitize HTML content for safe rendering"""
        if not html_content or not isinstance(html_content, str):
            return ""
            
        try:
            # First pass: remove dangerous patterns
            sanitized = cls._remove_dangerous_patterns(html_content)
            
            # Second pass: validate and clean tags
            sanitized = cls._clean_tags(sanitized)
            
            # Third pass: validate and clean attributes
            sanitized = cls._clean_attributes(sanitized)
            
            # Fourth pass: validate CSS in style attributes
            sanitized = cls._clean_css(sanitized)
            
            return sanitized
            
        except Exception as e:
            logger.warning(f"HTML sanitization error: {e}")
            # Return escaped version as fallback
            return html.escape(html_content)
    
    @classmethod
    def _remove_dangerous_patterns(cls, content: str) -> str:
        """Remove dangerous patterns from content"""
        for pattern in cls.DANGEROUS_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        return content
    
    @classmethod
    def _clean_tags(cls, content: str) -> str:
        """Remove or escape disallowed HTML tags"""
        # Find all HTML tags
        tag_pattern = r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>'
        
        def replace_tag(match):
            closing = match.group(1)
            tag_name = match.group(2).lower()
            full_tag = match.group(0)
            
            if tag_name in cls.ALLOWED_TAGS:
                return full_tag
            else:
                # Escape disallowed tags
                return html.escape(full_tag)
        
        return re.sub(tag_pattern, replace_tag, content)
    
    @classmethod
    def _clean_attributes(cls, content: str) -> str:
        """Clean attributes in allowed tags"""
        # Pattern to match tag with attributes
        tag_pattern = r'<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>'
        
        def clean_tag_attributes(match):
            tag_name = match.group(1).lower()
            attributes = match.group(2)
            
            if tag_name not in cls.ALLOWED_TAGS:
                return match.group(0)  # Keep as-is if tag not allowed
            
            # Clean attributes
            cleaned_attrs = cls._clean_tag_attributes(tag_name, attributes)
            return f'<{tag_name}{cleaned_attrs}>'
        
        return re.sub(tag_pattern, clean_tag_attributes, content)
    
    @classmethod
    def _clean_tag_attributes(cls, tag_name: str, attributes: str) -> str:
        """Clean attributes for a specific tag"""
        if not attributes.strip():
            return ''
            
        allowed_attrs = cls.ALLOWED_ATTRIBUTES.get(tag_name, set())
        if not allowed_attrs:
            return ''
        
        # Parse attributes
        attr_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'
        cleaned_attrs = []
        
        for match in re.finditer(attr_pattern, attributes):
            attr_name = match.group(1).lower()
            attr_value = match.group(2)
            
            if attr_name in allowed_attrs:
                # Additional validation for specific attributes
                if attr_name == 'style':
                    attr_value = cls._clean_style_attribute(attr_value)
                elif attr_name == 'class':
                    attr_value = cls._clean_class_attribute(attr_value)
                
                if attr_value:  # Only add if value is not empty after cleaning
                    cleaned_attrs.append(f'{attr_name}="{attr_value}"')
        
        return ' ' + ' '.join(cleaned_attrs) if cleaned_attrs else ''
    
    @classmethod
    def _clean_style_attribute(cls, style: str) -> str:
        """Clean CSS style attribute"""
        if not style:
            return ''
        
        # Split by semicolon and validate each property
        properties = []
        for prop in style.split(';'):
            prop = prop.strip()
            if ':' in prop:
                prop_name, prop_value = prop.split(':', 1)
                prop_name = prop_name.strip().lower()
                prop_value = prop_value.strip()
                
                if (prop_name in cls.ALLOWED_CSS_PROPERTIES and 
                    cls._is_safe_css_value(prop_value)):
                    properties.append(f'{prop_name}:{prop_value}')
        
        return ';'.join(properties)
    
    @classmethod
    def _clean_class_attribute(cls, class_value: str) -> str:
        """Clean class attribute"""
        if not class_value:
            return ''
        
        # Only allow alphanumeric, hyphens, and underscores
        safe_classes = []
        for class_name in class_value.split():
            if re.match(r'^[a-zA-Z0-9_-]+$', class_name):
                safe_classes.append(class_name)
        
        return ' '.join(safe_classes)
    
    @classmethod
    def _is_safe_css_value(cls, value: str) -> bool:
        """Check if CSS value is safe"""
        if not value:
            return False
        
        # Remove dangerous patterns
        dangerous_css_patterns = [
            r'javascript:', r'expression\s*\(', r'@import',
            r'url\s*\(', r'<', r'>', r'&lt;', r'&gt;'
        ]
        
        for pattern in dangerous_css_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
    
    @classmethod
    def _clean_css(cls, content: str) -> str:
        """Final CSS cleaning pass"""
        # Remove any remaining style blocks
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.IGNORECASE | re.DOTALL)
        return content

# Streamlit-specific safe rendering functions
class StreamlitSafeRenderer:
    """Safe rendering utilities for Streamlit"""
    
    @staticmethod
    def safe_markdown(content: str, allow_html: bool = False) -> str:
        """Safely render markdown content"""
        if not allow_html:
            # For plain markdown, escape any HTML
            return html.escape(content) if content else ""
        
        # For HTML content, sanitize it
        return HTMLSanitizer.sanitize_html(content)
    
    @staticmethod
    def safe_html(content: str) -> str:
        """Safely render HTML content"""
        return HTMLSanitizer.sanitize_html(content)
    
    @staticmethod
    def create_safe_progress_bar(progress: float, color: str = "green") -> str:
        """Create a safe progress bar HTML"""
        # Validate inputs
        progress = max(0, min(100, float(progress)))
        
        # Only allow safe colors
        safe_colors = {
            'green', 'blue', 'red', 'orange', 'purple', 'gray', 'grey',
            'lightgray', 'lightgrey', 'darkgray', 'darkgrey'
        }
        
        if color not in safe_colors:
            color = 'gray'
        
        html_content = f"""
        <div style="width:100%;background-color:lightgray;border-radius:4px;height:8px;">
            <div style="width:{progress}%;background-color:{color};border-radius:4px;height:8px;"></div>
        </div>
        """
        
        return HTMLSanitizer.sanitize_html(html_content)
    
    @staticmethod
    def create_safe_status_badge(status: str, color: str = "blue") -> str:
        """Create a safe status badge HTML"""
        # Sanitize status text
        status = html.escape(str(status)[:50])  # Limit length
        
        # Only allow safe colors
        safe_colors = {
            'green': '#28a745',
            'blue': '#007bff', 
            'red': '#dc3545',
            'orange': '#fd7e14',
            'yellow': '#ffc107',
            'gray': '#6c757d'
        }
        
        color_code = safe_colors.get(color, safe_colors['gray'])
        
        html_content = f"""
        <span style="background-color:{color_code};color:white;padding:4px 8px;border-radius:4px;font-size:12px;">
            {status}
        </span>
        """
        
        return HTMLSanitizer.sanitize_html(html_content)