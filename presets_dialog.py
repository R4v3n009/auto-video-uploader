from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QMessageBox, 
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QFormLayout
)
from preset_manager import PresetManager

class PresetsDialog(QDialog):
    def __init__(self, manager: PresetManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Manage Editing Presets")
        self.setMinimumWidth(600)

        main_layout = QHBoxLayout(self)
        
        # Left side: List of presets
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Saved Presets:"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.load_preset_to_ui)
        left_panel.addWidget(self.list_widget)
        
        # Right side: Settings form
        right_panel = QVBoxLayout()
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.flip_combo = QComboBox()
        self.flip_combo.addItems(["None", "Horizontal", "Vertical"])
        self.zoom_spin = QDoubleSpinBox(); self.zoom_spin.setRange(1.0, 3.0); self.zoom_spin.setSingleStep(0.05); self.zoom_spin.setDecimals(2)
        self.rotate_spin = QDoubleSpinBox(); self.rotate_spin.setRange(-45.0, 45.0); self.rotate_spin.setSingleStep(0.5); self.rotate_spin.setDecimals(1)
        self.overlay_spin = QDoubleSpinBox(); self.overlay_spin.setRange(0.0, 1.0); self.overlay_spin.setSingleStep(0.01); self.overlay_spin.setDecimals(2)
        
        form_layout.addRow("Preset Name:", self.name_edit)
        form_layout.addRow("Flip Video:", self.flip_combo)
        form_layout.addRow("Zoom Factor:", self.zoom_spin)
        form_layout.addRow("Rotation Angle:", self.rotate_spin)
        form_layout.addRow("Overlay Opacity:", self.overlay_spin)
        
        right_panel.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        new_btn = QPushButton("New"); save_btn = QPushButton("Save"); delete_btn = QPushButton("Delete")
        button_layout.addWidget(new_btn); button_layout.addWidget(save_btn); button_layout.addWidget(delete_btn)
        
        new_btn.clicked.connect(self.clear_form)
        save_btn.clicked.connect(self.save_preset)
        delete_btn.clicked.connect(self.delete_preset)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)
        left_panel.addLayout(button_layout)

        self.populate_list()
        self.clear_form()

    def populate_list(self):
        self.list_widget.clear()
        for name in self.manager.get_presets().keys():
            self.list_widget.addItem(name)
            
    def load_preset_to_ui(self, current, previous):
        if not current: return
        name = current.text()
        settings = self.manager.get_preset(name)
        if not settings: return
        
        self.name_edit.setText(name)
        self.flip_combo.setCurrentText(settings.get("flip_mode", "None"))
        self.zoom_spin.setValue(settings.get("zoom_factor", 1.0))
        self.rotate_spin.setValue(settings.get("rotation_angle", 0.0))
        self.overlay_spin.setValue(settings.get("overlay_opacity", 0.0))

    def save_preset(self):
        name = self.name_edit.text()
        settings = {
            "flip_mode": self.flip_combo.currentText(),
            "zoom_factor": self.zoom_spin.value(),
            "rotation_angle": self.rotate_spin.value(),
            "overlay_opacity": self.overlay_spin.value(),
        }
        success, message = self.manager.save_preset(name, settings)
        if success:
            QMessageBox.information(self, "Success", message)
            self.populate_list()
        else:
            QMessageBox.warning(self, "Error", message)

    def delete_preset(self):
        selected = self.list_widget.currentItem()
        if not selected: return QMessageBox.warning(self, "Warning", "Please select a preset to delete.")
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{selected.text()}'?")
        if reply == QMessageBox.Yes:
            self.manager.delete_preset(selected.text())
            self.populate_list()
            self.clear_form()
    
    def clear_form(self):
        self.list_widget.setCurrentItem(None)
        self.name_edit.clear()
        self.flip_combo.setCurrentIndex(0)
        self.zoom_spin.setValue(1.0)
        self.rotate_spin.setValue(0.0)
        self.overlay_spin.setValue(0.0)