#!/usr/bin/env python3
"""
Generate images using Google Gemini API for Xiaohongshu infographics.
Supports multiple models with fallback: tries gemini-3-pro-image-preview first,
falls back to gemini-2.5-flash-image if the first model fails.
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

from google import genai
from google.genai import types
from PIL import Image
import io

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_api_key() -> str:
    """Get Gemini API key from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set it in your .env file or environment variables.")
        sys.exit(1)
    return api_key


def load_style_preset(style: str) -> Dict[str, Any]:
    """Load style preset configuration."""
    # This is a simplified version - in a full implementation,
    # you would load from references/presets/{style}.md
    presets = {
        "cute": {
            "description": "Sweet, adorable, girly - classic Xiaohongshu aesthetic",
            "colors": ["#FFB7C5", "#FFD6E7", "#FFF0F5"],  # Pastel pink
            "elements": ["hearts", "stars-sparkles", "clouds"]
        },
        "fresh": {
            "description": "Clean, refreshing, natural",
            "colors": ["#A8E6CF", "#DCEDC1", "#FFD3B6"],  # Pastel green/peach
            "elements": ["leaves", "clouds", "water-droplets"]
        },
        "warm": {
            "description": "Cozy, friendly, approachable",
            "colors": ["#FFCC99", "#FFB366", "#FF9966"],  # Warm orange
            "elements": ["clouds", "stars-sparkles", "coffee-cup"]
        },
        "bold": {
            "description": "High impact, attention-grabbing",
            "colors": ["#FF6B6B", "#4ECDC4", "#FFE66D"],  # Bright red/teal/yellow
            "elements": ["star-burst", "explosion", "arrow"]
        },
        "minimal": {
            "description": "Ultra-clean, sophisticated",
            "colors": ["#FFFFFF", "#F5F5F5", "#E0E0E0"],  # White/gray
            "elements": ["thin-line", "dot", "simple-frame"]
        },
        "retro": {
            "description": "Vintage, nostalgic, trendy",
            "colors": ["#FF9A8B", "#FF6F91", "#FF9671"],  # Retro orange/pink
            "elements": ["geometric", "line-art", "vintage-frame"]
        },
        "pop": {
            "description": "Vibrant, energetic, eye-catching",
            "colors": ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3"],  # Bright palette
            "elements": ["explosion", "star-burst", "confetti"]
        },
        "notion": {
            "description": "Minimalist hand-drawn line art, intellectual",
            "colors": ["#1A1A1A", "#4A4A4A", "#A8D4F0", "#F9E79F", "#FADBD8"],  # Notion palette
            "elements": ["hand-drawn-line", "checkmark", "bulb"]
        },
        "chalkboard": {
            "description": "Colorful chalk on black board, educational",
            "colors": ["#000000", "#FFFFFF", "#FFD700", "#FF69B4", "#00CED1"],  # Chalk colors
            "elements": ["chalk-line", "eraser-mark", "chalk-dust"]
        },
        "study-notes": {
            "description": "Realistic handwritten photo style",
            "colors": ["#0000FF", "#FF0000", "#FFFF00"],  # Blue pen, red annotation, yellow highlighter
            "elements": ["handwriting", "highlighter", "sticky-note"]
        }
    }
    
    return presets.get(style, presets["notion"])


def load_layout_preset(layout: str) -> Dict[str, Any]:
    """Load layout preset configuration."""
    layouts = {
        "sparse": {
            "description": "Minimal information, maximum impact (1-2 points)",
            "density": "low",
            "whitespace": "60-70%"
        },
        "balanced": {
            "description": "Standard content layout (3-4 points)",
            "density": "medium",
            "whitespace": "40-50%"
        },
        "dense": {
            "description": "High information density, knowledge card style (5-8 points)",
            "density": "high",
            "whitespace": "20-30%"
        },
        "list": {
            "description": "Enumeration and ranking format (4-7 items)",
            "density": "medium",
            "whitespace": "30-40%"
        },
        "comparison": {
            "description": "Side-by-side contrast layout",
            "density": "medium",
            "whitespace": "30-40%"
        },
        "flow": {
            "description": "Process and timeline layout (3-6 steps)",
            "density": "medium",
            "whitespace": "30-40%"
        },
        "mindmap": {
            "description": "Center radial mind map layout (4-8 branches)",
            "density": "high",
            "whitespace": "20-30%"
        },
        "quadrant": {
            "description": "Four-quadrant / circular section layout",
            "density": "medium",
            "whitespace": "30-40%"
        }
    }
    
    return layouts.get(layout, layouts["balanced"])


