"""Helpers to convert PIL images into Qt pixmaps."""
from PyQt6.QtGui import QImage, QPixmap


def pil_to_qpixmap(image):
    """Convert a PIL image to a QPixmap via an RGBA QImage."""
    img = image.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)
