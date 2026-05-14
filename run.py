"""
Web3 Hunter Bot — Entry Point
Run this file to start the bot: python run.py
"""
import sys
import os

# Make sure all imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main_bot import main

if __name__ == "__main__":
    main()