def build_prompt(
    content_prompt: str,
    style: str = "notion",
    layout: str = "balanced",
    ref_image_path: Optional[str] = None
) -> str:
    """Build a complete prompt for image generation."""
    
    # Load presets
    style_preset = load_style_preset(style)
    layout_preset = load_layout_preset(layout)
    
    # Base prompt structure
    prompt_parts = [
        "Create a Xiaohongshu (Little Red Book) style infographic image.",
        "",
        "## Image Specifications",
        "- Type: Infographic",
        "- Orientation: Portrait (vertical)",
        "- Aspect Ratio: 3:4",
        f"- Style: {style_preset['description']}",
        "",
        "## Visual Style Guidelines",
        f"- Color palette: {', '.join(style_preset['colors'])}",
        f"- Visual elements: {', '.join(style_preset['elements'])}",
        f"- Layout: {layout_preset['description']}",
        f"- Information density: {layout_preset['density']}",
        f"- Whitespace: {layout_preset['whitespace']}",
        "",
        "## Content Requirements",
        "- ALL text MUST be hand-drawn style (no computer fonts)",
        "- Key text should be bold and enlarged",
        "- Use Chinese (简体中文) for all text unless specified otherwise",
        "- Keep information concise, highlight keywords and core concepts",
        "- NO realistic or photographic elements",
        "",
        "## Content to Illustrate",
        content_prompt,
        "",
        "## Additional Instructions",
        "- Maintain visual consistency with hand-drawn aesthetic",
        "- Ensure text is legible and well-integrated with visuals",
        "- Create engaging composition suitable for social media",
    ]
    
    # Add reference image instruction if provided
    if ref_image_path and os.path.exists(ref_image_path):
        prompt_parts.append("")
        prompt_parts.append("## Visual Consistency Requirement")
        prompt_parts.append(f"- Maintain same character design, color rendering, and illustration style as reference image")
        prompt_parts.append(f"- Match the visual aesthetic and artistic style")
    
    return "\n".join(prompt_parts)


def generate_with_model(
    client: genai.Client,
    prompt: str,
    model: str,
    max_retries: int = 3
) -> Optional[bytes]:
    """Generate image with a specific model, with retry logic."""
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries} with model: {model}")
            
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
            )
            
            # Extract image data
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    return part.inline_data.data
            
            print(f"No image data found in response from model {model}")
            return None
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error with model {model}: {error_msg}")
            
            # Check if it's a model-specific error that warrants fallback
            if "503" in error_msg or "UNAVAILABLE" in error_msg.upper():
                print(f"Model {model} is unavailable, will try fallback")
                return None  # Signal to try fallback
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts with model {model}")
                return None
    
    return None


def generate_image(
    prompt: str,
    output_file: str,
    style: str = "notion",
    layout: str = "balanced",
    ref_image: Optional[str] = None,
    fallback: bool = True
) -> bool:
    """
    Generate an image using Google Gemini API.
    
    Args:
        prompt: Content description for the image
        output_file: Path to save the generated image
        style: Visual style (cute, fresh, warm, bold, minimal, retro, pop, notion, chalkboard, study-notes)
        layout: Information layout (sparse, balanced, dense, list, comparison, flow, mindmap, quadrant)
        ref_image: Optional path to reference image for visual consistency
        fallback: Whether to fallback to gemini-2.5-flash-image if gemini-3-pro fails
    
    Returns:
        True if successful, False otherwise
    """
    
    # Get API key
    api_key = get_api_key()
    
    # Build complete prompt
    full_prompt = build_prompt(prompt, style, layout, ref_image)
    
    print(f"Generating image with style: {style}, layout: {layout}")
    if ref_image:
        print(f"Using reference image: {ref_image}")
    
    # Save prompt for debugging (optional)
    prompt_debug_file = f"{output_file}.prompt.txt"
    with open(prompt_debug_file, "w", encoding="utf-8") as f:
        f.write(full_prompt)
    print(f"Prompt saved to: {prompt_debug_file}")
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Try primary model first (Gemini 3 Pro Image Preview)
        image_data = generate_with_model(client, full_prompt, "gemini-3-pro-image-preview")
        
        # If primary model fails and fallback is enabled, try secondary model
        if not image_data and fallback:
            print("Primary model failed, trying fallback model: gemini-2.5-flash-image")
            image_data = generate_with_model(client, full_prompt, "gemini-2.5-flash-image")
        
        if not image_data:
            print("All models failed to generate image")
            return False
        
        # Save image
        image = Image.open(io.BytesIO(image_data))
        image.save(output_file)
        
        # Get image info
        file_size = os.path.getsize(output_file) / 1024  # KB
        width, height = image.size
        
        print(f"✓ Image saved to: {output_file}")
        print(f"  Size: {width}x{height}, File size: {file_size:.1f}KB")
        
        return True
        
    except Exception as e:
        print(f"Error generating image: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate Xiaohongshu infographic images using Google Gemini API")
    
    parser.add_argument("--prompt", type=str, required=True, help="Content description for the image")
    parser.add_argument("--output", type=str, required=True, help="Output image file path")
    parser.add_argument("--style", type=str, default="notion", 
                       choices=["cute", "fresh", "warm", "bold", "minimal", "retro", "pop", "notion", "chalkboard", "study-notes"],
                       help="Visual style for the infographic")
    parser.add_argument("--layout", type=str, default="balanced",
                       choices=["sparse", "balanced", "dense", "list", "comparison", "flow", "mindmap", "quadrant"],
                       help="Information layout for the infographic")
    parser.add_argument("--ref", type=str, help="Path to reference image for visual consistency")
    parser.add_argument("--no-fallback", action="store_true", 
                       help="Disable fallback to gemini-2.5-flash-image")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate image
    success = generate_image(
        prompt=args.prompt,
        output_file=args.output,
        style=args.style,
        layout=args.layout,
        ref_image=args.ref,
        fallback=not args.no_fallback
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()