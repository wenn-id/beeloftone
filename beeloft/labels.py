from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from qrcode.image.svg import SvgPathImage


def bundle_scan_code(bundle_id):
    return f'BEELOFT:BUNDLE:{bundle_id}'


def bundle_label_svg(bundle):
    code=bundle_scan_code(bundle['id'])
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
    qr.add_data(code);qr.make(fit=True)
    output=BytesIO();qr.make_image(image_factory=SvgPathImage).save(output)
    svg=output.getvalue().decode('utf-8')
    svg=svg.replace('<svg ','<svg role="img" aria-labelledby="bundle-qr-title bundle-qr-desc" ',1)
    start=svg.index('>',svg.index('<svg'))+1
    title=escape(f"QR bundle {bundle['reference']}")
    description=escape(code)
    return svg[:start]+f'<title id="bundle-qr-title">{title}</title>' \
        f'<desc id="bundle-qr-desc">{description}</desc>'+svg[start:]
