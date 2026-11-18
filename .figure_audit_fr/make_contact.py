from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


root = Path(__file__).parent
files = sorted(path for path in root.glob("*.png") if not path.name.startswith("contact_"))
font = ImageFont.load_default()

for sheet_index, start in enumerate(range(0, len(files), 6), 1):
    canvases = []
    for path in files[start : start + 6]:
        image = Image.open(path).convert("RGB")
        image.thumbnail((700, 400))
        canvas = Image.new("RGB", (720, 440), "white")
        canvas.paste(image, ((720 - image.width) // 2, 25))
        ImageDraw.Draw(canvas).text((10, 5), path.stem, fill="black", font=font)
        canvases.append(canvas)

    sheet = Image.new("RGB", (1440, 1320), "white")
    for index, canvas in enumerate(canvases):
        sheet.paste(canvas, ((index % 2) * 720, (index // 2) * 440))
    sheet.save(root / f"contact_{sheet_index}.png")
