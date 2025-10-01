import json
import os

class PresetManager:
    PRESETS_FILE = 'presets.json'

    def __init__(self):
        self.presets = {}
        self.load_presets()

    def load_presets(self):
        if os.path.exists(self.PRESETS_FILE):
            with open(self.PRESETS_FILE, 'r', encoding='utf-8') as f:
                self.presets = json.load(f)
        else:
            self.presets = {}

    def save_presets(self):
        with open(self.PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.presets, f, indent=4)

    def get_presets(self):
        return self.presets

    def get_preset(self, name):
        return self.presets.get(name, {})

    def save_preset(self, name, settings):
        if not name:
            return False, "Preset name cannot be empty."
        self.presets[name] = settings
        self.save_presets()
        return True, f"Preset '{name}' saved."

    def delete_preset(self, name):
        if name in self.presets:
            del self.presets[name]
            self.save_presets()
            return True, f"Preset '{name}' deleted."
        return False, f"Preset '{name}' not found."