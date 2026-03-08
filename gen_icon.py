from PIL import Image, ImageDraw

def create_app_icon(filename="icon.ico", size=256):
    # Transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # We use a 4x supersampled image for anti-aliasing
    super_size = size * 4
    super_img = Image.new("RGBA", (super_size, super_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(super_img)
    
    cx, cy = super_size // 2, super_size // 2
    r = int(super_size * 0.42)
    
    # Matches _BG = #1e1e2e, _ACCENT = #89b4fa, _FG = #cdd6f4
    bg_color = (30, 30, 46, 255)
    accent_color = (137, 180, 250, 255)
    fg_color = (205, 214, 244, 255)
    
    # Outer ring
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color, outline=accent_color, width=int(super_size * 0.05))
    
    # Minute hand
    draw.line([cx, cy, cx, cy - int(r*0.6)], fill=fg_color, width=int(super_size * 0.05))
    # Hour hand
    draw.line([cx, cy, cx + int(r*0.35), cy + int(r*0.35)], fill=fg_color, width=int(super_size * 0.06))
    
    # Center dot
    dot_r = int(super_size * 0.06)
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=accent_color)
    
    # Downsample for anti-aliasing
    img = super_img.resize((size, size), resample=Image.Resampling.LANCZOS)
    
    # Save as ICO
    img.save(filename, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

if __name__ == "__main__":
    create_app_icon("icon.ico")
