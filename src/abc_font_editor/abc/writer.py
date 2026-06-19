"""Writing the in-memory ABC data back to disk."""
from PyQt6.QtWidgets import QFileDialog


class WriterMixin:
    """Saving the ABC file for :class:`ABCFontEditor`."""

    def save_abc(self):
        if not self.original_data:
            self.show_warning("No Data", "Load an .abc file first.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save ABC", self.abc_path or "", "ABC Files (*.abc)")
        if not save_path:
            return

        try:
            with open(save_path, "wb") as f:
                f.write(self.original_data)
        except Exception as e:
            self.show_error("Error", f"Failed to write ABC file:\n{str(e)}")
            return

        self.abc_path = save_path
        self.dirty = False
        self.show_info("Saved", f"Saved to:\n{save_path}")
