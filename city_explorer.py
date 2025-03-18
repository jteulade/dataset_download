#!/usr/bin/env python3
"""
Main entry point for the Sentinel City Explorer application.
This script provides easy access to the functionality organized in the src package.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core functionality
from src.sentinel_city_explorer import main

if __name__ == "__main__":
    main() 