"""Document generation services: PDF generation with WeasyPrint/HTML fallback and QR codes."""
import base64

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from apps.documents.models import Document
from apps.vouchers.models import Voucher


def generate_voucher_pdf(voucher: Voucher, requesting_user=None) -> Document:
    """
    Generates the official Voucher Dispatch PDF (Vale de Salida)
    and saves it to voucher.pdf_file and the Document repository.
    """
    voucher.refresh_from_db()
    lines = voucher.lines.select_related("equipment_model").all()
    items = voucher.items.select_related("equipment_model").all()

    context = {
        "voucher": voucher,
        "lines": lines,
        "items": items,
        "generated_at": timezone.now(),
        "app_name": getattr(settings, "APP_NAME", "Admón Almacén SSIT 2.0"),
    }

    html_string = render_to_string("documents/voucher_pdf.html", context)
    pdf_filename = f"vale_{voucher.id}_{timezone.now():%Y%m%d%H%M%S}.pdf"

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()
    except Exception:
        # Fallback para desarrollo sin librerías nativas de WeasyPrint en host
        pdf_bytes = html_string.encode("utf-8")
        pdf_filename = f"vale_{voucher.id}_{timezone.now():%Y%m%d%H%M%S}.html"

    file_content = ContentFile(pdf_bytes, name=pdf_filename)
    voucher.pdf_file.save(pdf_filename, file_content, save=False)
    Voucher.objects.filter(pk=voucher.pk).update(pdf_file=voucher.pdf_file.name)

    # Registrar en el repositorio Document
    doc = Document.objects.create(
        kind=Document.Kind.VALE_PDF,
        related_type="Voucher",
        related_id=voucher.id,
        file=voucher.pdf_file,
        created_by=requesting_user or voucher.delivered_by or voucher.requested_by,
    )
    return doc


def generate_return_pdf(case, requesting_user=None) -> Document:
    """
    Generates the official Return Confirmation PDF (Formato de Devolución / Envío)
    with embedded QR code and saves it to case.return_pdf and the Document repository.
    """
    case.refresh_from_db()

    # Generate QR Code for return tracking
    import io
    import qrcode

    qr_img_data = None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6,
            border=2,
        )
        qr_data = f"CASO-DEV:{case.id}|SN:{case.returned_serial}|ORIGEN:{case.origin_region.code if case.origin_region else ''}|FOLIO:{case.shipping_folio}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_bytes = buffer.getvalue()
        qr_filename = f"qr_case_{case.id}_{timezone.now():%Y%m%d%H%M%S}.png"
        case.return_qr.save(qr_filename, ContentFile(qr_bytes), save=False)
        qr_img_data = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode('utf-8')}"
    except Exception:
        pass

    context = {
        "case": case,
        "qr_base64": qr_img_data,
        "generated_at": timezone.now(),
        "app_name": getattr(settings, "APP_NAME", "Admón Almacén SSIT 2.0"),
    }

    html_string = render_to_string("documents/return_pdf.html", context)
    pdf_filename = f"devolucion_{case.id}_{timezone.now():%Y%m%d%H%M%S}.pdf"

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_string, base_url=str(settings.BASE_DIR)).write_pdf()
    except Exception:
        pdf_bytes = html_string.encode("utf-8")
        pdf_filename = f"devolucion_{case.id}_{timezone.now():%Y%m%d%H%M%S}.html"

    file_content = ContentFile(pdf_bytes, name=pdf_filename)
    case.return_pdf.save(pdf_filename, file_content, save=False)
    from apps.cases.models import EquipmentCase
    EquipmentCase.objects.filter(pk=case.pk).update(
        return_pdf=case.return_pdf.name,
        return_qr=case.return_qr.name if case.return_qr else None,
    )

    doc = Document.objects.create(
        kind=Document.Kind.REGRESO_PDF,
        related_type="EquipmentCase",
        related_id=case.id,
        file=case.return_pdf,
        created_by=requesting_user or case.received_by,
    )
    return doc


def save_base64_signature(data_url: str, voucher: Voucher) -> str | None:
    """Decodes a base64 signature from signature_pad and saves it to voucher.signature_image."""
    if not data_url or "base64," not in data_url:
        return None

    try:
        format_part, img_str = data_url.split(";base64,")
        ext = format_part.split("/")[-1] or "png"
        data = base64.b64decode(img_str)
        filename = f"sig_voucher_{voucher.id}_{timezone.now():%Y%m%d%H%M%S}.{ext}"
        voucher.signature_image.save(filename, ContentFile(data), save=False)
        Voucher.objects.filter(pk=voucher.pk).update(signature_image=voucher.signature_image.name)
        return voucher.signature_image.url
    except Exception:
        return None

