"""Short-lived deterministic QR decoder; never print payloads."""
import json
import sys
from PIL import Image
import zxingcpp


def decode(path):
    with Image.open(path) as image:
        results=zxingcpp.read_barcodes(image,formats=zxingcpp.BarcodeFormat.QRCode,try_rotate=True,try_downscale=True,try_invert=True)
    return [{'format':'QR_CODE','payload':r.text,'payload_bytes_hex':r.bytes.hex(),
             'position':[[getattr(r.position,p).x,getattr(r.position,p).y] for p in ('top_left','top_right','bottom_right','bottom_left')]} for r in results]


if __name__=='__main__':
    try: output={'codes':decode(sys.argv[1])}
    except Exception as exc: output={'codes':[],'error':type(exc).__name__}
    with open(sys.argv[2],'w') as file: json.dump(output,file,ensure_ascii=False)
