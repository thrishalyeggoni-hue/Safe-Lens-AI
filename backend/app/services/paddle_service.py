import asyncio
import importlib.util
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import sys
import tempfile
from ..config import settings
from .paddle_worker import PROFILES, DETECTOR

# OCR is serialized and loaded only inside a killable child process.
OCR_LOCK = asyncio.Lock()


def capability():
    root = Path(settings.SCREENSHOT_OCR_MODEL_ROOT)
    def installed(name):
        try: return version(name)
        except PackageNotFoundError: return None
    def ready(model):
        path = root / model
        return (path / 'inference.json').is_file() and (path / 'inference.pdiparams').is_file()
    langs = {lang: {'model': model, 'available': ready(model), 'accuracy_verified': False} for lang, model in PROFILES.items()}
    return {'engine': 'PaddleOCR', 'package_version': installed('paddleocr'), 'runtime_version': installed('paddlepaddle'),
            'detector': DETECTOR, 'detector_available': ready(DETECTOR), 'languages': langs,
            'device': 'CPU', 'threads': 1, 'automatic_downloads': False,
            'setup_command': '.venv/bin/python scripts/setup_screenshot_ocr.py',
            'language_limitation': 'Choose the screenshot language. Mixed uses English, Hindi and Telugu recognizers; confidence is not comparable accuracy across languages. No comprehensive multilingual guarantee.'}


async def run_paddle(image, language, on_stage=None):
    info = capability()
    selected = list(PROFILES) if language == 'mixed' else [language]
    base = {**info, 'status': 'unavailable', 'selected_language': language, 'regions': [], 'runs': []}
    if not info['package_version'] or not info['runtime_version']:
        return {**base, 'error': 'PaddleOCR or PaddlePaddle inference runtime is not installed'}
    if not info['detector_available'] or not all(info['languages'][lang]['available'] for lang in selected):
        return {**base, 'error': 'Required OCR models are unavailable. Run the reported setup command; uploads do not trigger downloads.'}
    async with OCR_LOCK:
        with tempfile.TemporaryDirectory(prefix='safelens-ocr-') as folder:
            image_path = Path(folder) / 'image.png'
            image.save(image_path)
            for lang in selected:
                if on_stage: on_stage(f'Running real PaddleOCR · {lang} · CPU, one thread')
                output = Path(folder) / f'{lang}.json'
                env = {**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True'}
                process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'backend.app.services.paddle_worker', '--language', lang,
                    '--model-root', settings.SCREENSHOT_OCR_MODEL_ROOT, '--input', str(image_path), '--output', str(output),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, env=env,
                    cwd=str(Path(__file__).resolve().parents[3]))
                try:
                    await asyncio.wait_for(process.wait(), settings.SCREENSHOT_OCR_TIMEOUT)
                    if not output.exists() or output.stat().st_size > 2 * 1024 * 1024:
                        run = {'error': 'OCR worker did not produce a bounded result', 'regions': []}
                    else:
                        run = json.loads(output.read_text())
                        if not isinstance(run, dict) or not isinstance(run.get('regions'), list):
                            raise ValueError('Invalid worker shape')
                except TimeoutError:
                    run = {'error': 'OCR processing timed out', 'regions': []}
                except (OSError, ValueError, KeyError, TypeError):
                    run = {'error': 'OCR worker returned an invalid result', 'regions': []}
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                base['runs'].append({'language': lang, **run})
                base['regions'].extend(run['regions'])
            failed = [run for run in base['runs'] if run.get('error')]
            base['status'] = 'unavailable' if len(failed) == len(selected) else 'partial' if failed else 'completed'
            if failed: base['error'] = '; '.join(run['error'] for run in failed)
            return base
