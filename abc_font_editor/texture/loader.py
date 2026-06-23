"""Loading textures from disk and applying manual texture resolution."""
from PyQt6.QtWidgets import QFileDialog
from PIL import Image

from .image_utils import pil_to_qpixmap


class TextureMixin:
    """Texture loading / resolution handling for :class:`ABCFontEditor`."""

    def load_texture(self):
        filter_str = (
            "Images with Alpha Channel (*.dds *.DDS *.png *.PNG *.tga *.TGA);;"
            "Images without Alpha Channel (*.jpg *.JPG *.jpeg *.JPEG *.bmp *.BMP);;"
            "All Files (*)"
        )

        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Texture",
            "",
            filter_str,
            "Images with Alpha Channel (*.dds *.DDS *.png *.PNG *.tga *.TGA)"
        )

        if not path:
            return

        self.texture_path = path

        try:
            image = Image.open(path)
        except Exception as e:
            self.show_error(
                "Texture Error",
                f"Failed to load texture:\n{e}"
            )
            return

        self.texture_size = image.size

        # Update texture resolution inputs with actual image size
        self.texture_width_input.setText(str(image.size[0]))
        self.texture_height_input.setText(str(image.size[1]))

        self.pixmap = pil_to_qpixmap(image)
        self.update_glyph_count_label()
        self.refresh_view()

    def apply_texture_resolution(self):
        """Apply manually entered texture resolution"""
        try:
            width = int(self.texture_width_input.text())
            height = int(self.texture_height_input.text())
            if width <= 0 or height <= 0:
                self.show_error("Error", "Texture resolution must be positive numbers.")
                return
            self.texture_size = (width, height)
            
            # Update pixel coordinates for existing glyphs
            if self.glyphs:
                for glyph in self.glyphs:
                    glyph["px_x_start"] = int(glyph["uv_x_start"] * width)
                    glyph["px_y_start"] = int(glyph["uv_y_start"] * height)
                    glyph["px_x_end"] = int(glyph["uv_x_end"] * width)
                    glyph["px_y_end"] = int(glyph["uv_y_end"] * height)
            
            self.refresh_view()
            self.show_info("Success", f"Texture resolution updated to {width}x{height}")
        except ValueError:
            self.show_error("Error", "Invalid texture resolution values.")
