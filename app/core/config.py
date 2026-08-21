import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
_MAX_HISTORY_TURNS = 20

ENCODINGS = ["utf-8-sig", "utf-8", "iso-8859-9", "windows-1254", "latin1", "cp1252"]
DELIMITERS = [",", ";", "\t", "|"]
