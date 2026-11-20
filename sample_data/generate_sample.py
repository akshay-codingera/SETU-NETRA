"""
generate_sample.py: Generates synthetic test images for SETU-NETRA experimentation.

Why this file exists:
To test an image pipeline reliably, you need known inputs with known properties.
This script generates a clean multiple-choice question image using Pillow's ImageDraw.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def create_sample_question_image(output_path: Path) -> Path:
    """Generate a clean synthetic multiple-choice question image."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1200 x 800 pixel image with a soft light-gray background
    width, height = 1200, 800
    background_color = (250, 250, 252)
    card_color = (255, 255, 255)
    border_color = (210, 215, 225)
    text_color = (20, 25, 35)
    accent_color = (30, 90, 200)

    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)

    # Draw a card container with border
    margin = 40
    draw.rectangle(
        [(margin, margin), (width - margin, height - margin)],
        fill=card_color,
        outline=border_color,
        width=3,
    )

    # Header banner
    draw.rectangle(
        [(margin, margin), (width - margin, margin + 70)],
        fill=(240, 245, 255),
    )

    # Draw header text using default bitmap font (built-in, no external ttf required)
    # We will use large scaling or multi-stroke if TTF is not present
    title = "SETU-NETRA TEST BENCH: SAMPLE QUESTION"
    draw.text((margin + 20, margin + 25), title, fill=accent_color)

    # Question text lines
    lines = [
        "Q.1) What is the computational complexity of performing 2D convolution",
        "     on an image of size H x W with a kernel of size K x K?",
        "",
        "     [A]  O(H * W)",
        "     [B]  O(H * W * K^2)",
        "     [C]  O((H * W)^2)",
        "     [D]  O(K^4)",
        "",
        "Note: Assume stride 1 and standard direct spatial domain computation.",
    ]

    start_y = margin + 110
    line_height = 45

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        color = text_color
        if line.strip().startswith("["):
            color = (40, 60, 120)
        draw.text((margin + 30, y), line, fill=color)

    img.save(output_path, format="PNG")
    print(f"Generated sample question image at: {output_path.resolve()}")
    return output_path.resolve()


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "sample_question.png"
    create_sample_question_image(out)
