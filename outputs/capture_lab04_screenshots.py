import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path.cwd()
CHROME = Path.home() / 'AppData/Local/Google/Chrome/Application/chrome.exe'
SOURCE = ROOT / 'outputs/lab04/evidence'
OUTPUT = ROOT / 'submissions/lab04/evidence/截图'
OUTPUT.mkdir(parents=True, exist_ok=True)

JOBS = [
    ('058ed7a3d4054d00960b2ea661ceaf2a-start.html', '01-start-identity.png'),
    ('91b7e89eedff45ee981613572867b55f-verify.html', '02-main-replay.png'),
    ('5287cd662cb14aa99c7e4c0bd8aa72d9-inspect_state.html', '03-database-inspection.png'),
    ('dadd21b276d8450d800edef1d45d0783-check_student_transaction.html', '04-student-transaction-pass.png'),
    ('75038dfbc68f4ad1b6e497e422d49f45-final.html', '05-final-identity.png'),
]

for html_name, image_name in JOBS:
    html = SOURCE / html_name
    raw_out = OUTPUT / ('raw-' + image_name)
    with tempfile.TemporaryDirectory(prefix='bdp-chrome-') as profile:
        command = [
            str(CHROME), '--headless=new', '--disable-gpu', '--hide-scrollbars',
            '--force-device-scale-factor=1', '--window-size=1200,4000',
            f'--user-data-dir={profile}', f'--screenshot={raw_out}', html.as_uri(),
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if result.returncode != 0 or not raw_out.is_file():
        raise SystemExit(f'screenshot failed: {image_name}')
    image = Image.open(raw_out).convert('RGB')
    width, height = image.size
    background = image.getpixel((width - 10, height - 10))
    difference = ImageChops.difference(image, Image.new('RGB', image.size, background))
    bbox = difference.convert('L').point(lambda value: 255 if value > 4 else 0).getbbox()
    if bbox is None:
        raise SystemExit(f'empty screenshot: {image_name}')
    bottom = min(height, bbox[3] + 24)
    image.crop((0, 0, width, bottom)).save(OUTPUT / image_name)
    raw_out.unlink()
    print(image_name, (width, bottom))
