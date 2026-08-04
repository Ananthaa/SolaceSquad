"""
Google Health Plugin — Self-registration
Imported automatically by fitness_plugins/__init__.py autodiscover().
"""
from fitness_plugins.registry import PluginRegistry
from .plugin import GoogleHealthPlugin

PluginRegistry.register(GoogleHealthPlugin())
