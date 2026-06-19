"""The main editor window, assembled from the functional mixins."""
from PyQt6.QtWidgets import (
    QCheckBox, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtCore import Qt

from .dialogs import DialogsMixin
from .abc.glyph import CodepointMixin
from .abc.parser import ParserMixin
from .abc.writer import WriterMixin
from .abc.editing import EditingMixin
from .io.json_io import JsonMixin
from .texture.loader import TextureMixin
from .graphics.renderer import RendererMixin
from .graphics.view import ViewMixin


class ABCFontEditor(
    DialogsMixin,
    CodepointMixin,
    ParserMixin,
    WriterMixin,
    EditingMixin,
    JsonMixin,
    TextureMixin,
    RendererMixin,
    ViewMixin,
    QWidget,
):
    ZOOM_STEP_PERCENT = 5
    ZOOM_MIN_PERCENT = 5
    ZOOM_MAX_PERCENT = 300

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABC Font Editor")
        self.abc_path = None
        self.texture_path = None
        self.texture_size = (2048, 1024)
        self.offset_dec = 0
        self.zoom = 1.0
        self.glyphs = []
        self.original_data = b""
        self.dirty = False
        self.manual_offset = False  # Track if offset was set manually
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #202020; color: white;")
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()

        self.glyph_count_label = QLabel("Glyphs: 0")
        self.glyph_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph_count_label.setStyleSheet("color: white;")
        
        # Texture resolution input (moved before glyph count)
        top_row.addWidget(QLabel("Texture:"))
        self.texture_width_input = QLineEdit(str(self.texture_size[0]))
        self.texture_height_input = QLineEdit(str(self.texture_size[1]))
        self.texture_width_input.setFixedWidth(50)
        self.texture_height_input.setFixedWidth(50)
        self.texture_width_input.setStyleSheet("background-color: #333; color: white;")
        self.texture_height_input.setStyleSheet("background-color: #333; color: white;")
        self.texture_width_input.setPlaceholderText("width")
        self.texture_height_input.setPlaceholderText("height")
        top_row.addWidget(self.texture_width_input)
        top_row.addWidget(QLabel("x"))
        top_row.addWidget(self.texture_height_input)
        
        # Apply texture resolution button
        self.apply_texture_btn = QPushButton("Apply")
        self.apply_texture_btn.setFixedWidth(60)
        self.apply_texture_btn.clicked.connect(self.apply_texture_resolution)
        top_row.addWidget(self.apply_texture_btn)
        
        # Add spacing after texture controls
        top_row.addSpacing(30)
        
        top_row.addWidget(self.glyph_count_label)
        
        # Add spacing after glyph count
        top_row.addSpacing(30)

        for btn in [self.apply_texture_btn]:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; } QPushButton:disabled { background-color: #2a2a2a; color: #666666; }")

        top_row.addStretch()

        # Zoom controls
        top_row.addWidget(QLabel("Zoom:"))
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedWidth(25)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        top_row.addWidget(self.zoom_out_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(30)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet("background-color: #202020; color: white;")
        top_row.addWidget(self.zoom_label)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(25)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        top_row.addWidget(self.zoom_in_btn)

        self.fit_view_btn = QPushButton("Fit")
        self.fit_view_btn.setFixedWidth(40)
        self.fit_view_btn.setToolTip("Fit entire texture in the view (all glyphs are on the atlas)")
        self.fit_view_btn.clicked.connect(self.fit_texture_view)
        top_row.addWidget(self.fit_view_btn)
        
        for btn in [self.zoom_out_btn, self.zoom_in_btn, self.fit_view_btn]:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; } QPushButton:disabled { background-color: #2a2a2a; color: #666666; }")

        # Smooth Texture
        self.smooth_texture_cb = QCheckBox("Smooth Texture")
        self.smooth_texture_cb.setChecked(True)
        self.smooth_texture_cb.toggled.connect(self.toggle_smooth_texture)
        
        top_row.addSpacing(30)
        
        top_row.addWidget(self.smooth_texture_cb)

        layout.addLayout(top_row)

        # Canvas
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor(60, 60, 60))
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.view.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.view.viewport().setStyleSheet("background-color: #3c3c3c;")
        self.view.mousePressEvent = self.handle_view_click
        layout.addWidget(self.view, stretch=1)

        # Buttons
        bottom_row = QHBoxLayout()
        self.load_texture_btn = QPushButton("Load Texture")
        self.load_abc_btn = QPushButton("Load .abc")
        self.charmap_table_btn = QPushButton("Charmap")
        self.global_params_btn = QPushButton("Global Params")
        self.export_json_btn = QPushButton("Export to JSON")
        self.import_json_btn = QPushButton("Import from JSON")
        self.delete_symbols_btn = QPushButton("Delete Symbols")
        self.add_symbol_btn = QPushButton("Add Symbol")
        self.save_abc_btn = QPushButton("Save .abc")
        for btn in [
            self.load_texture_btn, self.load_abc_btn, self.charmap_table_btn,
            self.global_params_btn, self.export_json_btn, self.import_json_btn,
            self.delete_symbols_btn, self.add_symbol_btn, self.save_abc_btn,
        ]:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; } QPushButton:disabled { background-color: #2a2a2a; color: #666666; }")
        self.charmap_table_btn.setEnabled(False)
        self.global_params_btn.setEnabled(False)
        self.export_json_btn.setEnabled(False)
        self.import_json_btn.setEnabled(False)
        self.delete_symbols_btn.setEnabled(False)
        self.add_symbol_btn.setEnabled(False)
        self.save_abc_btn.setEnabled(False)

        bottom_row.addWidget(self.load_texture_btn)
        bottom_row.addWidget(self.load_abc_btn)
        bottom_row.addWidget(self.charmap_table_btn)
        bottom_row.addWidget(self.global_params_btn)
        bottom_row.addWidget(self.export_json_btn)
        bottom_row.addWidget(self.import_json_btn)
        bottom_row.addWidget(self.delete_symbols_btn)
        bottom_row.addWidget(self.add_symbol_btn)
        bottom_row.addWidget(self.save_abc_btn)
        layout.addLayout(bottom_row)

        self.load_texture_btn.clicked.connect(self.load_texture)
        self.load_abc_btn.clicked.connect(self.load_abc)
        self.charmap_table_btn.clicked.connect(self.show_charmap_table)
        self.export_json_btn.clicked.connect(self.export_json)
        self.import_json_btn.clicked.connect(self.import_json)
        self.delete_symbols_btn.clicked.connect(self.delete_symbols)
        self.add_symbol_btn.clicked.connect(self.add_symbol)
        self.global_params_btn.clicked.connect(self.edit_global_params)
        self.save_abc_btn.clicked.connect(self.save_abc)
