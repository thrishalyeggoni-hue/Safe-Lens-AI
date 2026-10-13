"""Explicit model provisioning; screenshot uploads never download models.
Official model links: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
"""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import settings
from backend.app.services.paddle_worker import PROFILES, DETECTOR


def main():
    target = Path(settings.SCREENSHOT_OCR_MODEL_ROOT)
    target.mkdir(parents=True, exist_ok=True)
    for model in [DETECTOR, *PROFILES.values()]:
        destination = target / model
        if (destination / 'inference.json').exists() and (destination / 'inference.pdiparams').exists():
            print(f'{model}: already provisioned', flush=True)
            continue
        url = f'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/{model}_infer.tar'
        print(f'Downloading official {model}', flush=True)
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024:
            raise ValueError('Model download exceeded limit')
        with tempfile.TemporaryDirectory(prefix='safelens-model-') as folder:
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                members = archive.getmembers()
                if sum(m.size for m in members) > 128 * 1024 * 1024 or len(members) > 100:
                    raise ValueError('Model archive exceeded limits')
                archive.extractall(folder, filter='data')
            configs = list(Path(folder).rglob('inference.json'))
            if len(configs) != 1 or not (configs[0].parent / 'inference.pdiparams').exists():
                raise ValueError('Model archive did not contain expected inference files')
            shutil.copytree(configs[0].parent, destination, dirs_exist_ok=True)
        (destination / 'safelens-model-source.json').write_text(json.dumps({'source': url, 'download_sha256': hashlib.sha256(data).hexdigest()}))
        print(f'{model}: ready', flush=True)


if __name__ == '__main__': main()
