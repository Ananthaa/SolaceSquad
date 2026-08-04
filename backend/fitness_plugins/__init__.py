"""
Sync-X — Fitness Plugin Auto-Discovery
Scans fitness_plugins/ subpackages and registers each plugin automatically.
Adding a new provider = create a new subfolder. Nothing else changes.
"""
import importlib
import pkgutil
import os


def autodiscover():
    """Import every subpackage so each plugin self-registers via PluginRegistry."""
    package_dir = os.path.dirname(__file__)
    for _, name, is_pkg in pkgutil.iter_modules([package_dir]):
        if is_pkg:
            try:
                importlib.import_module(f"fitness_plugins.{name}")
                print(f"[Sync-X] Discovered plugin: {name}")
            except Exception as e:
                print(f"[Sync-X] Failed to load plugin '{name}': {e}")


autodiscover()
