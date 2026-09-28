import imageio
from PIL import Image

input_path = "/config/.gemini/antigravity/brain/12bbece7-ade6-40c0-b065-55824cd3037d/demo_video.webm"
output_path = "/config/.gemini/antigravity/scratch/travel-concierge/demo.gif"

print(f"Reading frames from {input_path}...")
reader = imageio.get_reader(input_path)
fps = reader.get_meta_data().get('fps', 10)

frames = []
# Sample 1 frame out of every 3 to keep GIF size optimized (< 15MB)
for i, frame in enumerate(reader):
    if i % 3 == 0:
        # Resize frame to width 640 for crisp rendering and smaller file size
        img = Image.fromarray(frame)
        img = img.resize((640, 360), Image.Resampling.LANCZOS)
        frames.append(img)

print(f"Saving {len(frames)} optimized frames to {output_path}...")
frames[0].save(
    output_path,
    save_all=True,
    append_images=frames[1:],
    duration=int(1000 / (fps / 3)),
    loop=0,
    optimize=True
)
print(f"Successfully created looping GIF: {output_path}")
