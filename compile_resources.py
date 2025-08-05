#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compile resources file
"""

import subprocess
import sys
import os

def compile_resources():
    """Compile resources.qrc to resources.py"""
    try:
        # Try to use pyrcc5
        subprocess.call(['pyrcc5', '-o', 'resources.py', 'resources.qrc'])
        print("Resources compiled successfully with pyrcc5")
    except:
        try:
            # Try to use pyside2-rcc as fallback
            subprocess.call(['pyside2-rcc', '-o', 'resources.py', 'resources.qrc'])
            print("Resources compiled successfully with pyside2-rcc")
        except:
            print("Failed to compile resources. Please install PyQt5 development tools.")
            sys.exit(1)

if __name__ == "__main__":
    compile_resources()