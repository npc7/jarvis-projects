# Baoyu Xiaohongshu Images Skill (Gemini API Version)

This is a modified version of the original `baoyu-xhs-images` skill that uses Google Gemini API for image generation instead of the original image generation service.

## Features

- **Google Gemini API Integration**: Uses the latest Gemini models for high-quality image generation
- **Model Fallback**: Automatically falls back from `gemini-3-pro-image-preview` to `gemini-2.5-flash-image` if the primary model is unavailable
- **Style Presets**: 10 visual styles (cute, fresh, warm, bold, minimal, retro, pop, notion, chalkboard, study-notes)
- **Layout Options**: 8 information layouts (sparse, balanced, dense, list, comparison, flow, mindmap, quadrant)
- **Visual Consistency**: Supports reference image chaining for consistent character/style across a series
- **Environment Configuration**: API key managed via `.env` file

## Installation

1. **Clone or download** this skill to your OpenClaw skills directory:
   ```bash
   cd /path/to/openclaw/skills
   git clone https://github.com/your-repo/baoyu-xhs-images-gemini.git
   ```

2. **Install Python dependencies**:
   ```bash
   pip install google-genai Pillow python-dotenv
   ```

3. **Configure API key**:
   ```bash
   cd baoyu-xhs-images-gemini
   cp .env.example .env
   # Edit .env and add your Gemini API key
   ```

4. **Set environment variable** (optional):
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

### Basic Usage
```bash
# Generate an image with default settings (notion style, balanced layout)
python3 scripts/generate_image.py \
  --prompt "Your content description here" \
  --output "output.png"

# Specify style and layout
python3 scripts/generate_image.py \
  --prompt "小红书风格信息图：如何选择面霜" \
  --output "skincare-infographic.png" \
  --style cute \
  --layout list

# Use reference image for visual consistency
python3 scripts/generate_image.py \
  --prompt "Second page of the skincare series" \
  --output "page2.png" \
  --ref "page1.png" \
  --style cute \
  --layout balanced
```

### Within OpenClaw
This skill integrates with OpenClaw's skill system. Use the `/baoyu-xhs-images` command as described in `SKILL.md`.

## Configuration

### Environment Variables
- `GEMINI_API_KEY`: Your Google Gemini API key (required)
- `PRIMARY_MODEL`: Primary model to use (default: `gemini-3-pro-image-preview`)
- `FALLBACK_MODEL`: Fallback model (default: `gemini-2.5-flash-image`)

### Style Presets
Each style has predefined color palettes and visual elements:

| Style | Description | Best For |
|-------|-------------|----------|
| `cute` | Sweet, adorable, girly | Beauty, fashion, lifestyle |
| `fresh` | Clean, refreshing, natural | Health, wellness, nature |
| `warm` | Cozy, friendly, approachable | Personal stories, reviews |
| `bold` | High impact, attention-grabbing | Important announcements, warnings |
| `minimal` | Ultra-clean, sophisticated | Professional content, business |
| `retro` | Vintage, nostalgic, trendy | Classic products, throwbacks |
| `pop` | Vibrant, energetic, eye-catching | Fun content, entertainment |
| `notion` | Minimalist hand-drawn line art | Knowledge, productivity, SaaS |
| `chalkboard` | Colorful chalk on black board | Education, tutorials, teaching |
| `study-notes` | Realistic handwritten photo style | Study guides, notes, knowledge sharing |

### Layout Options
| Layout | Description | Best For |
|--------|-------------|----------|
| `sparse` | Minimal information, maximum impact | Covers, hero images |
| `balanced` | Standard content layout | Most content pages |
| `dense` | High information density | Knowledge cards, cheat sheets |
| `list` | Enumeration and ranking | Product lists, checklists |
| `comparison` | Side-by-side contrast | Product comparisons, pros/cons |
| `flow` | Process and timeline | Tutorials, how-to guides |
| `mindmap` | Center radial mind map | Brainstorming, concept mapping |
| `quadrant` | Four-quadrant / circular section | Analysis, categorization |

## Workflow

The skill follows a structured workflow for creating Xiaohongshu infographic series:

1. **Content Analysis**: Analyze source content and determine optimal strategy
2. **Strategy Selection**: Choose from Story-Driven, Information-Dense, or Visual-First approaches
3. **Outline Generation**: Create detailed outline with style and layout recommendations
4. **Image Generation**: Generate images sequentially with visual consistency
5. **Completion**: Provide final report with all generated files

## Troubleshooting

### Common Issues

1. **API Key Not Set**:
   ```
   Error: GEMINI_API_KEY environment variable not set.
   ```
   **Solution**: Set the `GEMINI_API_KEY` in your `.env` file or environment variables.

2. **Model Unavailable**:
   ```
   Error: 503 UNAVAILABLE. This model is currently experiencing high demand.
   ```
   **Solution**: The script automatically falls back to `gemini-2.5-flash-image`. Wait a few minutes and try again.

3. **Image Generation Failure**:
   ```
   No image data found in response.
   ```
   **Solution**: Check your prompt length and content. Gemini may refuse to generate images for certain content.

4. **Dependencies Missing**:
   ```
   ModuleNotFoundError: No module named 'google.genai'
   ```
   **Solution**: Install required packages: `pip install google-genai Pillow python-dotenv`

### Debug Mode
Enable debug output by setting environment variable:
```bash
export DEBUG=1
python3 scripts/generate_image.py --prompt "test" --output test.png
```

## Performance Notes

- **Generation Time**: 15-120 seconds per image depending on complexity
- **Rate Limits**: Google Gemini API has usage quotas. Check Google AI Studio for details.
- **Cost**: Gemini API pricing applies. Refer to Google's pricing page.

## References

- [Google Gemini API Documentation](https://ai.google.dev/gemini-api/docs/image-generation?hl=zh-cn)
- [Original Baoyu XHS Images Skill](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-xhs-images)
- [OpenClaw Skills Documentation](https://docs.openclaw.ai/skills/)

## License

This skill is based on the original `baoyu-xhs-images` skill. See the original repository for license information.

## Contributing

Feel free to submit issues and pull requests for improvements and bug fixes.