from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from qrcode.image.svg import SvgPathImage


def bundle_scan_code(bundle_id):
    return f'BEELOFT:BUNDLE:{bundle_id}'


def material_batch_scan_code(batch_id):
    return f'BEELOFT:MATERIAL-BATCH:{batch_id}'


def finished_goods_scan_code(receipt_id):
    return f'BEELOFT:FINISHED-GOODS:{receipt_id}'


def _label_svg(code, title, element_prefix):
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
    qr.add_data(code);qr.make(fit=True)
    output=BytesIO();qr.make_image(image_factory=SvgPathImage).save(output)
    svg=output.getvalue().decode('utf-8')
    svg=svg.replace('<svg ',f'<svg role="img" aria-labelledby="{element_prefix}-title {element_prefix}-desc" ',1)
    start=svg.index('>',svg.index('<svg'))+1
    return svg[:start]+f'<title id="{element_prefix}-title">{escape(title)}</title>' \
        f'<desc id="{element_prefix}-desc">{escape(code)}</desc>'+svg[start:]


def bundle_label_svg(bundle):
    return _label_svg(bundle_scan_code(bundle['id']),f"QR bundle {bundle['reference']}",'bundle-qr')


def material_batch_label_svg(batch):
    return _label_svg(material_batch_scan_code(batch['id']),
                      f"QR batch bahan {batch['reference']}",'material-batch-qr')


def finished_goods_label_svg(receipt):
    return _label_svg(finished_goods_scan_code(receipt['id']),
                      f"QR barang jadi {receipt['reference']}",'finished-goods-qr')
