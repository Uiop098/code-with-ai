#!/usr/bin/env python3
"""
Code With AI — Full CLI Coding Experience for Termux / Any Python 3 Terminal
=============================================================================
A complete coding IDE in your terminal. Features:
  • AI chat with slash-command shortcuts  (/ai, /noai to toggle)
  • Code editor with syntax highlighting (via Pygments or built-in fallback)
  • Multi-file manager: open, create, delete, more actions per file
  • Run any file with its correct compiler/interpreter/runner
  • Full terminal passthrough (run any shell command; toggle AI analysis)
  • Hot-swap provider, model, and API key mid-session (ai-provider, ai-model, ai-key)
  • 8 providers: Anthropic, Groq, Gemini, OpenAI, OpenRouter, Together, Mistral, Cohere
  • Saved prompts, file context attachment, unified diff editing, AI-assisted generation

Setup:
    pip install requests pygments   # pygments is optional but highly recommended
    python code_with_ai.py

Dependencies used if installed: requests (required), pygments (syntax colors)
"""

import os, sys, re, json, shutil, socket, signal, difflib, getpass, subprocess, textwrap, shlex, time, io, contextlib, zipfile, threading, base64, tempfile, hashlib, uuid

def check_dependencies():
    required = ['requests', 'pygments', 'prompt_toolkit', 'flask', 'telebot']
    missing = []
    for pkg in required:
        try: __import__(pkg)
        except ImportError: missing.append('pyTelegramBotAPI' if pkg == 'telebot' else pkg)
    
    if missing:
        print(f"\nInstalling missing dependencies: {', '.join(missing)}...\n")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("\nDependencies installed successfully! Resuming startup...\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"\nFailed to auto-install dependencies: {e}")
            print("Please run manually: pip install requests pygments prompt_toolkit flask pyTelegramBotAPI")
            sys.exit(1)

check_dependencies()
try:
    from flask import Flask
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
from datetime import datetime

import prompt_toolkit
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory, AutoSuggest, Suggestion
from prompt_toolkit.formatted_text import ANSI


# ─── Optional: readline for arrow-key history ─────────────────────────────────
try:
    import readline
except ImportError:
    readline = None

if readline:
    readline.set_auto_history(True)
    _history_file = os.path.expanduser('~/.code_ai_history')
    try:
        readline.read_history_file(_history_file)
    except (FileNotFoundError, OSError):
        pass
    import atexit
    atexit.register(lambda: readline.write_history_file(_history_file))
    readline.set_history_length(500)

# ─── Optional dependency: Pygments for syntax highlighting ───────────────────
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
    from pygments.formatters import Terminal256Formatter
    from pygments.styles import get_style_by_name
    from pygments.util import ClassNotFound
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

# ─── Required dependency: requests ───────────────────────────────────────────
try:
    import requests as _requests
except ImportError:
    print("Missing dependency. Run:  pip install requests pygments")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI color helpers
# ═══════════════════════════════════════════════════════════════════════════════
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
# Foreground
BLACK   = "\033[30m";  RED    = "\033[31m";  GREEN  = "\033[32m"
YELLOW  = "\033[33m";  BLUE   = "\033[34m";  MAGENTA= "\033[35m"
CYAN    = "\033[36m";  WHITE  = "\033[37m"
# Bright
BBLACK  = "\033[90m";  BRED   = "\033[91m";  BGREEN = "\033[92m"
BYELLOW = "\033[93m";  BBLUE  = "\033[94m";  BMAGENTA="\033[95m"
BCYAN   = "\033[96m";  BWHITE = "\033[97m"
# Background
BG_BLACK= "\033[40m";  BG_BLUE= "\033[44m";  BG_CYAN= "\033[46m"

def c(color, text): return f"{color}{text}{RESET}"
def bold(t):        return c(BOLD, t)
def dim(t):         return c(DIM+BBLACK, t)
def ok(t):          return c(BGREEN, t)
def warn(t):        return c(BYELLOW, t)
def err(t):         return c(BRED, t)
def info(t):        return c(BCYAN, t)
def label(t):       return c(BBLUE+BOLD, t)
def hl(t):          return c(BMAGENTA, t)

# ═══════════════════════════════════════════════════════════════════════════════
# Terminal width helper
# ═══════════════════════════════════════════════════════════════════════════════
def term_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80

def divider(char="─", color=BBLACK):
    return c(color, char * min(term_width(), 80))

def header_bar(title, color=BBLUE):
    w = min(term_width(), 80)
    inner = f"  {title}  "
    pad = max(0, w - len(inner))
    left = pad // 2;  right = pad - left
    return c(color+BOLD, "─"*left + inner + "─"*right)

# ═══════════════════════════════════════════════════════════════════════════════
# Extension → language + runner map
# ═══════════════════════════════════════════════════════════════════════════════
EXT_TO_LANG = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".swift": "swift", ".m": "objectivec",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash",
    ".ps1": "powershell", ".bat": "batch", ".cmd": "batch",
    ".html": "html", ".htm": "html", ".css": "css",
    ".scss": "scss", ".sass": "scss",
    ".json": "json", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".sql": "sql", ".md": "markdown", ".markdown": "markdown",
    ".txt": "text", ".r": "r", ".jl": "julia", ".lua": "lua",
    ".pl": "perl", ".dart": "dart", ".scala": "scala", ".vue": "vue",
    ".ex": "elixir", ".exs": "elixir", ".hs": "haskell",
    ".clj": "clojure", ".erl": "erlang", ".nim": "nim",
    ".zig": "zig", ".tf": "terraform",
}

# Runner definitions: ext → (description, command_template)
# Use {file} as placeholder for the full path
RUNNERS = {
    ".py":    ("Python",         [sys.executable, "{file}"]),
    ".pyw":   ("Python",         [sys.executable, "{file}"]),
    ".js":    ("Node.js",        ["node", "{file}"]),
    ".mjs":   ("Node.js (ESM)",  ["node", "{file}"]),
    ".ts":    ("ts-node",        ["npx", "ts-node", "{file}"]),
    ".sh":    ("Bash",           ["bash", "{file}"]),
    ".bash":  ("Bash",           ["bash", "{file}"]),
    ".zsh":   ("Zsh",            ["zsh", "{file}"]),
    ".rb":    ("Ruby",           ["ruby", "{file}"]),
    ".php":   ("PHP",            ["php", "{file}"]),
    ".lua":   ("Lua",            ["lua", "{file}"]),
    ".pl":    ("Perl",           ["perl", "{file}"]),
    ".r":     ("Rscript",        ["Rscript", "{file}"]),
    ".jl":    ("Julia",          ["julia", "{file}"]),
    ".dart":  ("Dart",           ["dart", "{file}"]),
    ".go":    ("Go run",         ["go", "run", "{file}"]),
    ".java":  ("Java",           ["java", "{file}"]),      # single-file launch (Java 11+)
    ".kt":    ("Kotlin script",  ["kotlinc", "-script", "{file}"]),
    ".scala": ("Scala",          ["scala", "{file}"]),
    ".ex":    ("Elixir",         ["elixir", "{file}"]),
    ".exs":   ("Elixir script",  ["elixir", "{file}"]),
    ".nim":   ("Nim",            ["nim", "r", "{file}"]),
    ".zig":   ("Zig run",        ["zig", "run", "{file}"]),
    ".rs":    ("rustc+run",      None),                    # handled specially
    ".c":     ("gcc+run",        None),                    # handled specially
    ".cpp":   ("g+++run",        None),                    # handled specially
    ".cc":    ("g+++run",        None),
    ".cs":    ("dotnet-script",  ["dotnet-script", "{file}"]),
}

def detect_lang(path):
    if path in _lang_overrides:
        return _lang_overrides[path]
    ext = os.path.splitext(path)[1].lower()
    return EXT_TO_LANG.get(ext, "text")

# ═══════════════════════════════════════════════════════════════════════════════
# Syntax highlighting
# ═══════════════════════════════════════════════════════════════════════════════
PYGMENTS_STYLE = "monokai"
# UI themes for the editor (Ctrl+L → theme slot 0-9)
EDITOR_THEME_SLOTS = [
    "monokai",
    "native",
    "friendly",
    "colorful",
    "emacs",
    "autumn",
    "manni",
    "paraiso-dark",
    "borland",
    "fruity",
]

def syntax_highlight(code: str, lang: str) -> str:
    """Return ANSI-colored code using Pygments, or plain text fallback."""
    if not HAS_PYGMENTS or not code.strip():
        return code
    try:
        lexer = get_lexer_by_name(lang, stripall=False)
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()
    try:
        style = get_style_by_name(PYGMENTS_STYLE)
        formatter = Terminal256Formatter(style=style)
        return highlight(code, lexer, formatter)
    except Exception:
        return code

def print_code(code: str, lang: str, show_line_nums: bool = True):
    """Print syntax-highlighted code with optional line numbers."""
    colored = syntax_highlight(code, lang)
    lines = colored.splitlines()
    raw_lines = code.splitlines()
    width = len(str(len(raw_lines)))
    for i, (raw, col) in enumerate(zip(raw_lines, lines), 1):
        if show_line_nums:
            num = c(BBLACK, f"{i:>{width}} │ ")
            print(num + col)
        else:
            print(col)
    if not lines and code:
        print(code)

# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED: Cryptography for encrypted API key storage

# Editor UI theme persistence
EDITOR_THEME_CFG = os.path.expanduser("~/.code_ai_editor_theme.json")

def load_editor_theme_slot(default_slot: int = 0) -> int:
    try:
        if os.path.exists(EDITOR_THEME_CFG):
            with open(EDITOR_THEME_CFG, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
            slot = int(d.get("slot", default_slot))
            return slot if 0 <= slot <= 9 else default_slot
    except Exception:
        pass
    return default_slot


def save_editor_theme_slot(slot: int):
    try:
        slot = int(slot)
        if slot < 0 or slot > 9:
            return
        with open(EDITOR_THEME_CFG, "w", encoding="utf-8") as f:
            json.dump({"slot": slot}, f)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    import base64
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# Config file for persistent storage
CONFIG_FILE = os.path.expanduser("~/.code_ai_config.json")
ENCRYPTION_SALT = b'code_with_ai_salt_v1'

def _get_cipher():
    """Generate encryption cipher from machine-specific data"""
    if not HAS_CRYPTO:
        return None
    try:
        with open("/etc/machine-id", "r") as f:
            machine_id = f.read().strip()
    except:
        machine_id = socket.gethostname()
    password = f"{machine_id}_{getpass.getuser()}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ENCRYPTION_SALT,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return Fernet(key)

def load_config() -> dict:
    """Load configuration from file"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(config: dict):
    """Save configuration to file"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def encrypt_api_key(key: str) -> str:
    """Encrypt API key for storage"""
    cipher = _get_cipher()
    if cipher:
        return cipher.encrypt(key.encode()).decode()
    return key

def decrypt_api_key(encrypted: str) -> str:
    """Decrypt stored API key"""
    cipher = _get_cipher()
    if cipher:
        try:
            return cipher.decrypt(encrypted.encode()).decode()
        except:
            return encrypted
    return encrypted

def get_saved_provider_key(provider: str) -> tuple:
    """Get saved API key for provider"""
    config = load_config()
    provider_data = config.get("providers", {}).get(provider, {})
    if provider_data.get("key"):
        return provider_data["key"], provider_data.get("model")
    return None, None

def save_provider_key(provider: str, key: str, model: str = None):
    """Save API key for provider"""
    config = load_config()
    if "providers" not in config:
        config["providers"] = {}
    config["providers"][provider] = {
        "key": encrypt_api_key(key),
        "model": model
    }
    save_config(config)

# Model memory - track last used models
def get_last_model(provider: str) -> str:
    """Get last used model for provider"""
    config = load_config()
    return config.get("last_models", {}).get(provider)

def save_last_model(provider: str, model: str):
    """Save last used model for provider"""
    config = load_config()
    if "last_models" not in config:
        config["last_models"] = {}
    config["last_models"][provider] = model
    save_config(config)

# Startup mode
def get_startup_mode() -> str:
    """Get preferred startup mode"""
    config = load_config()
    return config.get("startup_mode", "menu")

def save_startup_mode(mode: str):
    """Save preferred startup mode"""
    config = load_config()
    config["startup_mode"] = mode
    save_config(config)

# Custom endpoints
CUSTOM_ENDPOINTS = {}

def load_custom_endpoints():
    """Load custom API endpoints"""
    config = load_config()
    return config.get("custom_endpoints", {})

def save_custom_endpoint(name: str, url: str, key: str, provider_type: str = "openai"):
    """Save custom endpoint"""
    config = load_config()
    if "custom_endpoints" not in config:
        config["custom_endpoints"] = {}
    config["custom_endpoints"][name] = {
        "url": url,
        "key": encrypt_api_key(key),
        "provider": provider_type
    }
    save_config(config)

def get_custom_endpoint(name: str) -> dict:
    """Get custom endpoint details"""
    config = load_config()
    ep = config.get("custom_endpoints", {}).get(name)
    if ep and ep.get("key"):
        ep = ep.copy()
        ep["key"] = decrypt_api_key(ep["key"])
    return ep

# ═══════════════════════════════════════════════════════════════════════════════
# Session state (module-level globals)
# ═══════════════════════════════════════════════════════════════════════════════
attached_files: dict = {}   # abs_path → {"lang": str, "content": str}
_lang_overrides: dict = {}  # abs_path → lang override
last_reply: str = ""
ai_on_terminal: bool = False   # whether to send terminal output to AI automatically

# ── In-editor preview workspace ─────────────────────────────────────────────
# AI edits done inside the editor are applied to this in-memory preview
# workspace first (so RUN can use them), and are written to disk only when
# the user explicitly saves (Ctrl+S, or /save from the terminal).
EDITOR_PREVIEW_CHANGES: dict = {}  # abs_path -> {"lang": str, "content": str}
EDITOR_PREVIEW_OPEN_ORDER: list = []  # abs_path ordered for tab/menu UI
EDITOR_PREVIEW_ACTIVE: str | None = None


def _get_lan_ip() -> str | None:
    """Best-effort LAN IP for instant LAN link printing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Routing probe; no packets are actually sent.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return None


def save_editor_preview_changes_to_disk():
    """Persist pending in-editor preview changes.

    Requirement: AI preview changes are NOT saved automatically; user must
    explicitly call /save (or press Ctrl+S in-editor).
    """
    global EDITOR_PREVIEW_CHANGES, EDITOR_PREVIEW_OPEN_ORDER, EDITOR_PREVIEW_ACTIVE

    if not EDITOR_PREVIEW_CHANGES:
        print(warn("  No pending editor preview changes to save.\n"))
        return

    changed_paths = list(EDITOR_PREVIEW_CHANGES.keys())
    for p in changed_paths:
        info = EDITOR_PREVIEW_CHANGES.get(p) or {}
        content = info.get("content", "")
        lang = info.get("lang") or detect_lang(p)
        write_text_file(p, content)
        attached_files[p] = {"lang": lang, "content": content}

    EDITOR_PREVIEW_CHANGES.clear()
    EDITOR_PREVIEW_OPEN_ORDER = []
    EDITOR_PREVIEW_ACTIVE = None
    print(ok("  Saved pending editor preview changes to disk.\n"))

# Request-size limits (fix for hitting a provider's tokens-per-minute cap):
# only the most recent messages and a capped amount of attached-file content
# are ever sent on the wire, no matter how long the session or how many/large
# the attached files are.
MAX_HISTORY_MESSAGES = 12      # most recent chat turns sent per request
MAX_CONTEXT_CHARS = 12000      # total attached-file characters sent per request

# Only one AI request in flight at a time (terminal + Telegram bridge share
# this), so two large requests can never overlap and stack up tokens.
AI_REQUEST_LOCK = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════════
# Providers
# ═══════════════════════════════════════════════════════════════════════════════
PROVIDERS = {
    "anthropic": {
        "name": "Anthropic Claude", "type": "anthropic",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "default_model": "claude-sonnet-4-6",
        "env_var": "ANTHROPIC_API_KEY",
        "key_url": "console.anthropic.com/settings/keys",
        "models": ["claude-opus-4-5", "claude-sonnet-4-6", "claude-haiku-4-5"],
    },
    "groq": {
        "name": "Groq", "type": "openai",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "env_var": "GROQ_API_KEY",
        "key_url": "console.groq.com/keys",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
    },
    "gemini": {
        "name": "Google Gemini", "type": "gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "default_model": "gemini-2.0-flash",
        "env_var": "GEMINI_API_KEY",
        "key_url": "aistudio.google.com/apikey",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "openai": {
        "name": "OpenAI", "type": "openai",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "env_var": "OPENAI_API_KEY",
        "key_url": "platform.openai.com/api-keys",
        "models": ["gpt-4o", "gpt-4o-mini", "o1-mini"],
    },
    "openrouter": {
        "name": "OpenRouter", "type": "openai",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "meta-llama/llama-3.1-8b-instruct:free",
        "env_var": "OPENROUTER_API_KEY",
        "key_url": "openrouter.ai/keys",
        "models": ["meta-llama/llama-3.1-8b-instruct:free", "google/gemma-3-4b-it:free"],
    },
    "together": {
        "name": "Together AI", "type": "openai",
        "endpoint": "https://api.together.xyz/v1/chat/completions",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        "env_var": "TOGETHER_API_KEY",
        "key_url": "api.together.ai/settings/api-keys",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"],
    },
    "mistral": {
        "name": "Mistral", "type": "openai",
        "endpoint": "https://api.mistral.ai/v1/chat/completions",
        "default_model": "mistral-small-latest",
        "env_var": "MISTRAL_API_KEY",
        "key_url": "console.mistral.ai/api-keys",
        "models": ["mistral-small-latest", "mistral-large-latest", "codestral-latest"],
    },
    
    "pollinations": {
        "name": "Pollinations AI", "type": "pollinations",
        "endpoint": "https://text.pollinations.ai/",
        "default_model": "openai",
        "env_var": "POLLINATIONS_API_KEY",
        "key_url": "pollinations.ai",
        "models": ["openai", "openai-fast"],
        "free": True,
    },
    "huggingface": {
        "name": "HuggingFace", "type": "openai",
        "endpoint": "https://api-inference.huggingface.co/v1/chat/completions",
        "default_model": "meta-llama/Llama-3.2-11B-Vision-Instruct",
        "env_var": "HF_TOKEN",
        "key_url": "huggingface.co/settings/tokens",
        "models": ["meta-llama/Llama-3.2-11B-Vision-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
    },
    "githubmodels": {
        "name": "GitHub Models", "type": "openai",
        "endpoint": "https://models.inference.ai.azure.com/chat/completions",
        "default_model": "gpt-4o-mini",
        "env_var": "GITHUB_TOKEN",
        "key_url": "github.com/settings/tokens",
        "models": ["gpt-4o-mini", "gpt-4o", "Meta-Llama-3.1-70B-Instruct", "Mistral-small"],
    },
    "cerebras": {
        "name": "Cerebras", "type": "openai",
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "default_model": "llama3.1-70b",
        "env_var": "CEREBRAS_API_KEY",
        "key_url": "cloud.cerebras.ai",
        "models": ["llama3.1-70b", "llama3.1-8b"],
    },
    "sambanova": {
        "name": "SambaNova", "type": "openai",
        "endpoint": "https://fast-api.snova.ai/v1/chat/completions",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "env_var": "SAMBANOVA_API_KEY",
        "key_url": "cloud.sambanova.ai",
        "models": ["Meta-Llama-3.3-70B-Instruct", "Qwen2.5-Coder-32B-Instruct"],
    },
    "hyperbolic": {
        "name": "Hyperbolic", "type": "openai",
        "endpoint": "https://api.hyperbolic.xyz/v1/chat/completions",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "env_var": "HYPERBOLIC_API_KEY",
        "key_url": "app.hyperbolic.xyz/settings",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct"],
    },
    "novita": {
        "name": "Novita AI", "type": "openai",
        "endpoint": "https://api.novita.ai/v3/openai/chat/completions",
        "default_model": "meta-llama/llama-3.1-8b-instruct",
        "env_var": "NOVITA_API_KEY",
        "key_url": "novita.ai/settings/key-management",
        "models": ["meta-llama/llama-3.1-8b-instruct", "meta-llama/llama-3.3-70b-instruct"],
    },
    "chutes": {
        "name": "Chutes AI", "type": "openai",
        "endpoint": "https://llm.chutes.ai/v1/chat/completions",
        "default_model": "deepseek-ai/DeepSeek-V3-0324",
        "env_var": "CHUTES_API_KEY",
        "key_url": "chutes.ai",
        "models": ["deepseek-ai/DeepSeek-V3-0324", "deepseek-ai/DeepSeek-R1"],
    },
    "custom": {
        "name": "Custom Provider", "type": "openai",
        "endpoint": "http://127.0.0.1:20128/v1/chat/completions",
        "default_model": "auto",
        "env_var": "OMNIROUTE_API_KEY",
        "key_url": "localhost:20128",
        "models": ["auto"],
    },
    "cohere": {
        "name": "Cohere", "type": "cohere",
        "endpoint": "https://api.cohere.com/v2/chat",
        "default_model": "command-r-08-2024",
        "env_var": "COHERE_API_KEY",
        "key_url": "dashboard.cohere.com/api-keys",
        "models": ["command-r-08-2024", "command-r-plus-08-2024"],
    },
}
PROVIDER_ORDER = ["anthropic", "groq", "gemini", "openai", "openrouter", "together", "mistral", "cohere", "custom", "pollinations", "huggingface", "githubmodels", "cerebras", "sambanova", "hyperbolic", "novita", "chutes"]

# ═══════════════════════════════════════════════════════════════════════════════
# Saved prompts
# ═══════════════════════════════════════════════════════════════════════════════
PROMPTS_FILE = os.path.expanduser("~/.code_ai_prompts.json")

def load_prompts() -> dict:
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_prompts(prompts: dict):
    with open(PROMPTS_FILE, "w") as f:
        json.dump(prompts, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════════════
# File utilities
# ═══════════════════════════════════════════════════════════════════════════════
def resolve_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))

def read_text_file(path: str):
    full = resolve_path(path)
    if not os.path.isfile(full):
        return False, f"No such file: {full}"
    for enc in ("utf-8", "latin-1"):
        try:
            with open(full, encoding=enc) as f:
                return True, f.read()
        except UnicodeDecodeError:
            continue
        except OSError as e:
            return False, str(e)
    return False, "Cannot decode as text."

def write_text_file(path: str, content: str) -> str:
    full = resolve_path(path)
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return full

def file_size_str(path: str) -> str:
    try:
        s = os.path.getsize(path)
        if s < 1024: return f"{s}B"
        if s < 1024*1024: return f"{s//1024}KB"
        return f"{s//(1024*1024)}MB"
    except OSError:
        return "?"

def file_mtime_str(path: str) -> str:
    try:
        mt = os.path.getmtime(path)
        return datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
    except OSError:
        return "?"

# ═══════════════════════════════════════════════════════════════════════════════
# Provider: setup / switch
# ═══════════════════════════════════════════════════════════════════════════════
def choose_provider_interactive() -> str:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:20128/v1/models", timeout=1.0)
        PROVIDERS["custom"]["endpoint"] = "http://127.0.0.1:20128/v1/chat/completions"
        PROVIDERS["custom"]["name"] = "Custom Provider"
    except Exception:
        PROVIDERS["custom"]["name"] = "Custom Provider (no local server detected)"

    print(f"\n{header_bar('Choose Provider', BBLUE)}")
    for i, key in enumerate(PROVIDER_ORDER, 1):
        p = PROVIDERS[key]
        print(f"  {c(BCYAN, str(i))}. {c(BWHITE, p['name'])}{dim('  '+p['default_model'])}")
    choice = input(f"\n{c(BBLUE,'Provider')} (1-{len(PROVIDER_ORDER)}, default 1): ").strip()
    if not choice:
        return PROVIDER_ORDER[0]
    if choice.isdigit() and 1 <= int(choice) <= len(PROVIDER_ORDER):
        return PROVIDER_ORDER[int(choice)-1]
    if choice.lower() in PROVIDERS:
        return choice.lower()
    print(warn("Not recognised, defaulting to Anthropic."))
    return PROVIDER_ORDER[0]

def get_api_key_for(provider: dict, force_prompt: bool = False) -> str:
    if provider.get("free"):
        return "anonymous"
    if not force_prompt:
        key = os.environ.get(provider["env_var"], "")
        if key:
            return key
    print(dim(f"  Get a key at: {provider['key_url']}"))
    key = getpass.getpass(f"  {provider['name']} API key: ").strip()
    if not key:
        print(err("No key — exiting."))
        sys.exit(1)
    return key

def discover_new_models(provider_key: str, provider: dict, api_key: str) -> list:
    """For openai-type providers: GET /models and return newly discovered IDs."""
    if provider.get("type") != "openai":
        return []
    try:
        endpoint = provider["endpoint"]
        # Strip '/chat/completions' to get the base URL
        base = endpoint
        if base.endswith("/chat/completions"):
            base = base[:-len("/chat/completions")]
        models_url = base.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = _requests.get(models_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                return [m["id"] for m in items if isinstance(m, dict) and "id" in m]
    except Exception:
        pass
    return []


def test_provider_models(provider_key: str, provider: dict, api_key: str, models: list = None) -> list:
    """Test each model with a tiny ping and return only the working ones."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if models is None:
        models = list(provider.get("models", []))
    if not models:
        return []

    ping_history = [
        {"role": "user", "content": "ping"},
    ]
    # For anthropic, system is separate; for others it's a system message
    ptype = provider.get("type", "openai")

    def test_one(model):
        try:
            if ptype == "anthropic":
                url = provider["endpoint"]
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                body = {"model": model, "max_tokens": 1, "system": "hi",
                        "messages": [{"role": "user", "content": "ping"}]}
            elif ptype == "gemini":
                url = provider["endpoint"].format(model=model) + f"?key={api_key}"
                headers = {"Content-Type": "application/json"}
                body = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}],
                        "generationConfig": {"maxOutputTokens": 1}}
            elif ptype == "cohere":
                url = provider["endpoint"]
                headers = {"Content-Type": "application/json",
                           "Authorization": "Bearer " + api_key}
                body = {"model": model, "messages": [{"role": "user", "content": "ping"}]}
            elif ptype == "pollinations":
                # Pollinations is always free/available; skip real test
                return model
            else:
                # openai-compatible
                url = provider["endpoint"]
                headers = {"Content-Type": "application/json",
                           "Authorization": "Bearer " + api_key}
                body = {"model": model, "max_tokens": 1,
                        "messages": [{"role": "system", "content": "hi"},
                                     {"role": "user", "content": "ping"}]}
            resp = _requests.post(url, headers=headers, json=body, timeout=5)
            if resp.status_code == 200:
                return model
        except Exception:
            pass
        return None

    working = []
    use_threads = len(models) > 5
    if use_threads:
        with ThreadPoolExecutor(max_workers=min(len(models), 10)) as ex:
            futures = {ex.submit(test_one, m): m for m in models}
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    working.append(result)
        # Preserve original order
        order = {m: i for i, m in enumerate(models)}
        working.sort(key=lambda m: order.get(m, 9999))
    else:
        for m in models:
            result = test_one(m)
            if result:
                working.append(result)
    return working


def choose_model_interactive(provider_key_or_dict, provider: dict = None, api_key: str = None) -> str:
    """Fetch real model list from endpoint, merge with known list, show all, let user pick."""
    # Support both old call style (just provider dict) and new (provider_key, provider, api_key)
    if provider is None:
        # Old style: choose_model_interactive(provider_dict)
        provider = provider_key_or_dict
        provider_key = ""
        api_key = ""
    else:
        provider_key = provider_key_or_dict

    known = list(provider.get("models", []))
    default = provider["default_model"]

    # Fetch live model list from endpoint (fast, no ping test)
    sys.stdout.write(c(BBLUE, "  Fetching model list... "))
    sys.stdout.flush()
    discovered = discover_new_models(provider_key, provider, api_key or "")
    sys.stdout.write(c(BBLACK, f"({len(discovered)} from endpoint)\n") if discovered else "\n")

    # Merge discovered with known, preserving order, known first
    all_models = list(dict.fromkeys(known + [m for m in discovered if m not in known]))

    # Persist any newly found models
    if discovered:
        for m in discovered:
            if m not in provider["models"]:
                provider["models"].append(m)
        cfg = load_config()
        cfg.setdefault("provider_models", {})[provider_key] = provider["models"]
        save_config(cfg)

    display_models = all_models if all_models else [default]

    print(f"\n{c(BBLUE,'Models for')} {provider['name']}:")
    for i, m in enumerate(display_models, 1):
        star = c(BGREEN, " ★") if m == default else ""
        tag = c(BCYAN, " (new)") if m in discovered and m not in known else ""
        print(f"  {c(BBLACK, str(i)+'.')} {m}{star}{tag}")

    effective_default = default if default in display_models else display_models[0]
    choice = input(f"  Model (Enter for {c(BGREEN, effective_default)}): ").strip()
    if not choice:
        return effective_default
    if choice.isdigit() and 1 <= int(choice) <= len(display_models):
        return display_models[int(choice)-1]
    return choice

# ═══════════════════════════════════════════════════════════════════════════════
# API communication
# ═══════════════════════════════════════════════════════════════════════════════
def build_request(provider: dict, model: str, api_key: str, history: list):
    ptype = provider["type"]
    if ptype == "pollinations":
        url = provider["endpoint"]
        headers = {"Content-Type": "application/json"}
        body = {"messages": history, "jsonMode": False, "model": model}
        return url, headers, body
    if ptype == "anthropic":
        url = provider["endpoint"]
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {"model": model, "max_tokens": 4096, "messages": history}
        return url, headers, body
    if ptype == "gemini":
        url = provider["endpoint"].format(model=model) + f"?key={api_key}"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
                for m in history
            ]
        }
        return url, headers, body
    if ptype == "cohere":
        url = provider["endpoint"]
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
        body = {"model": model, "messages": history}
        return url, headers, body
    # openai-compatible
    url = provider["endpoint"]
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
    body = {"model": model, "messages": history}
    return url, headers, body

def extract_reply(provider: dict, data: dict) -> str:
    ptype = provider["type"]
    if ptype == "pollinations":
        if data.get("_pollinations_text"):
            return data["_pollinations_text"]
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return ""
    if ptype == "anthropic":
        return "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
    if ptype == "gemini":
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text","") for p in parts)
        except (KeyError, IndexError):
            return "(empty response)"
    if ptype == "cohere":
        try:
            return data["message"]["content"][0]["text"]
        except (KeyError, IndexError):
            return data.get("text","(empty response)")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return "(empty response)"

def send_message(provider, model, api_key, history, text,
                 silent=False, include_context=True, spinner=True):
    global last_reply
    outgoing = text
    if include_context:
        ctx = build_context_block()
        if ctx:
            outgoing = ctx + text
    history.append({"role": "user", "content": outgoing})

    # Keep the request size bounded: only the most recent messages are sent.
    # (The full history still lives in `history` for anything else that
    # reads it — this only trims what actually goes over the wire.)
    trimmed_history = history[-MAX_HISTORY_MESSAGES:] if len(history) > MAX_HISTORY_MESSAGES else history
    url, headers, body = build_request(provider, model, api_key, trimmed_history)

    # spinner
    if spinner and not silent:
        sys.stdout.write(c(BBLACK, "  thinking "))
        sys.stdout.flush()

    def _clear_spinner():
        if spinner and not silent:
            sys.stdout.write("\r" + " "*25 + "\r")

    # Only one AI request in flight at a time — protects against overlap if
    # the terminal and the Telegram bridge (or anything else) ever fire at
    # the same moment, since concurrent large requests are what actually
    # blows through a provider's tokens-per-minute limit.
    with AI_REQUEST_LOCK:
        resp = None
        for attempt in range(2):   # one real attempt + one retry after a 429
            try:
                resp = _requests.post(url, headers=headers, json=body, timeout=90)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except ValueError:
                    if provider.get("type") == "pollinations":
                        data = {"_pollinations_text": resp.text}
                    else:
                        raise
                break
            except _requests.exceptions.HTTPError:
                try:
                    err_detail = resp.json()
                except ValueError:
                    err_detail = resp.text
                if resp.status_code == 429 and attempt == 0:
                    wait_s = _extract_retry_after(resp, err_detail)
                    _clear_spinner()
                    print(warn(f"  Rate limited (429) — waiting {wait_s:.1f}s and retrying once…"))
                    time.sleep(wait_s)
                    if spinner and not silent:
                        sys.stdout.write(c(BBLACK, "  thinking "))
                        sys.stdout.flush()
                    continue
                _clear_spinner()
                print(err(f"API error ({resp.status_code}): {err_detail}\n"))
                history.pop()
                return None
            except _requests.exceptions.RequestException as e:
                _clear_spinner()
                print(err(f"Request failed: {e}\n"))
                history.pop()
                return None
            except ValueError:
                _clear_spinner()
                print(err("Could not parse API response.\n"))
                history.pop()
                return None
        else:
            _clear_spinner()
            print(err("  Still rate limited after waiting — try again shortly, "
                       "or trim history/attached files with 'ai-close all'.\n"))
            history.pop()
            return None

    _clear_spinner()

    reply = extract_reply(provider, data)
    history.append({"role": "assistant", "content": reply})
    last_reply = reply
    if not silent:
        _print_ai_reply(reply)
    return reply


def _extract_retry_after(resp, err_detail) -> float:
    """Figure out how long to wait before retrying a 429, from (in order)
    the Retry-After header, a 'try again in Ns' message, or a safe default."""
    header_val = resp.headers.get("Retry-After") if resp is not None else None
    if header_val:
        try:
            return max(float(header_val), 0.5) + 0.5
        except ValueError:
            pass
    text_blob = json.dumps(err_detail) if isinstance(err_detail, (dict, list)) else str(err_detail)
    m = re.search(r'(?:try again in|retry in)\s+([\d.]+)\s*s', text_blob, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) + 0.5
        except ValueError:
            pass
    return 15.0

def _print_ai_reply(reply: str):
    """Print AI reply, rendering code blocks with syntax highlighting."""
    print(f"\n{c(BMAGENTA+BOLD, '╭─ AI ')}{c(BBLACK,'─'*40)}")
    # split on code fences
    parts = re.split(r"(```\w*\n.*?```)", reply, flags=re.DOTALL)
    for part in parts:
        fence_m = re.match(r"```(\w*)\n(.*?)```", part, re.DOTALL)
        if fence_m:
            lang_tag = fence_m.group(1) or "text"
            code_body = fence_m.group(2)
            print(c(BBLACK, f"  ┌─ {lang_tag} ") + c(BBLACK, "─"*20))
            for line in syntax_highlight(code_body, lang_tag).splitlines():
                print(c(BBLACK,"  │ ") + line)
            print(c(BBLACK, "  └" + "─"*26))
        else:
            for line in textwrap.wrap(part.strip(), width=min(term_width()-4, 76)):
                print(f"  {c(WHITE, line)}")
    print(c(BMAGENTA+BOLD, "╰" + "─"*45) + "\n")
    if os.environ.get("TERM") == "xterm" or "TTY_WRITE_BINARY" in os.environ:
        try:
            b64 = base64.b64encode(reply.encode('utf-8')).decode('utf-8')
            print(f'\033]52;c;{b64}\007', end='', flush=True)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# Context block builder
# ═══════════════════════════════════════════════════════════════════════════════
def build_context_block() -> str:
    if not attached_files:
        return ""
    blocks = []
    total_chars = 0
    for path, info in attached_files.items():
        content = info['content']
        remaining = MAX_CONTEXT_CHARS - total_chars
        if remaining <= 0:
            blocks.append(f"File: {path}\n(skipped — attached-context budget already used by earlier files)")
            continue
        if len(content) > remaining:
            content = content[:remaining] + f"\n… (truncated, {len(info['content']) - remaining} more chars not sent)"
        blocks.append(f"File: {path}\n```{info['lang']}\n{content}\n```")
        total_chars += len(content)
    return "Attached files for context:\n\n" + "\n\n".join(blocks) + "\n\n"

def extract_code_from_reply(reply: str) -> str:
    """Pull first fenced code block content, else raw reply."""
    m = re.search(r"```(?:[a-zA-Z0-9_+\-]*)\n(.*?)```", reply, re.DOTALL)
    return m.group(1) if m else reply

# ═══════════════════════════════════════════════════════════════════════════════
# FILE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
def handle_ls(arg: str):
    target = resolve_path(arg) if arg else os.getcwd()
    if not os.path.isdir(target):
        print(err(f"Not a directory: {target}\n")); return
    try:
        raw_entries = sorted(os.listdir(target))
    except OSError as e:
        print(err(str(e))); return
    if not raw_entries:
        print(dim("  (empty)\n")); return

    print(f"\n{c(BBLUE, '📂 '+ target)}")
    print(divider())
    for e in raw_entries:
        full = os.path.join(target, e)
        if os.path.isdir(full):
            print(f"  {c(BYELLOW, '▸')} {c(BBLUE+BOLD, e)}/")
        else:
            ext = os.path.splitext(e)[1].lower()
            lang = EXT_TO_LANG.get(ext, "")
            lang_tag = c(BBLACK, f"[{lang}]") if lang and lang != "text" else ""
            size = c(BBLACK, file_size_str(full))
            mtime = c(BBLACK, file_mtime_str(full))
            print(f"  {c(BBLACK,'·')} {c(BWHITE, e)} {lang_tag}  {size}  {mtime}")
    print()

def handle_tree(arg: str, max_depth: int = 3):
    root = resolve_path(arg) if arg else os.getcwd()
    if not os.path.isdir(root):
        print(err(f"Not a directory: {root}\n")); return
    print(f"\n{c(BBLUE+BOLD, root)}")
    def walk(dirpath, prefix, depth):
        if depth > max_depth: return
        try:
            entries = sorted(e for e in os.listdir(dirpath) if not e.startswith("."))
        except OSError:
            return
        for i, e in enumerate(entries):
            full = os.path.join(dirpath, e)
            last = i == len(entries)-1
            branch = c(BBLACK, "└── ") if last else c(BBLACK, "├── ")
            if os.path.isdir(full):
                print(prefix + branch + c(BBLUE+BOLD, e+"/"))
                walk(full, prefix + (c(BBLACK,"    ") if last else c(BBLACK,"│   ")), depth+1)
            else:
                ext = os.path.splitext(e)[1].lower()
                lang = EXT_TO_LANG.get(ext, "")
                lang_tag = c(BBLACK, f" [{lang}]") if lang else ""
                print(prefix + branch + c(BWHITE, e) + lang_tag)
    walk(root, "", 1)
    print()

def handle_cd(arg: str):
    if not arg:
        print(f"  {c(BBLUE, os.getcwd())}\n"); return
    target = resolve_path(arg)
    try:
        os.chdir(target)
        print(ok(f"  → {os.getcwd()}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

def handle_mkdir(arg: str):
    if not arg:
        print(warn("Usage: ai-mkdir <folder>\n")); return
    target = resolve_path(arg)
    try:
        os.makedirs(target, exist_ok=True)
        print(ok(f"  Created: {target}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# FILE ACTIONS MENU  (open in editor / AI / create / delete / more)
# ═══════════════════════════════════════════════════════════════════════════════
def file_actions_menu(path: str, provider, model, api_key, history):
    """Show action menu for a file: AI chat / editor / create / delete / more."""
    full = resolve_path(path)
    exists = os.path.isfile(full)
    lang = detect_lang(path)
    name = os.path.basename(full)

    print(f"\n{header_bar(f'  {name}  [{lang}]', BBLUE)}")
    if exists:
        size = file_size_str(full)
        mtime = file_mtime_str(full)
        print(f"  {dim(full)}  {c(BBLACK, size)}  {c(BBLACK, mtime)}")

    print(f"""
  {c(BCYAN,'1')}. {bold('Chat with AI')}       — attach to chat context
  {c(BCYAN,'2')}. {bold('Open in editor')}     — view/edit with syntax colours
  {c(BCYAN,'3')}. {bold('Create / generate')}  — AI writes a new file here
  {c(BCYAN,'4')}. {bold('AI edit')}            — AI modifies this file
  {c(BCYAN,'5')}. {bold('Run file')}           — compile/run with correct tool
  {c(BCYAN,'6')}. {bold('Delete')}             — remove this file
  {c(BCYAN,'7')}. {bold('Rename / copy')}
  {c(BCYAN,'8')}. {bold('View raw')}           — print file contents
  {c(BCYAN,'9')}. {bold('Language override')}  — change detected language
  {c(BCYAN,'s')}. {bold('Serve on localhost')} — run this file's folder as a website
  {c(BBLACK,'0')}. Back
""")
    choice = input(f"  {c(BBLUE,'Action')}: ").strip()
    if choice == "1":
        handle_open(path)
    elif choice == "2":
        handle_view_editor(path, provider, model, api_key, history, session=session)
    elif choice == "3":
        instructions = input("  Describe what this file should contain: ").strip()
        if instructions:
            handle_new(provider, model, api_key, history, f"{path} {instructions}")
    elif choice == "4":
        instructions = input("  What changes should AI make? ").strip()
        if instructions:
            handle_edit(provider, model, api_key, history, f"{path} {instructions}")
    elif choice == "5":
        handle_run(path)
    elif choice == "6":
        handle_delete_file(path)
    elif choice == "7":
        handle_rename_copy(path)
    elif choice == "8":
        handle_view_raw(path)
    elif choice == "9":
        new_lang = input(f"  New language tag for {name} (current: {lang}): ").strip()
        if new_lang:
            _lang_overrides[full] = new_lang.lower()
            if full in attached_files:
                attached_files[full]["lang"] = new_lang.lower()
            print(ok(f"  Language set to '{new_lang}'\n"))
    elif choice.lower() == "s":
        handle_serve(os.path.dirname(full) or ".")

def _read_multiline_block():
    """Read lines from stdin until a line containing only ':end' — used for
    pasting/replacing a whole file body inside the manual editor."""
    print(dim("  Paste/type content. Finish with a line containing only :end"))
    buf = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ":end":
            break
        buf.append(line)
    return "\n".join(buf)


def handle_view_editor(farg: str, provider: dict, model: str, api_key: str, history: list, session: dict = None, start_with_ai=False):
    # Legacy function kept for backward compatibility; real implementation
    # moved to handle_view_editor_v2.
    return handle_view_editor_v3(farg, provider, model, api_key, history, session=session, start_with_ai=start_with_ai)


def handle_view_editor_v2(farg: str, provider: dict, model: str, api_key: str, history: list, session: dict = None, start_with_ai=False):

    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    path = os.path.abspath(farg)
    
    while True:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        else:
            if not os.path.exists(os.path.dirname(path)) and os.path.dirname(path) != "":
                os.makedirs(os.path.dirname(path), exist_ok=True)
            content = ""

        from prompt_toolkit.lexers import PygmentsLexer
        from pygments.lexers import get_lexer_for_filename
        from pygments.util import ClassNotFound
        try:
            pt_lexer = PygmentsLexer(get_lexer_for_filename(path).__class__)
        except ClassNotFound:
            pt_lexer = None
            
        text_area = TextArea(
            text=content,
            scrollbar=True,
            line_numbers=True,
            lexer=pt_lexer
        )

        kb = KeyBindings()

        # Trigger completion manually (if device prevents auto completions)
        @kb.add("c-space")
        def _(event):
            # no-op here: prompt_toolkit handles completion UI from completer
            event.app.invalidate()
            return

        
        def _add_pair(key, pair):
            @kb.add(key)
            def _(event):
                event.current_buffer.insert_text(pair)
                event.current_buffer.cursor_position -= 1
                
        def _add_same_pair(key, pair):
            @kb.add(key)
            def _(event):
                event.current_buffer.insert_text(pair)
                event.current_buffer.cursor_position -= 1
                
        _add_pair('(', '()')
        _add_pair('{', '{}')
        _add_pair('[', '[]')
        _add_same_pair('"', '""')
        _add_same_pair("'", "''")

        @kb.add("c-x")
        def _(event):
            event.app.exit(result="exit")
            
        @kb.add("c-s")
        def _(event):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_area.text)
            
        @kb.add("c-r")
        def _(event):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_area.text)
            event.app.exit(result="run")
            
        @kb.add("c-n")
        def _(event):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_area.text)
            event.app.exit(result="nano")
            
        @kb.add("c-a")
        def _(event):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_area.text)
            event.app.exit(result="ai")
            
        menu = Window(
            height=1,
            content=FormattedTextControl(
                " Ctrl+S: Save | Ctrl+X: Exit | Ctrl+R: Run | Ctrl+A: Ask AI | Ctrl+N: Nano"
            ),
            style="class:status",
        )

        root = HSplit([text_area, menu])
        app = Application(
            layout=Layout(root),
            key_bindings=kb,
            full_screen=True,
            mouse_support=True
        )

        # Handle 'start_with_ai' param gracefully
        if start_with_ai:
            res = "ai"
            start_with_ai = False
        else:
            res = app.run()

        if res == "exit":
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_area.text)
            print(f"Saved {path}")
            break
            
        elif res == "nano":
            # global os
            os.system(f"nano '{path}'")
            
        elif res == "run":
            print(f"\n> Running {path}...\n")
            ext = os.path.splitext(path)[1].lower()
            cmd = None
            err_text = ""
            
            if ext == ".py": cmd = ["python3", path]
            elif ext == ".js": cmd = ["node", path]
            elif ext == ".sh": cmd = ["bash", path]
            elif ext == ".rb": cmd = ["ruby", path]
            elif ext in (".c", ".cpp"):
                import tempfile
                cc = "gcc" if ext == ".c" else "g++"
                fd, tmp = tempfile.mkstemp(suffix=".out")
                os.close(fd)
                cp = subprocess.run([cc, path, "-o", tmp, "-lm"], capture_output=True, text=True)
                if cp.returncode == 0:
                    cmd = [tmp]
                else:
                    print(cp.stderr)
                    err_text = cp.stderr
            elif ext == ".java": cmd = ["java", path]
            elif ext == ".go": cmd = ["go", "run", path]
            elif ext == ".rs":
                import tempfile
                fd, tmp = tempfile.mkstemp(suffix=".out")
                os.close(fd)
                cp = subprocess.run(["rustc", path, "-o", tmp], capture_output=True, text=True)
                if cp.returncode == 0: cmd = [tmp]
                else: print(cp.stderr); err_text = cp.stderr
                
            if cmd:
                print(f"Executing: {' '.join(cmd)}\n")
                try:
                    p = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
                    if p.stderr:
                        sys.stdout.write(p.stderr)
                        sys.stdout.flush()
                        err_text = p.stderr
                    if p.returncode == 0:
                        err_text = ""
                except KeyboardInterrupt:
                    pass
            elif not err_text:
                print("No quick-runner defined for this extension.")
                
            if err_text:
                ans = input(f"\n[Command failed] Ask AI to analyze and fix the syntax error? [Y/n]: ")
                if ans.lower() in ('', 'y', 'yes'):
                    _prov = session.get("provider") if session else provider
                    _mod = session.get("model") if session else model
                    _key = session.get("api_key") if session else api_key
                    if session: ensure_ai_ready(session)
                    prompt = f"Executing {os.path.basename(path)} failed:\n\n{err_text}\n\nFix the error in this file.\nReturn ONLY the replacement script inside a markdown code block. Do not add outside chatter."
                    print("\nAsking AI for fix...")
                    reply = send_message(_prov, _mod, _key, [], prompt, silent=True, include_context=False)
                    
                    if reply:
                        extracted = extract_code_from_reply(reply)
                        if extracted:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(extracted)
                            print("\nAI applied fix! Reloading in editor...")
            
            input("\nPress Enter to return to editor...")
            
        elif res == "ai":
            _prov = session.get("provider") if session else provider
            _mod = session.get("model") if session else model
            _key = session.get("api_key") if session else api_key
            
            if session: ensure_ai_ready(session)
            instr = input(f"\n[AI] What do you want to change in {path}? ")
            if instr.strip():
                with open(path, "r", encoding="utf-8") as f:
                    curr = f.read()
                    
                prompt = (
                    f"File '{path}' content:\n```\n{curr}\n```\n\n"
                    f"Task: {instr}\n\n"
                    "Rewrite the file to apply these changes. Return ONLY valid text/code inside a SINGLE markdown block. Do not use diffs."
                )
                print("\nThinking...")
                reply = send_message(_prov, _mod, _key, [], prompt, silent=True, include_context=False)
                if reply:
                    new_code = extract_code_from_reply(reply)
                    if new_code:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_code)
                        print("\nModified file successfully.")
                    else:
                        print("Error: No code block returned by AI.")
                        
            input("\nPress Enter to return to editor...")



def handle_view_editor_v3(farg: str, provider: dict, model: str, api_key: str, history: list, session: dict = None, start_with_ai=False):
    """Multi-file prompt_toolkit editor.

    Key features implemented:
      - Ctrl+M: toggle file tab menu (bottom)
      - Ctrl+L: theme slot selection (0-9)
      - Ctrl+H: host current project folder on localhost/LAN
      - Ctrl+S: persist preview changes to disk
      - Ctrl+R: RUN using preview (does not auto-save)
      - Ctrl+A: AI edit writes into preview only (does not auto-save)
      - Ctrl+X: exit

    Note: This editor is an in-memory preview workspace; AI changes are
    written to preview first, and only committed to disk on Ctrl+S or /save.
    """

    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.lexers import PygmentsLexer
    from prompt_toolkit.styles import style_from_pygments_cls, merge_styles
    from prompt_toolkit.completion import Completer, Completion

    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound
    from pygments.styles import get_style_by_name

    # --- helpers ---
    def _looks_like_path(s: str) -> bool:
        s = (s or "").strip()
        if not s:
            return False
        if "/" in s or "\\" in s:
            return True
        if s.startswith(".") or s.startswith(".."):
            return True
        ext = os.path.splitext(s)[1].lower()
        return ext in EXT_TO_LANG or ext in RUNNERS or ext in (".html", ".htm", ".css", ".js", ".mjs", ".json", ".jsx", ".tsx", ".ts")

    def _resolve_candidate_path(info: str) -> str:
        # If info is absolute, use it. If it's relative, resolve against
        # current file's directory.
        info = info.strip()
        if os.path.isabs(info):
            return os.path.abspath(info)
        base_dir = os.path.dirname(os.path.abspath(farg))
        return os.path.abspath(os.path.join(base_dir, info))

    def _extract_code_blocks(reply: str) -> dict:
        """Return mapping abs_path_or_current_None -> code."""
        mapping = {}
        if not reply:
            return mapping
        blocks = re.findall(r"```([^\n`]*)\n(.*?)```", reply, flags=re.DOTALL)
        if not blocks:
            # No fences; treat as replacement for current.
            mapping[active_path] = extract_code_from_reply(reply)
            return mapping
        for info, code in blocks:
            info = (info or "").strip()
            code = code.rstrip("\n") + "\n" if code and not code.endswith("\n") else code
            if _looks_like_path(info):
                p = _resolve_candidate_path(info)
                mapping[p] = code
            else:
                # Info might be language tag; assume it's current file.
                mapping[active_path] = code
        return mapping

    def _effective_content_for(path: str) -> str:
        if path in EDITOR_PREVIEW_CHANGES:
            return EDITOR_PREVIEW_CHANGES[path]["content"]
        ok, content = read_text_file(path)
        return content if ok else ""

    def _ensure_preview_entry(path: str):
        abs_p = os.path.abspath(path)
        if abs_p in EDITOR_PREVIEW_CHANGES:
            return
        content = ""
        ok, c = read_text_file(abs_p)
        if ok:
            content = c
        else:
            # Create parent dirs if needed for new file.
            parent = os.path.dirname(abs_p)
            if parent:
                os.makedirs(parent, exist_ok=True)
        EDITOR_PREVIEW_CHANGES[abs_p] = {"lang": detect_lang(abs_p), "content": content}
        if abs_p not in EDITOR_PREVIEW_OPEN_ORDER:
            EDITOR_PREVIEW_OPEN_ORDER.append(abs_p)

    def _parse_referenced_files(base_path: str) -> list[str]:
        """Best-effort referenced file discovery for HTML/CSS/JS-like files."""
        base_abs = os.path.abspath(base_path)
        base_dir = os.path.dirname(base_abs)
        ext = os.path.splitext(base_abs)[1].lower()
        try:
            ok, content = read_text_file(base_abs)
        except Exception:
            ok, content = False, ""
        if not ok:
            return []
        refs = []
        def _add(rel):
            if not rel:
                return
            rel = rel.strip().strip('"\'')
            if not rel:
                return
            # Ignore external URLs.
            if rel.startswith("http://") or rel.startswith("https://") or rel.startswith("//"):
                return
            # Resolve relative links.
            p = os.path.abspath(os.path.join(base_dir, rel))
            refs.append(p)

        if ext in (".html", ".htm", ".vue"):
            for m in re.finditer(r"<script[^>]*src=[\"']([^\"']+)[\"']", content, flags=re.I):
                _add(m.group(1))
            for m in re.finditer(r"<link[^>]*href=[\"']([^\"']+)[\"']", content, flags=re.I):
                _add(m.group(1))
        if ext == ".css" or ext == ".scss" or ext == ".sass":
            for m in re.finditer(r"@import\s+(?:url\(\s*)?[\"']?([^\"'\)]+)[\"']?\s*\)?", content, flags=re.I):
                _add(m.group(1))
        if ext in (".js", ".mjs", ".ts", ".tsx", ".jsx"):
            for m in re.finditer(r"import\s+[^;]*?from\s+[\"']([^\"']+)[\"']", content, flags=re.I):
                _add(m.group(1))
            for m in re.finditer(r"require\(\s*[\"']([^\"']+)[\"']\s*\)", content, flags=re.I):
                _add(m.group(1))
        # Only keep plausible text sources.
        uniq = []
        for p in refs:
            if p not in uniq:
                uniq.append(p)
        return uniq

    def _save_preview_to_current_buffer():
        if active_path is None:
            return
        EDITOR_PREVIEW_CHANGES[active_path] = {
            "lang": detect_lang(active_path),
            "content": text_area.text,
        }

    def _write_preview_to_temp_dir(paths: list[str]) -> tuple[str, str]:
        # return (temp_root, temp_active_file)
        if not paths:
            paths = [active_path]
        abs_paths = [os.path.abspath(p) for p in paths if p]
        if not abs_paths:
            abs_paths = [os.path.abspath(active_path)]
        common = os.path.commonpath(abs_paths)
        temp_root = tempfile.mkdtemp(prefix="cwa_editor_preview_", dir=os.path.expanduser("~/.hermes/cache/scratch"))
        for p in abs_paths:
            rel = os.path.relpath(p, common)
            dst = os.path.join(temp_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            content = _effective_content_for(p)
            lang = detect_lang(p)
            EDITOR_PREVIEW_CHANGES[p] = {"lang": lang, "content": content}
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)
        rel_active = os.path.relpath(active_path, common)
        return temp_root, os.path.join(temp_root, rel_active)

    def _run_preview_current():
        # Execute current file inside a temp directory reflecting preview.
        preview_paths = list(dict.fromkeys(list(EDITOR_PREVIEW_OPEN_ORDER) + list(EDITOR_PREVIEW_CHANGES.keys())))
        temp_root, temp_active = _write_preview_to_temp_dir(preview_paths)
        ext = os.path.splitext(temp_active)[1].lower()
        cmd = None
        err_text = ""
        if ext == ".py": cmd = ["python3", temp_active]
        elif ext == ".js": cmd = ["node", temp_active]
        elif ext == ".mjs": cmd = ["node", temp_active]
        elif ext == ".sh": cmd = ["bash", temp_active]
        elif ext == ".rb": cmd = ["ruby", temp_active]
        elif ext in (".c", ".cpp"):
            import tempfile as _tf
            cc = "gcc" if ext == ".c" else "g++"
            fd, tmp = _tf.mkstemp(suffix=".out")
            os.close(fd)
            cp = subprocess.run([cc, temp_active, "-o", tmp, "-lm"], capture_output=True, text=True)
            if cp.returncode == 0:
                cmd = [tmp]
            else:
                err_text = cp.stderr
        elif ext == ".java": cmd = ["java", temp_active]
        elif ext == ".go": cmd = ["go", "run", temp_active]
        elif ext == ".rs":
            import tempfile as _tf
            fd, tmp = _tf.mkstemp(suffix=".out")
            os.close(fd)
            cp = subprocess.run(["rustc", temp_active, "-o", tmp], capture_output=True, text=True)
            if cp.returncode == 0:
                cmd = [tmp]
            else:
                err_text = cp.stderr
        else:
            cmd = None

        if cmd:
            print(f"\nExecuting (preview): {' '.join(cmd)}\n")
            try:
                p = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
                if p.stderr:
                    sys.stdout.write(p.stderr)
                    sys.stdout.flush()
                    err_text = p.stderr
            except KeyboardInterrupt:
                pass
        elif not err_text:
            print("No quick-runner defined for this extension.")

        if err_text:
            return False, err_text
        return True, ""

    def _ask_ai_edit_fix(last_err: str = "") -> dict:
        _prov = session.get("provider") if session else provider
        _mod = session.get("model") if session else model
        _key = session.get("api_key") if session else api_key
        if session:
            ensure_ai_ready(session)

        # Ensure referenced files are loaded into preview (HTML/CSS/JS imports, links, etc.).
        try:
            for rp in _parse_referenced_files(active_path):
                _ensure_preview_entry(rp)
        except Exception:
            pass

        # Provide preview open files as context.
        files_for_ctx = list(dict.fromkeys(list(EDITOR_PREVIEW_OPEN_ORDER)))

        # Keep prompt bounded (avoid blowing up tokens).
        ctx_blocks = []
        used_chars = 0
        max_chars = MAX_CONTEXT_CHARS
        for p in files_for_ctx:
            content = _effective_content_for(p)
            block = f"File: {p}\n```{detect_lang(p)}\n{content}\n```"
            if used_chars + len(block) > max_chars:
                # Try to truncate content in-place for the last block.
                remaining = max(0, max_chars - used_chars)
                if remaining <= 0:
                    break
                # crude truncation
                content2 = content[:max(0, remaining - len(f"File: {p}\n```{detect_lang(p)}\n\n```") )] if isinstance(content,str) else ""
                block = f"File: {p}\n```{detect_lang(p)}\n{content2}\n```"
            ctx_blocks.append(block)
            used_chars += len(block)
            if used_chars >= max_chars:
                break
        ctx = "\n\n".join(ctx_blocks)

        if last_err:
            prompt = (
                f"We are running these files (current: {active_path}).\n\n"
                f"Execution error output:\n```\n{last_err[:2000]}\n```\n\n"
                f"Fix the code. Return ONLY fenced code blocks (```path-or-language\\ncode```), "
                f"where blocks may target multiple files using their paths (absolute or relative).\n\n"
                f"Context files:\n\n{ctx}"
            )
        else:
            instr = input(f"\n[AI] What do you want to change in {active_path}? ")
            instr = instr.strip() if instr else ""
            if not instr:
                return {}
            prompt = (
                f"We are editing a multi-file project in an IDE preview.\n"
                f"Task: {instr}\n\n"
                f"Context files (full contents):\n\n{ctx}\n\n"
                f"Return ONLY updated code in fenced blocks. Each block's info line must be either: "
                f"(1) the file path to update, or (2) a language tag to apply to the current file. "
                f"No explanations, no diffs."
            )
        reply = send_message(_prov, _mod, _key, [], prompt, silent=True, include_context=False)
        if not reply:
            return {}
        # Apply via preview: extract blocks to mapping.
        mapping = _extract_code_blocks(reply)
        return mapping

    # --- init preview workspace ---
    EDITOR_PREVIEW_CHANGES.clear()
    EDITOR_PREVIEW_OPEN_ORDER.clear()
    EDITOR_PREVIEW_ACTIVE = None

    start_abs = os.path.abspath(farg)
    initial_files = [start_abs] + _parse_referenced_files(start_abs)
    # Ensure active first.
    uniq_files = []
    for p in initial_files:
        if p not in uniq_files:
            uniq_files.append(p)

    for p in uniq_files:
        _ensure_preview_entry(p)

    # Pick theme
    theme_slot = load_editor_theme_slot(0)

    active_path = start_abs
    active_index = EDITOR_PREVIEW_OPEN_ORDER.index(start_abs) if start_abs in EDITOR_PREVIEW_OPEN_ORDER else 0

    while True:
        # Active file may have moved.
        active_path = EDITOR_PREVIEW_OPEN_ORDER[active_index]
        EDITOR_PREVIEW_ACTIVE = active_path
        # Ensure entry exists
        _ensure_preview_entry(active_path)
        content = _effective_content_for(active_path)

        # Build lexer
        try:
            pt_lexer = PygmentsLexer(get_lexer_for_filename(active_path).__class__)
        except ClassNotFound:
            pt_lexer = None

        # Syntax completer (deterministic, no AI)
        class _LangCompleter(Completer):
            _BANKS = {
                "python": ["def ", "class ", "import ", "from ", "if ", "elif ", "else:", "try:", "except ", "return ", "with ", "as ", "lambda ", "yield ", "raise "],
                "javascript": ["function ", "const ", "let ", "var ", "class ", "if (", "for (", "while (", "try {", "catch (", "finally {", "export ", "import "],
                "html": ["<!doctype html>", "<html>", "<head>", "<body>", "<div>", "<script>", "<style>", "<link rel=\"stylesheet\" href=\"\">", "<meta charset=\"\" >"],
                "css": ["display: ", "position: ", "top: ", "left: ", "width: ", "height: ", "margin: ", "padding: ", "border: ", "background: ", "color: ", "font-size: ", "flex ", "grid ", "align-items: ", "justify-content: "],
                "json": ["{", "}", "[", "]", '"key": "value"'],
            }

            def get_completions(self, document, complete_event):
                lang = detect_lang(active_path)
                bank = self._BANKS.get(lang, [])
                word = document.get_word_before_cursor(WORD=True)
                for s in bank:
                    if not word or s.lower().startswith(word.lower()):
                        yield Completion(s, start_position=-len(word) if word else 0, display=s)

        # Style with theme slot: affect syntax colors and chrome.
        pyg_style_name = EDITOR_THEME_SLOTS[int(theme_slot) % 10]
        try:
            pyg_style_cls = get_style_by_name(pyg_style_name)
            code_style = style_from_pygments_cls(pyg_style_cls)
        except Exception:
            code_style = None

        ui_style = Style.from_dict({
            "status": "fg:ansigray",
            "title": "fg:cyan bold",
            "selected": "fg:black bg:ansicyan bold",
            "entry": "fg:white",
        })
        app_style = ui_style
        if code_style is not None:
            try:
                app_style = merge_styles([ui_style, code_style])
            except Exception:
                app_style = ui_style

        # Build editor buffer
        text_area = TextArea(
            text=content,
            scrollbar=True,
            line_numbers=True,
            lexer=pt_lexer,
            completer=_LangCompleter(),
            auto_suggest=AutoSuggestFromHistory(),
            complete_while_typing=True,
        )

        # tab menu state
        tab_menu_open = False
        tab_selected = active_index
        theme_menu_open = False
        host_menu_open = False
        theme_choice = theme_slot
        host_armed = False

        def _render_bottom():
            nonlocal tab_menu_open, tab_selected, theme_menu_open
            lines = []
            if tab_menu_open:
                lines.append(("class:title", " Tabs (Ctrl+M to close) — Enter to switch, Esc to close\n"))
                for i, p in enumerate(EDITOR_PREVIEW_OPEN_ORDER):
                    label = os.path.basename(p)
                    if i == tab_selected:
                        lines.append(("class:selected", f"  {i}: {label}\n"))
                    else:
                        lines.append(("class:entry", f"  {i}: {label}\n"))
            elif theme_menu_open:
                lines.append(("class:title", " Theme slot (Ctrl+L) — press 0-9\n"))
                row = " ".join([str(i) + ("*" if i == theme_choice else "") for i in range(10)])
                lines.append(("class:entry", row + "\n"))
            else:
                changed = "" if not EDITOR_PREVIEW_CHANGES else f" preview:{len(EDITOR_PREVIEW_CHANGES)}"
                lines.append(("class:status", f" Ctrl+S Save | Ctrl+R Run | Ctrl+A AI edit | Ctrl+M Tabs | Ctrl+L Theme | Ctrl+H Host{changed} | Ctrl+X Exit\n"))
            return lines

        bottom = Window(height=4, content=FormattedTextControl(_render_bottom), style="")
        root = HSplit([text_area, bottom])

        kb = KeyBindings()

        # Trigger completion manually (if device prevents auto completions)
        @kb.add("c-space")
        def _(event):
            # no-op here: prompt_toolkit handles completion UI from completer
            event.app.invalidate()
            return


        @kb.add("c-x")
        def _(event):
            # Commit current buffer into preview before exit.
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="exit")

        @kb.add("c-s")
        def _(event):
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="save")

        @kb.add("c-r")
        def _(event):
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="run")

        @kb.add("c-a")
        def _(event):
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="ai")

        @kb.add("c-n")
        def _(event):
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="nano")

        @kb.add("c-m")
        def _(event):
            nonlocal tab_menu_open
            tab_menu_open = not tab_menu_open

        @kb.add("escape")
        def _(event):
            nonlocal tab_menu_open, theme_menu_open
            tab_menu_open = False
            theme_menu_open = False

        @kb.add("up")
        def _(event):
            nonlocal tab_selected, tab_menu_open
            if tab_menu_open:
                tab_selected = (tab_selected - 1) % max(1, len(EDITOR_PREVIEW_OPEN_ORDER))

        @kb.add("down")
        def _(event):
            nonlocal tab_selected, tab_menu_open
            if tab_menu_open:
                tab_selected = (tab_selected + 1) % max(1, len(EDITOR_PREVIEW_OPEN_ORDER))

        @kb.add("enter")
        def _(event):
            nonlocal tab_menu_open, tab_selected, active_index
            if tab_menu_open:
                active_index = tab_selected
                tab_menu_open = False
                event.app.exit(result="switch")

        # Manual completion trigger (some Termux keyboards don't reliably
        # show the completion popup automatically).
        @kb.add("c-space")
        def _(event):
            event.app.invalidate()
            return


        @kb.add("c-l")
        def _(event):
            nonlocal theme_menu_open
            theme_menu_open = not theme_menu_open

        # digits for theme selection
        for i in range(10):
            key = str(i)

            @kb.add(key)
            def _(event, i=i):
                nonlocal theme_choice, theme_menu_open, theme_slot
                if theme_menu_open:
                    theme_choice = i
                    theme_slot = i
                    # Persist theme for future sessions.
                    save_editor_theme_slot(theme_slot)
                    # Exit to rebuild app with new syntax theme.
                    event.app.exit(result="theme")

        # Hosting: avoid accidental trigger on Android keyboards.
        # Must be done as: Ctrl+H twice quickly.
        @kb.add("c-h")
        def _(event):
            nonlocal host_armed
            now = time.time()
            if not host_armed:
                host_armed = True
                # Disarm after short window.
                def _disarm():
                    nonlocal host_armed
                    host_armed = False
                event.app.create_background_task(_disarm, delay=1.0)
                return
            # Second press within window => host.
            host_armed = False
            if active_path:
                EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": text_area.text}
            event.app.exit(result="host")

        app = Application(
            layout=Layout(root),
            key_bindings=kb,
            full_screen=True,
            mouse_support=True,
            style=app_style,
        )

        # Optionally jump directly to AI edit.
        if start_with_ai:
            start_with_ai = False
            # Store and trigger AI after UI closes (we just exit UI immediately).
            return None

        res = app.run()

        if res == "exit":
            break
        if res == "switch":
            # Tab switched; just rebuild with new active file.
            continue
        if res == "theme":
            # Continue loop; rebuild app.
            continue
        if res == "save":
            save_editor_preview_changes_to_disk()
            # After save, keep editing.
            continue
        if res == "nano":
            # Persist only current file into disk for external nano.
            try:
                write_text_file(active_path, text_area.text)
            except Exception:
                pass
            os.system(f"nano '{active_path}'")
            # Reload current content into preview.
            ok, c = read_text_file(active_path)
            EDITOR_PREVIEW_CHANGES[active_path] = {"lang": detect_lang(active_path), "content": c if ok else ""}
            # Continue.
            continue
        if res == "host":
            root_dir = os.path.commonpath([os.path.dirname(p) for p in EDITOR_PREVIEW_OPEN_ORDER if p]) if EDITOR_PREVIEW_OPEN_ORDER else os.path.dirname(active_path)
            # Auto-detect free-ish port using existing server logic (it will switch if busy).
            # We still try a deterministic starting port so users get stable URLs.
            start_port = 8080 + (abs(hash(root_dir)) % 2000)

            lan_ip = _get_lan_ip() or ""
            # Bind only to localhost by default so we don't surprise-expose.
            # Requirement says: localhost link + LAN address instantly upon start.
            # We'll start on 127.0.0.1 and additionally print the LAN IP address.
            host = "127.0.0.1"
            handle_serve(f"{root_dir} :{start_port} {host}")

            if lan_ip:
                print(dim(f"  LAN address: http://{lan_ip}:{start_port} (if reachable on your Wi‑Fi)\n"))
            else:
                print(dim("  LAN address: (could not detect LAN IP automatically)\n"))

            # Optional public tunnel (manual fallback).
            try:
                tun = input("  Optional: start a public tunnel link? [y/N]: ").strip().lower()
            except Exception:
                tun = ""
            if tun in ("y", "yes"):
                print(warn("  Tunnel auto-start isn't fully automated here. If you have ngrok/cloudflared,")
                      + warn(" run it separately, then share the public URL.\n"))
            continue
        if res == "run":
            ok_run, err_text = _run_preview_current()
            if ok_run:
                input("\nPress Enter to return to editor...")
                continue
            # If run failed, offer AI fix but only into preview.
            ans = input("\n[Command failed] Ask AI to analyze and fix? [Y/n]: ").strip().lower()
            if ans in ("", "y", "yes"):
                mapping = _ask_ai_edit_fix(err_text)
                for p, code in mapping.items():
                    abs_p = os.path.abspath(p)
                    EDITOR_PREVIEW_CHANGES[abs_p] = {"lang": detect_lang(abs_p), "content": code}
                    if abs_p not in EDITOR_PREVIEW_OPEN_ORDER:
                        EDITOR_PREVIEW_OPEN_ORDER.append(abs_p)
                input("\nAI applied fixes to preview. Press Enter to re-run...")
                continue
            input("\nPress Enter to return to editor...")
            continue
        if res == "ai":
            # AI edit into preview.
            mapping = _ask_ai_edit_fix("")
            for p, code in mapping.items():
                abs_p = os.path.abspath(p)
                EDITOR_PREVIEW_CHANGES[abs_p] = {"lang": detect_lang(abs_p), "content": code}
                if abs_p not in EDITOR_PREVIEW_OPEN_ORDER:
                    EDITOR_PREVIEW_OPEN_ORDER.append(abs_p)
            # Switch editor to active_path if it got removed (it won't).
            input("\nAI applied edits to preview. Press Enter to continue editing...")
            # Keep current active_index.
            continue

    # On exit, keep preview changes in memory until user explicitly /save.
    return


def handle_view_raw(path: str):
    ok_r, content = read_text_file(path)
    if not ok_r:
        print(err(content+"\n")); return
    lang = detect_lang(path)
    print(f"\n{divider()}")
    print_code(content, lang)
    print(f"{divider()}\n")

def handle_delete_file(path: str):
    full = resolve_path(path)
    if not os.path.exists(full):
        print(warn(f"  File not found: {full}\n")); return
    confirm = input(f"  {err('Delete')} {c(BWHITE,full)}? This cannot be undone. [y/N]: ").strip().lower()
    if confirm == "y":
        try:
            os.remove(full)
            if full in attached_files:
                del attached_files[full]
            print(ok(f"  Deleted: {full}\n"))
        except OSError as e:
            print(err(f"  {e}\n"))
    else:
        print(dim("  Cancelled.\n"))

def handle_rename_copy(path: str):
    full = resolve_path(path)
    print(f"  {c(BCYAN,'1')}. Rename\n  {c(BCYAN,'2')}. Copy")
    op = input("  Choose: ").strip()
    dest = input("  Destination path: ").strip()
    if not dest: print(dim("  Cancelled.\n")); return
    dest_full = resolve_path(dest)
    try:
        if op == "1":
            os.rename(full, dest_full)
            if full in attached_files:
                attached_files[dest_full] = attached_files.pop(full)
            print(ok(f"  Renamed → {dest_full}\n"))
        elif op == "2":
            # global shutil
            shutil.copy2(full, dest_full)
            print(ok(f"  Copied → {dest_full}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# OPEN / CLOSE / FILES LIST
# ═══════════════════════════════════════════════════════════════════════════════
def handle_open(arg: str):
    if not arg:
        print(warn("Usage: ai-open <file>\n")); return
    ok_r, content = read_text_file(arg)
    if not ok_r:
        print(err(content+"\n")); return
    full = resolve_path(arg)
    lang = detect_lang(arg)
    attached_files[full] = {"lang": lang, "content": content}
    lines = content.count("\n")+1
    print(ok(f"  Attached {full}") + f" {c(BBLACK, f'[{lang}, {lines} lines]')}\n")

def handle_close(arg: str):
    if not arg:
        print(warn("Usage: ai-close <file|all>\n")); return
    if arg.strip().lower() == "all":
        attached_files.clear()
        print(ok("  Detached all files.\n")); return
    full = resolve_path(arg)
    if full in attached_files:
        del attached_files[full]
        print(ok(f"  Detached {full}.\n"))
    else:
        print(warn(f"  {full} is not attached.\n"))

def handle_files_list():
    if not attached_files:
        print(warn("  No files attached. Use 'ai-open <file>'.\n")); return
    print(f"\n{c(BBLUE+BOLD, '  Attached files:')}")
    for path, info in attached_files.items():
        lines = info["content"].count("\n")+1
        lang_tag = info["lang"]
        print(f"  {c(BBLACK,'·')} {c(BWHITE, path)} {c(BBLACK, '['+lang_tag+']')} {c(BBLACK, str(lines)+' lines')}")
    print()

def handle_lang(arg: str):
    parts = arg.split(maxsplit=1) if arg else []
    if len(parts) != 2:
        print(warn("Usage: ai-lang <file> <language>\n")); return
    path, lang = parts
    full = resolve_path(path)
    _lang_overrides[full] = lang.strip().lower()
    if full in attached_files:
        attached_files[full]["lang"] = _lang_overrides[full]
    print(ok(f"  Language for {full} set to '{lang}'\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# AI EDIT & AI NEW
# ═══════════════════════════════════════════════════════════════════════════════
def show_diff(old: str, new: str, label: str) -> bool:
    diff = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=label+" (before)",
        tofile=label+" (after)",
    ))
    if not diff:
        print(dim("  (AI version is identical — nothing to change)\n")); return False
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(c(BGREEN, line), end="")
        elif line.startswith("-") and not line.startswith("---"):
            print(c(BRED, line), end="")
        elif line.startswith("@@"):
            print(c(BCYAN, line), end="")
        else:
            print(c(BBLACK, line), end="")
    print()
    return True

def handle_edit(provider, model, api_key, history, arg: str):
    global last_reply
    parts = arg.split(maxsplit=1) if arg else []
    if not parts:
        print(warn("Usage: ai-edit <file> [instructions]\n")); return
    path = parts[0]
    instructions = parts[1] if len(parts)>1 else input("  What should change? ").strip()
    if not instructions:
        print(dim("  Cancelled.\n")); return

    full = resolve_path(path)
    if full not in attached_files:
        handle_open(path)
        if full not in attached_files:
            return

    original = attached_files[full]["content"]
    lang = attached_files[full]["lang"]
    prompt = (
        f"Here is the full current content of {path} (language: {lang}):\n\n"
        f"```{lang}\n{original}\n```\n\n"
        f"Task: {instructions}\n\n"
        "Reply with ONLY the complete updated file content in a single fenced "
        "code block, nothing else — no explanations, no partial snippets."
    )
    print(c(BBLUE, "\n  Asking AI to edit…"))
    reply = send_message(provider, model, api_key, history, prompt, silent=True)
    if reply is None: return
    last_reply = reply
    new_content = extract_code_from_reply(reply)

    print(f"\n{header_bar(f' Diff: {os.path.basename(path)} ', BYELLOW)}")
    changed = show_diff(original, new_content, path)
    if not changed: return
    confirm = input(f"  Save to {c(BWHITE, path)}? [y/N]: ").strip().lower()
    if confirm == "y":
        write_text_file(path, new_content)
        attached_files[full]["content"] = new_content
        print(ok(f"  Saved: {full}\n"))
    else:
        print(dim("  Discarded.\n"))

def handle_new(provider, model, api_key, history, arg: str):
    global last_reply
    parts = arg.split(maxsplit=1) if arg else []
    if not parts:
        print(warn("Usage: ai-new <file> [instructions]\n")); return
    path = parts[0]
    instructions = parts[1] if len(parts)>1 else input("  What should this file contain? ").strip()
    if not instructions:
        print(dim("  Cancelled.\n")); return

    full = resolve_path(path)
    if os.path.exists(full):
        confirm = input(f"  {warn(path+' already exists')} — overwrite? [y/N]: ").strip().lower()
        if confirm != "y":
            print(dim("  Cancelled.\n")); return

    lang = detect_lang(path)
    prompt = (
        f"Create the full content for a new file named {path} (language: {lang}).\n\n"
        f"Requirements: {instructions}\n\n"
        "Reply with ONLY the complete file content in a single fenced code block, nothing else."
    )
    print(c(BBLUE, "\n  Asking AI to generate…"))
    reply = send_message(provider, model, api_key, history, prompt, silent=True)
    if reply is None: return
    last_reply = reply
    content = extract_code_from_reply(reply)

    print(f"\n{header_bar(f' Preview: {os.path.basename(path)} [{lang}] ', BCYAN)}")
    print_code(content, lang)
    print(divider())
    confirm = input(f"  Save as {c(BWHITE, path)}? [y/N]: ").strip().lower()
    if confirm == "y":
        write_text_file(path, content)
        attached_files[full] = {"lang": lang, "content": content}
        print(ok(f"  Saved: {full}\n"))
    else:
        print(dim("  Discarded.\n"))

def handle_save_as(arg: str):
    if not arg:
        print(warn("Usage: ai-save-as <file>\n")); return
    if not last_reply:
        print(warn("  No AI reply yet.\n")); return
    lang = detect_lang(arg)
    content = extract_code_from_reply(last_reply)
    full = write_text_file(arg, content)
    print(ok(f"  Saved to: {full}\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# AI EXPLAIN / DEBUG / CHECK  (eai-explain, eai-debug, eai-check / ai-explain, ai-check)
# ═══════════════════════════════════════════════════════════════════════════════
def _collect_folder_files(full_dir: str, max_files=12, max_chars=20000):
    collected, total = [], 0
    for root, dirs, files in os.walk(full_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules','__pycache__','.git','vendor','venv')]
        for fn in sorted(files):
            if fn.startswith('.'):
                continue
            p = os.path.join(root, fn)
            ok_r, content = read_text_file(p)
            if not ok_r or total + len(content) > max_chars:
                continue
            collected.append((p, content))
            total += len(content)
            if len(collected) >= max_files:
                return collected
    return collected


def handle_explain(provider, model, api_key, history, arg: str):
    """ai-explain / eai-explain <file or folder> [-s short | -l long]"""
    if not arg:
        print(warn("Usage: ai-explain <file or folder> [-s|-l]\n")); return
    tokens = arg.split()
    long_form = "-l" in tokens
    target = " ".join(t for t in tokens if t not in ("-s", "-l")).strip()
    if not target:
        print(warn("Usage: ai-explain <file or folder> [-s|-l]\n")); return
    depth = ("Give a detailed, thorough explanation, section by section." if long_form else
             "Give a concise explanation in a few short paragraphs or bullets — just enough to understand it quickly.")

    full = resolve_path(target)
    if os.path.isdir(full):
        files = _collect_folder_files(full)
        if not files:
            print(warn(f"  No readable text files found in {full}\n")); return
        blocks = [f"File: {p}\n```{detect_lang(p)}\n{content}\n```" for p, content in files]
        prompt = "Explain what this project/folder does, based on these files:\n\n" + "\n\n".join(blocks) + f"\n\n{depth}"
    elif os.path.isfile(full):
        ok_r, content = read_text_file(target)
        if not ok_r:
            print(err(f"  {content}\n")); return
        lang = detect_lang(target)
        prompt = f"Explain what this file does (language: {lang}):\n\n```{lang}\n{content}\n```\n\n{depth}"
    else:
        print(err(f"  Not found: {full}\n")); return

    print(c(BBLUE, "\n  Asking AI to explain…"))
    send_message(provider, model, api_key, history, prompt)


def handle_debug(provider, model, api_key, history, arg: str):
    """ai-debug / eai-debug <file> — find bugs with line numbers and reasons,
    then optionally hand off to ai-edit to apply a fix."""
    if not arg:
        print(warn("Usage: ai-debug <file>\n")); return
    full = resolve_path(arg)
    if not os.path.isfile(full):
        print(err(f"  File not found: {full}\n")); return
    ok_r, content = read_text_file(arg)
    if not ok_r:
        print(err(f"  {content}\n")); return
    lang = detect_lang(arg)
    prompt = (
        f"Debug this {lang} file. Find bugs, logic errors, and likely runtime issues. "
        f"For each one, give the approximate line number, what's wrong, and why:\n\n"
        f"```{lang}\n{content}\n```"
    )
    print(c(BBLUE, "\n  Asking AI to debug…"))
    reply = send_message(provider, model, api_key, history, prompt)
    if reply and input("  Ask AI to apply a fix now? [y/N]: ").strip().lower() == "y":
        handle_edit(provider, model, api_key, history, f"{arg} fix the bugs just identified")


def handle_check(arg: str):
    """ai-check / eai-check <file or folder> — direct syntax/compile check,
    no editor, no run. Reports exact file/line/column + reason per issue."""
    if not arg:
        print(warn("Usage: ai-check <file or folder>\n")); return
    full = resolve_path(arg)
    if os.path.isdir(full):
        targets = [p for p, _ in _collect_folder_files(full, max_files=50, max_chars=10**9)]
    elif os.path.isfile(full):
        targets = [full]
    else:
        print(err(f"  Not found: {full}\n")); return

    any_fail = False
    for t in targets:
        lang = detect_lang(t)
        rel = os.path.relpath(t, os.getcwd())
        if lang in ("c", "cpp") and shutil.which("gcc" if lang == "c" else "g++"):
            compiler = "gcc" if lang == "c" else "g++"
            try:
                result = subprocess.run([compiler, t, "-fsyntax-only"], capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                any_fail = True
                print(err(f"  ✗ {rel}")); _print_errors(_extract_error_locations(result.stderr), result.stderr)
            else:
                print(ok(f"  ✓ {rel}"))
        elif lang == "rust" and shutil.which("rustc"):
            try:
                result = subprocess.run(["rustc", "--emit=metadata", "-o", os.devnull, t],
                                          capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                any_fail = True
                print(err(f"  ✗ {rel}")); _print_errors(_extract_error_locations(result.stderr), result.stderr)
            else:
                print(ok(f"  ✓ {rel}"))
        elif lang in _SYNTAX_CHECK_CMDS:
            passed, output = _run_syntax_check(lang, t)
            if passed:
                print(ok(f"  ✓ {rel}"))
            else:
                any_fail = True
                print(err(f"  ✗ {rel}")); _print_errors(_extract_error_locations(output), output)
        else:
            print(dim(f"  ~ {rel}: no checker for '{lang}', skipped"))
    print(ok("\n  All checked files passed.\n") if not any_fail else warn("\n  Some files have issues — see above.\n"))


# ═══════════════════════════════════════════════════════════════════════════════
# FILE OPERATIONS  (d-rename, d-reformat, d-zip, d-unzip, d-move, d-copy)
# ═══════════════════════════════════════════════════════════════════════════════
def handle_rename(arg: str):
    if not arg:
        print(warn("Usage: d-rename <file or folder>\n")); return
    full = resolve_path(arg)
    if not os.path.exists(full):
        print(err(f"  Not found: {full}\n")); return
    new_name = input(f"  New name for {os.path.basename(full)}: ").strip()
    if not new_name:
        print(dim("  Cancelled.\n")); return
    new_full = os.path.join(os.path.dirname(full), new_name)
    try:
        os.rename(full, new_full)
        print(ok(f"  Renamed to: {new_full}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))


def handle_reformat(provider, model, api_key, history, arg: str):
    if not arg:
        print(warn("Usage: d-reformat <file>\n")); return
    full = resolve_path(arg)
    if not os.path.isfile(full):
        print(err(f"  File not found: {full}\n")); return
    target_ext = input("  New format/extension (e.g. php, html, ts): ").strip().lstrip(".")
    if not target_ext:
        print(dim("  Cancelled.\n")); return
    base, _ = os.path.splitext(full)
    new_full = f"{base}.{target_ext}"
    ok_r, content = read_text_file(arg)
    if not ok_r:
        print(err(f"  {content}\n")); return
    convert = input("  Also have AI convert the content to valid syntax for that format? [y/N]: ").strip().lower()
    if convert == "y":
        old_lang = detect_lang(arg)
        new_lang = EXT_TO_LANG.get("." + target_ext, target_ext)
        prompt = (
            f"Convert this {old_lang} file's content into valid {new_lang}, keeping its behavior/structure "
            f"as close as makes sense for the target format:\n\n```{old_lang}\n{content}\n```\n\n"
            "Reply with ONLY the converted file content in a single fenced code block, nothing else."
        )
        print(c(BBLUE, "\n  Asking AI to convert…"))
        reply = send_message(provider, model, api_key, history, prompt, silent=True)
        if reply is None: return
        content = extract_code_from_reply(reply)
        new_lang_for_print = EXT_TO_LANG.get("." + target_ext, target_ext)
        print_code(content, new_lang_for_print)
    if os.path.exists(new_full) and input(f"  {new_full} exists — overwrite? [y/N]: ").strip().lower() != "y":
        print(dim("  Cancelled.\n")); return
    write_text_file(new_full, content)
    if input(f"  Keep the original {os.path.basename(full)} too? [Y/n]: ").strip().lower() == "n":
        try: os.remove(full)
        except OSError: pass
    print(ok(f"  Saved: {new_full}\n"))


def handle_zip(arg: str):
    if not arg:
        print(warn("Usage: d-zip <file or folder>\n")); return
    full = resolve_path(arg)
    if not os.path.exists(full):
        print(err(f"  Not found: {full}\n")); return
    fmt = (input("  Format — 'zip' or '7z'? [zip]: ").strip().lower() or "zip")
    base = full.rstrip("/\\")
    if fmt == "7z":
        if not shutil.which("7z"):
            print(warn("  '7z' isn't installed (pkg install p7zip) — using zip instead.\n"))
        else:
            out = base + ".7z"
            try:
                subprocess.run(["7z", "a", out, full], check=True, capture_output=True, text=True)
                print(ok(f"  Created: {out}\n"))
            except subprocess.CalledProcessError as e:
                print(err(f"  7z failed: {e.stderr}\n"))
            return
    out = base + ".zip"
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(full):
                for root, _, files in os.walk(full):
                    for fn in files:
                        p = os.path.join(root, fn)
                        zf.write(p, os.path.relpath(p, os.path.dirname(full)))
            else:
                zf.write(full, os.path.basename(full))
        print(ok(f"  Created: {out}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))


def handle_unzip(arg: str):
    if not arg:
        print(warn("Usage: d-unzip <archive>\n")); return
    full = resolve_path(arg)
    if not os.path.isfile(full):
        print(err(f"  File not found: {full}\n")); return
    dest = input(f"  Extract to [default: {os.path.dirname(full) or '.'}]: ").strip()
    dest_full = resolve_path(dest) if dest else (os.path.dirname(full) or ".")
    os.makedirs(dest_full, exist_ok=True)
    try:
        if full.lower().endswith(".7z"):
            if not shutil.which("7z"):
                print(err("  '7z' isn't installed (pkg install p7zip).\n")); return
            subprocess.run(["7z", "x", full, f"-o{dest_full}", "-y"], check=True, capture_output=True, text=True)
        else:
            with zipfile.ZipFile(full) as zf:
                zf.extractall(dest_full)
        print(ok(f"  Extracted to: {dest_full}\n"))
    except (zipfile.BadZipFile, subprocess.CalledProcessError, OSError) as e:
        print(err(f"  {e}\n"))


def handle_move(arg: str):
    if not arg:
        print(warn("Usage: d-move <file or folder>\n")); return
    full = resolve_path(arg)
    if not os.path.exists(full):
        print(err(f"  Not found: {full}\n")); return
    dest = input("  Move to (path): ").strip()
    if not dest:
        print(dim("  Cancelled.\n")); return
    dest_full = resolve_path(dest)
    try:
        os.makedirs(os.path.dirname(dest_full) or ".", exist_ok=True)
        shutil.move(full, dest_full)
        print(ok(f"  Moved to: {dest_full}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))


def handle_copy(arg: str):
    if not arg:
        print(warn("Usage: d-copy <file or folder>\n")); return
    full = resolve_path(arg)
    if not os.path.exists(full):
        print(err(f"  Not found: {full}\n")); return
    dest = input("  Copy to (path): ").strip()
    if not dest:
        print(dim("  Cancelled.\n")); return
    dest_full = resolve_path(dest)
    try:
        os.makedirs(os.path.dirname(dest_full) or ".", exist_ok=True)
        if os.path.isdir(full):
            shutil.copytree(full, dest_full, dirs_exist_ok=True)
        else:
            shutil.copy2(full, dest_full)
        print(ok(f"  Copied to: {dest_full}\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED: Global error tracking for AI solver
# ═══════════════════════════════════════════════════════════════════════════════
last_error_output: str = ""
last_error_locations: list = []

def track_errors(output: str, locations: list):
    """Track last errors for AI solving"""
    global last_error_output, last_error_locations
    last_error_output = output
    last_error_locations = locations

# Track errors after each run
_original_run_interactive = None

def handle_ai_solve_errors(provider, model, api_key, history):
    """AI analyzes and suggests fixes for last errors"""
    global last_error_output, last_error_locations
    
    if not last_error_output:
        print(warn("  No recent errors to solve. Run some code first!\n"))
        return
    
    if not last_error_locations:
        prompt = (
            f"I encountered this error output:\n\n```\n{last_error_output[:2000]}\n```\n\n"
            "Please analyze the error and suggest how to fix it. "
            "Provide specific code changes if possible."
        )
    else:
        error_summary = "\n".join([
            f"- {e['file']}:{e['line']}" + (f":{e['col']}" if e.get('col') else "") + f" → {e['msg']}"
            for e in last_error_locations[:5]
        ])
        prompt = (
            f"I encountered these errors:\n\n{error_summary}\n\n"
            f"Full error output:\n```\n{last_error_output[:2000]}\n```\n\n"
            "Please analyze these errors and suggest specific fixes with code examples."
        )
    
    print(c(BBLUE, "\n  Asking AI to solve errors...\n"))
    send_message(provider, model, api_key, history, prompt)

# ═══════════════════════════════════════════════════════════════════════════════
# FILE RUNNER with compiler support
# ═══════════════════════════════════════════════════════════════════════════════
def _extract_error_locations(output: str):
    """Best-effort extraction of (file, line, col, level, message) from
    common compiler/interpreter error formats (gcc/g++/clang, javac, rustc,
    PHP, Python tracebacks, Node)."""
    if not output:
        return []
    results = []
    for m in re.finditer(r'([^\s:()][^:\n]*):(\d+):(\d+):\s*(error|warning|fatal error|Error)?:?\s*(.+)', output):
        results.append({"file": m.group(1), "line": m.group(2), "col": m.group(3),
                         "level": (m.group(4) or "error").lower(), "msg": m.group(5).strip()})
    if results:
        return results
    for m in re.finditer(r'([^\s:()][^:\n]*):(\d+):\s*(error|warning|Error)?:?\s*(.+)', output):
        results.append({"file": m.group(1), "line": m.group(2), "col": None,
                         "level": (m.group(3) or "error").lower(), "msg": m.group(4).strip()})
    if results:
        return results
    m = re.search(r'PHP Parse error:\s*(.+?) in (.+?) on line (\d+)', output)
    if m:
        return [{"file": m.group(2), "line": m.group(3), "col": None, "level": "error", "msg": m.group(1).strip()}]
    file_lines = re.findall(r'File "(.+?)", line (\d+)', output)
    if file_lines:
        f, ln = file_lines[-1]
        tail = [l for l in output.strip().splitlines() if l.strip()]
        msg = tail[-1] if tail else "error"
        return [{"file": f, "line": ln, "col": None, "level": "error", "msg": msg}]
    return []


def _print_errors(errors, raw_output):
    if not errors:
        if raw_output and raw_output.strip():
            print(err(f"  {raw_output.strip()}\n"))
        return
    print(err(f"\n  ✗ {len(errors)} issue(s) found:"))
    for e in errors:
        loc = f"line {e['line']}" + (f", col {e['col']}" if e.get('col') else "")
        is_warning = "warn" in (e['level'] or "")
        icon = c(BYELLOW, "⚠") if is_warning else c(BRED, "✗")
        print(f"  {icon} {c(BWHITE, os.path.basename(e['file']))} — {c(BCYAN, loc)} "
              f"{dim('(' + e['level'] + ')')}")
        print(f"      {e['msg']}")
    print()


# Non-interactive syntax-check commands (no execution) for languages that
# support one — used by handle_run's pre-flight check and by 'ai-check'.
_SYNTAX_CHECK_CMDS = {
    "python":     [sys.executable, "-m", "py_compile", "{file}"],
    "php":        ["php", "-l", "{file}"],
    "javascript": ["node", "--check", "{file}"],
    "ruby":       ["ruby", "-c", "{file}"],
    "perl":       ["perl", "-c", "{file}"],
    "bash":       ["bash", "-n", "{file}"],
}


def _run_syntax_check(lang: str, full: str):
    """Returns (ok: bool, output: str). ok=True/output='' when the language
    has no checker registered, or the checker binary isn't installed
    (skipped silently rather than blocking a run)."""
    tmpl = _SYNTAX_CHECK_CMDS.get(lang)
    if not tmpl:
        return True, ""
    cmd = [p.replace("{file}", full) for p in tmpl]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return True, ""
    combined = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, combined


def _compile_and_run_c_cpp(full: str, lang: str):
    """Compile C/C++ with gcc/g++ (capturing output so errors can be parsed
    with exact line/column/reason), then run the binary fully interactively
    — stdin/stdout inherited so scanf/cin work and output streams live."""
    import tempfile
    compiler = "gcc" if lang == "c" else "g++"
    with tempfile.NamedTemporaryFile(suffix="", delete=False) as tf:
        binary = tf.name
    try:
        print(c(BBLUE, f"  Compiling with {compiler}…"))
        compile_result = subprocess.run(
            [compiler, full, "-o", binary, "-lm"],
            capture_output=True, text=True, timeout=60
        )
        if compile_result.returncode != 0:
            print(err(f"  Compilation failed ({compiler}):"))
            _print_errors(_extract_error_locations(compile_result.stderr), compile_result.stderr)
            return
        if compile_result.stderr:
            print(warn(f"  Warnings:"))
            _print_errors(_extract_error_locations(compile_result.stderr), compile_result.stderr)
        print(ok(f"  Compiled OK — running (interactive: type input as the program asks for it)\n"))
        _run_interactive([binary])
    finally:
        try:
            os.unlink(binary)
        except OSError:
            pass

def _compile_and_run_rust(full: str):
    """Compile Rust with rustc then run the binary interactively."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix="", delete=False) as tf:
        binary = tf.name
    try:
        print(c(BBLUE, "  Compiling with rustc…"))
        compile_result = subprocess.run(
            ["rustc", full, "-o", binary],
            capture_output=True, text=True, timeout=60
        )
        if compile_result.returncode != 0:
            print(err(f"  Compilation failed (rustc):"))
            _print_errors(_extract_error_locations(compile_result.stderr), compile_result.stderr)
            return
        print(ok("  Compiled OK — running (interactive: type input as the program asks for it)\n"))
        _run_interactive([binary])
    finally:
        try:
            os.unlink(binary)
        except OSError:
            pass

def _run_interactive(cmd):
    """Run a program with the terminal's stdin/stdout/stderr inherited
    directly — so input()/scanf/cin/Scanner all work live, and output
    streams to the screen exactly as it's produced, until the program
    either finishes or the loop completes. Ctrl+C stops a runaway program
    without killing the whole app."""
    start = time.time()
    try:
        result = subprocess.run(cmd)   # no capture_output, no timeout — fully interactive
        elapsed = time.time() - start
        color = BGREEN if result.returncode == 0 else BRED
        print(c(color, f"\n  ── exit code: {result.returncode}  ({elapsed:.2f}s) ──\n"))
    except KeyboardInterrupt:
        print(warn("\n  Stopped (Ctrl+C).\n"))
    except FileNotFoundError:
        print(err(f"  '{cmd[0]}' not found.\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

def handle_run(arg: str, extra_args: list = None):
    """Run a file with its appropriate compiler/interpreter. Compiled
    languages are checked for errors (exact file/line/column/reason) before
    anything runs; everything runs fully interactively afterward, so
    console input (scanf, input(), cin, Scanner, …) and streamed output
    work exactly like running it directly in a terminal, until the program
    or its loop finishes."""
    if not arg:
        print(warn("Usage: ai-run <file> [args…]\n")); return
    full = resolve_path(arg)
    if not os.path.isfile(full):
        print(err(f"  File not found: {full}\n")); return

    ext = os.path.splitext(full)[1].lower()
    lang = detect_lang(arg)
    runner = RUNNERS.get(ext)

    if runner is None:
        print(warn(f"  No runner registered for '{ext}'.\n"
                   "  Registered extensions: " +
                   ", ".join(sorted(RUNNERS.keys())) + "\n"))
        return

    desc, cmd_template = runner

    # special compile+run paths (C/C++/Rust)
    if cmd_template is None:
        confirm = input(f"  {bold(desc)} compile + run {c(BWHITE, full)}? [y/N]: ").strip().lower()
        if confirm != "y":
            print(dim("  Cancelled.\n")); return
        if lang == "rust":
            _compile_and_run_rust(full)
        else:
            _compile_and_run_c_cpp(full, lang)
        return

    # Pre-flight syntax check for languages that support one — catches
    # errors with exact line/column/reason before we even try to run.
    ok_syntax, check_output = _run_syntax_check(lang, full)
    if not ok_syntax:
        print(err(f"  Syntax check failed for {os.path.basename(full)}:"))
        _print_errors(_extract_error_locations(check_output), check_output)
        if input("  Run anyway? [y/N]: ").strip().lower() != "y":
            return

    cmd = [part.replace("{file}", full) for part in cmd_template]
    if extra_args:
        cmd.extend(extra_args)

    confirm = input(
        f"  Run {c(BBLUE, desc)}: {c(BWHITE, ' '.join(cmd))}? [y/N]: "
    ).strip().lower()
    if confirm != "y":
        print(dim("  Cancelled.\n")); return

    print(c(BBLUE, f"\n  Running ({desc}) — interactive: type input as the program asks for it\n"))
    _run_interactive(cmd)

# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL WEB SERVER — run html/php/css/js/etc. on localhost with one command
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL WEB SERVER — run html/php/css/js/etc. on localhost, one command
# Supports several servers running at once (tracked by port), a shorthand
# ":PORT" / "HOST:PORT" syntax, automatic fallback to a free port when the
# requested one is busy, and stopping servers even from a different session
# (state is persisted to a small JSON file keyed by port + PID).
# ═══════════════════════════════════════════════════════════════════════════════
running_servers: dict = {}   # port(int) -> {"proc": Popen, "dir": str, "host": str, "kind": str}   (this process only)
SERVER_STATE_FILE = os.path.expanduser("~/.code_with_ai_servers.json")


def _load_server_state() -> dict:
    if os.path.exists(SERVER_STATE_FILE):
        try:
            with open(SERVER_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_server_state(state: dict):
    try:
        with open(SERVER_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    return True


def _reap_dead_servers():
    """Drop entries whose process already exited on its own."""
    for port in list(running_servers.keys()):
        if running_servers[port]["proc"].poll() is not None:
            del running_servers[port]


def _is_port_free(host: str, port: int) -> bool:
    test_host = host if host and host != "0.0.0.0" else "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((test_host, port))
        free = True
    except OSError:
        free = False
    finally:
        s.close()
    return free


def _get_random_free_port(host: str) -> int:
    test_host = host if host and host != "0.0.0.0" else "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((test_host, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _parse_serve_args(arg: str):
    """Accepts, in any order: a directory, a bare port, ':PORT', or
    'HOST:PORT' / a bare host. Returns (directory_or_None, port_or_None, host_or_None)."""
    directory = port = host = None
    for tok in (arg.split() if arg else []):
        if tok.startswith(":") and tok[1:].isdigit():
            port = int(tok[1:])
        elif re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', tok):
            h, p = tok.rsplit(":", 1)
            host, port = h, int(p)
        elif tok.isdigit():
            port = int(tok)
        elif tok in ("0.0.0.0", "127.0.0.1", "localhost") or re.match(r'^\d{1,3}(\.\d{1,3}){3}$', tok):
            host = tok
        else:
            directory = tok
    return directory, port, host


def handle_serve(arg: str, _retrying: bool = False):
    """Serve a directory on localhost (or a given host, e.g. 0.0.0.0 for LAN
    access). Uses PHP's built-in server when PHP is installed (executes .php
    and serves .html/.css/.js/etc. natively); falls back to Python's static
    file server (static files only) otherwise. Several servers can run at
    once, each on its own port — see 'ai-stopserve' to stop one or all."""
    directory, req_port, host = _parse_serve_args(arg)
    directory = directory or os.getcwd()
    host = host or "127.0.0.1"
    req_port = req_port if req_port is not None else 8080

    full_dir = resolve_path(directory)
    if not os.path.isdir(full_dir):
        print(err(f"  Not a directory: {full_dir}\n")); return

    _reap_dead_servers()
    state = _load_server_state()

    if req_port in running_servers:
        print(warn(
            f"  Port {req_port} is already serving {running_servers[req_port]['dir']} in this session "
            f"(PID {running_servers[req_port]['proc'].pid}). Run 'ai-stopserve :{req_port}' first, "
            f"or just pick another port.\n"
        )); return

    if str(req_port) in state and _pid_alive(state[str(req_port)].get("pid")):
        print(warn(
            f"  Port {req_port} is already in use by a Code With AI server from another session "
            f"(PID {state[str(req_port)]['pid']}, dir {state[str(req_port)]['dir']}). "
            f"Run 'ai-stopserve :{req_port}' to stop it, or pick another port.\n"
        )); return

    if host == "0.0.0.0":
        print(warn("  Binding to 0.0.0.0 exposes this server to your whole LAN. "
                    "Only do this on networks you trust — never on public Wi-Fi.\n"))

    actual_port = req_port
    if not _is_port_free(host, req_port):
        actual_port = _get_random_free_port(host)
        print(warn(f"  Port {req_port} is already in use (by something outside this tool) — "
                    f"automatically switched to free port {actual_port}.\n"))

    php_path = shutil.which("php")
    if php_path:
        cmd = [php_path, "-S", f"{host}:{actual_port}", "-t", full_dir]
        kind = "PHP built-in server — executes .php, serves .html/.css/.js/images/etc. as static files"
    else:
        cmd = [sys.executable, "-m", "http.server", str(actual_port), "--directory", full_dir, "--bind", host]
        kind = "Python static file server — serves .html/.css/.js/etc. (no PHP found, so .php will NOT execute; 'pkg install php' to enable it)"

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except OSError as e:
        print(err(f"  Could not start server: {e}\n")); return

    time.sleep(0.6)
    if proc.poll() is not None:
        out = proc.stdout.read() if proc.stdout else ""
        print(err(f"  Server exited immediately:\n{out}"))
        if not _retrying and "address already in use" in out.lower():
            fallback_port = _get_random_free_port(host)
            print(warn(f"  Retrying automatically on free port {fallback_port}...\n"))
            handle_serve(f"{full_dir} :{fallback_port} {host}", _retrying=True)
        else:
            print()
        return

    running_servers[actual_port] = {"proc": proc, "dir": full_dir, "host": host, "kind": kind}
    state[str(actual_port)] = {"pid": proc.pid, "dir": full_dir, "host": host, "started": time.time()}
    _save_server_state(state)

    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{actual_port}"
    print(ok(f"\n  Serving {full_dir}"))
    print(f"  {dim(kind)}")
    print(f"  {c(BGREEN+BOLD, url)}" + (dim(f"   (also: http://localhost:{actual_port})") if display_host == "127.0.0.1" else ""))
    if host == "0.0.0.0":
        print(dim(f"  On the same Wi-Fi, other devices can use http://<this-phone's-LAN-IP>:{actual_port}"))
    print(dim(f"  Use 'ai-stopserve :{actual_port}' to stop this one, or 'ai-stopserve' to stop all.\n"))


def _stop_port(port: int) -> bool:
    """Stop the server on `port`, whether it belongs to this process or was
    started by an earlier one (via the persisted PID)."""
    stopped = False

    info = running_servers.get(port)
    if info and info["proc"].poll() is None:
        info["proc"].terminate()
        try:
            info["proc"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            info["proc"].kill()
        stopped = True
    running_servers.pop(port, None)

    state = _load_server_state()
    key = str(port)
    if key in state:
        pid = state[key].get("pid")
        if _pid_alive(pid):
            try:
                os.kill(int(pid), signal.SIGTERM)
                time.sleep(0.3)
                if _pid_alive(pid):
                    os.kill(int(pid), signal.SIGKILL)
                stopped = True
            except OSError:
                pass
        del state[key]
        _save_server_state(state)

    return stopped


def handle_stop_serve(arg: str = ""):
    """'ai-stopserve' stops every known server (this session + any left over
    from a previous one). 'ai-stopserve :PORT' (or just the port number)
    stops only that one."""
    _reap_dead_servers()
    state = _load_server_state()
    tok = arg.strip()

    if tok:
        port_str = tok[1:] if tok.startswith(":") else tok
        if not port_str.isdigit():
            print(warn("  Usage: ai-stopserve  or  ai-stopserve :PORT\n")); return
        port = int(port_str)
        if port not in running_servers and str(port) not in state:
            print(warn(f"  No server tracked on port {port}.\n")); return
        if _stop_port(port):
            print(ok(f"  Stopped server on port {port}.\n"))
        else:
            print(warn(f"  Port {port} wasn't actually running (cleaned up stale record).\n"))
        return

    all_ports = set(running_servers.keys()) | {int(p) for p in state.keys() if p.isdigit()}
    if not all_ports:
        print(warn("  No servers are currently running.\n")); return
    n = 0
    for port in sorted(all_ports):
        if _stop_port(port):
            n += 1
    print(ok(f"  Stopped {n} server(s).\n") if n else warn("  Nothing needed stopping (records cleaned up).\n"))


def handle_serve_log(arg: str = ""):
    """List every server currently tracked — this session's and any left
    running from a previous one."""
    _reap_dead_servers()
    state = _load_server_state()
    ports = set(running_servers.keys()) | {int(p) for p in state.keys() if p.isdigit()}
    if not ports:
        print(warn("  No servers are currently running.\n")); return
    print(f"\n{header_bar(' Running servers ', BBLUE)}")
    for port in sorted(ports):
        info = running_servers.get(port)
        if info:
            print(f"  {c(BGREEN,'●')} :{port}  host={info['host']}  dir={info['dir']}  {dim('(this session)')}")
        else:
            s = state.get(str(port), {})
            print(f"  {c(BYELLOW,'●')} :{port}  host={s.get('host','?')}  dir={s.get('dir','?')}  "
                  f"{dim('(from a previous session, PID '+str(s.get('pid','?'))+')')}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT — bridge this AI session to a Telegram bot by token
# ═══════════════════════════════════════════════════════════════════════════════
def _make_telegram_input(base: str, chat_id, offset_box: list):
    """Build a drop-in replacement for the builtin input() that, for the
    duration of one Telegram-triggered command, sends any prompt text to
    that Telegram chat and blocks until the user replies there — so
    handlers written for the terminal (confirmations, 'what should this
    file contain?', etc.) work unmodified when triggered from Telegram."""
    def tg_input(prompt: str = ""):
        prompt = strip_ansi(prompt).strip()
        _requests.post(f"{base}/sendMessage",
                        json={"chat_id": chat_id, "text": prompt or "…"})
        deadline = time.time() + 180  # give someone up to 3 minutes to reply
        while time.time() < deadline:
            params = {"timeout": 20}
            if offset_box[0] is not None:
                params["offset"] = offset_box[0]
            try:
                resp = _requests.get(f"{base}/getUpdates", params=params, timeout=25).json()
            except _requests.exceptions.RequestException:
                continue
            if not resp.get("ok"):
                continue
            for update in resp.get("result", []):
                offset_box[0] = update["update_id"] + 1
                msg = update.get("message") or update.get("edited_message")
                if not msg or "text" not in msg or msg["chat"]["id"] != chat_id:
                    continue
                return msg["text"]
        _requests.post(f"{base}/sendMessage",
                        json={"chat_id": chat_id, "text": "(no reply in time — cancelled)"})
        return ""
    return tg_input


def _normalize_telegram_text(text: str) -> str:
    """Telegram convention is '/command' — accept that alongside the plain
    'ai-command' form the terminal uses, without stripping the slash off
    the two commands that genuinely start with one ('/ai', '/noai')."""
    t = text.strip()
    if t in ("/ai", "/noai"):
        return t
    if t.startswith("/") and not t.startswith("//"):
        candidate = t[1:]
        if re.match(r'^(ai-|d-|tbot-token)', candidate, re.IGNORECASE):
            return candidate
    return t


def handle_telegram(session: dict):
    """Connect this AI session to a Telegram bot via long polling. Every
    message is run through the exact same command dispatcher as the
    terminal — ai-help, ai-new, ai-run, ai-serve, plain chat, all of it —
    and whatever it would have printed in the terminal is sent back as the
    reply, so Telegram behaves identically to typing into the app itself.
    Token comes from (in order): the session's 'telegram_token' (set via
    'tbot-token' or --tbot-token at launch), the TELEGRAM_BOT_TOKEN env var,
    or a one-time terminal prompt if neither is set."""
    token = (session.get("telegram_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        token = getpass.getpass("  Telegram bot token (from @BotFather, input hidden): ").strip()
        if token:
            session["telegram_token"] = token
    if not token:
        print(warn("  No token given. Set one anytime with 'tbot-token <TOKEN>'.\n")); return

    base = f"https://api.telegram.org/bot{token}"
    try:
        me = _requests.get(f"{base}/getMe", timeout=15).json()
    except _requests.exceptions.RequestException as e:
        print(err(f"  Could not reach Telegram: {e}\n")); return
    if not me.get("ok"):
        print(err(f"  Invalid token or Telegram error: {me}\n")); return

    bot_username = me["result"].get("username", "bot")
    print(ok(f"\n  Connected as @{bot_username}"))
    print(dim("  Message the bot on Telegram — any ai-*/d-* command works exactly like the\n"
              "  terminal, and plain messages chat with the AI. Send /status for session info,\n"
              "  /stop to end the bridge from Telegram, or press Ctrl+C here at any time.\n"))

    prompts = load_prompts()
    offset_box = [None]
    try:
        while True:
            params = {"timeout": 30}
            if offset_box[0] is not None:
                params["offset"] = offset_box[0]
            try:
                resp = _requests.get(f"{base}/getUpdates", params=params, timeout=35)
                data = resp.json()
            except _requests.exceptions.RequestException:
                time.sleep(2)
                continue
            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset_box[0] = update["update_id"] + 1
                msg = update.get("message") or update.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg["text"].strip()
                if not text:
                    continue
                print(c(BBLACK, f"  [telegram] {text}"))

                if text == "/stop":
                    _requests.post(f"{base}/sendMessage",
                                    json={"chat_id": chat_id, "text": "Stopping the bridge. Bye!"})
                    print(warn("  Bridge stopped from Telegram.\n"))
                    return
                if text == "/status":
                    prov = session["provider"]
                    reply_text = (
                        f"Provider: {prov['name']}\nModel: {session['model']}\n"
                        f"Directory: {os.getcwd()}\nAttached files: {len(attached_files)}"
                    )
                    for i in range(0, len(reply_text), 4000):
                        _requests.post(f"{base}/sendMessage",
                                        json={"chat_id": chat_id, "text": reply_text[i:i+4000]})
                    continue

                # Run the exact same dispatcher the terminal uses, capturing
                # everything it prints (and answering any input() prompts
                # via Telegram itself) so the reply matches the terminal 1:1.
                command_text = _normalize_telegram_text(text)
                buf = io.StringIO()
                real_input = globals().get("input", input)
                globals()["input"] = _make_telegram_input(base, chat_id, offset_box)
                try:
                    with contextlib.redirect_stdout(_Tee(buf)):
                        dispatch_command(command_text, session, prompts, via_telegram=True)
                except Exception as e:
                    print(err(f"  Error handling Telegram command: {e}"))
                    buf.write(f"Error: {e}\n")
                finally:
                    globals()["input"] = real_input

                reply_text = strip_ansi(buf.getvalue()).strip() or "(done — nothing to show)"
                for i in range(0, len(reply_text), 4000):
                    _requests.post(f"{base}/sendMessage",
                                    json={"chat_id": chat_id, "text": reply_text[i:i+4000]})
    except KeyboardInterrupt:
        print(warn("\n  Telegram bridge stopped.\n"))


def handle_tbot_token(session: dict, arg: str):
    """Quickly view, set, or change the Telegram bot token from the terminal
    — never stored in this file. 'tbot-token' alone prompts (hidden input);
    'tbot-token <TOKEN>' sets it directly since you already typed it in the
    terminal; 'tbot-token clear' removes it from this session."""
    arg = arg.strip()
    if not arg:
        current = session.get("telegram_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if current:
            masked = current[:6] + "…" + current[-4:] if len(current) > 12 else "•••set•••"
            print(dim(f"  Current Telegram token: {masked}"))
        new_token = getpass.getpass("  New Telegram bot token (from @BotFather, input hidden, Enter to cancel): ").strip()
        if new_token:
            session["telegram_token"] = new_token
            print(ok("  Telegram token updated. Run 'ai-telegram' to connect.\n"))
        else:
            print(dim("  Left unchanged.\n"))
        return
    if arg.lower() in ("clear", "reset", "none"):
        session["telegram_token"] = None
        print(ok("  Telegram token cleared for this session.\n"))
        return
    session["telegram_token"] = arg
    print(ok("  Telegram token set. Run 'ai-telegram' to connect.\n"))


# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL  (shell passthrough + optional AI analysis)
# ═══════════════════════════════════════════════════════════════════════════════
def handle_terminal(cmd_str: str, provider, model, api_key, history):
    """Run a shell command. Optionally send output to AI."""
    global ai_on_terminal
    if not cmd_str:
        print(warn("Usage: ! <shell command>  (e.g.  !ls -la  or  !npm install)\n")); return

    print(c(BBLUE, f"\n  $ {cmd_str}"))
    try:
        result = subprocess.run(
            cmd_str, shell=True, capture_output=True, text=True, timeout=120
        )
        combined = ""
        if result.stdout:
            print(result.stdout, end="")
            combined += result.stdout
        if result.stderr:
            print(c(BYELLOW, result.stderr), end="")
            combined += result.stderr
        rc_color = BGREEN if result.returncode == 0 else BRED
        print(c(rc_color, f"\n  [exit {result.returncode}]\n"))

        if ai_on_terminal and combined.strip():
            follow_up = input(c(BBLACK,"  Send output to AI? [Y/n]: ")).strip().lower()
            if follow_up != "n":
                prompt = (
                    f"I ran this command:\n```\n{cmd_str}\n```\n\n"
                    f"Output (exit {result.returncode}):\n```\n{combined[:3000]}\n```\n\n"
                    "Please review the output and comment on any errors, warnings, or notable results."
                )
                send_message(provider, model, api_key, history, prompt)
    except subprocess.TimeoutExpired:
        print(err("  Timed out after 120s.\n"))
    except OSError as e:
        print(err(f"  {e}\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER / MODEL / KEY switch commands
# ═══════════════════════════════════════════════════════════════════════════════
def handle_ai_provider(session: dict):
    """Interactively switch provider (and optionally model + key)."""
    pk = choose_provider_interactive()
    prov = PROVIDERS[pk]
    key = get_api_key_for(prov, force_prompt=False)
    mdl = choose_model_interactive(pk, prov, key)
    session["provider_key"] = pk
    session["provider"] = prov
    session["api_key"] = key
    session["model"] = mdl
    print(ok(f"\n  Switched to {prov['name']} / {mdl}\n"))

def handle_ai_model(session: dict):
    """Switch model only (same provider + key)."""
    prov = session["provider"]
    pk = session.get("provider_key", "")
    key = session.get("api_key", "")
    mdl = choose_model_interactive(pk, prov, key)
    session["model"] = mdl
    print(ok(f"\n  Model set to {mdl}\n"))

def handle_ai_key(session: dict):
    """Update API key for the current provider."""
    prov = session["provider"]
    key = get_api_key_for(prov, force_prompt=True)
    session["api_key"] = key
    print(ok(f"\n  API key updated for {prov['name']}\n"))

def handle_ai_status(session: dict):
    """Print current session settings."""
    prov = session["provider"]
    print(f"\n{header_bar(' Session Status ', BBLUE)}")
    print(f"  {label('Provider')}  {prov['name']}")
    print(f"  {label('Model   ')}  {session['model']}")
    key_preview = session['api_key'][:8] + "…" if session['api_key'] else c(BRED,'(none)')
    print(f"  {label('API Key ')}  {key_preview}")
    print(f"  {label('AI→Term ')}  {'on' if ai_on_terminal else 'off'}  {dim('(ai-terminal toggle)')}")
    print(f"  {label('Attached')}  {len(attached_files)} file(s)")
    print(f"  {label('History ')}  {len(session['history'])} message(s)")
    if HAS_PYGMENTS:
        print(f"  {label('Pygments')}  {ok('enabled')} ({PYGMENTS_STYLE} theme)")
    else:
        print(f"  {label('Pygments')}  {warn('not installed')} (pip install pygments)")
    print()

# ═══════════════════════════════════════════════════════════════════════════════
# SAVED PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════
def normalize_name(name: str):
    name = name.strip()
    if not name: return None
    return name if name.startswith("-") else "-"+name

def handle_save_prompt(prompts: dict):
    name = normalize_name(input("  Name for prompt (e.g. pm1): "))
    if not name:
        print(dim("  Cancelled.\n")); return
    text = input("  Prompt text: ").strip()
    if not text:
        print(dim("  Cancelled.\n")); return
    prompts[name] = text
    save_prompts(prompts)
    print(ok(f"  Saved '{name}'. Type it to run.\n"))

def handle_delete_prompt(prompts: dict, arg: str):
    name = normalize_name(arg)
    if name and name in prompts:
        del prompts[name]
        save_prompts(prompts)
        print(ok(f"  Deleted '{name}'.\n"))
    else:
        print(warn(f"  No saved prompt '{arg}'.\n"))

# ═══════════════════════════════════════════════════════════════════════════════
# HELP
# ═══════════════════════════════════════════════════════════════════════════════
HELP_TEXT = """
{H}═══════════════  Code With AI — Commands  ═══════════════{R}

{B}CHAT{R}
  {C}(just type){R}           Send a message to the AI
  {C}/ai{R}                  Enable AI responses   (default on)
  {C}/noai{R}                Disable AI (chat commands still work)
  {C}/status{R}            Show current provider / model / key

{B}PROVIDER / MODEL / KEY  (switch anytime){R}
  {C}/provider{R}          Switch AI provider
  {C}/model{R}             Switch model (same provider)
  {C}/key{R}               Update API key (same provider)

{B}MODE SWITCHES{R}
  {C}/ai_only{R}                  Drop into a bare AI-only chat (no commands);
                     type '/full' inside it to come back
  {C}/editor <file>{R}       Open the manual in-Termux editor directly
  {C}/aieditor <file>{R}     Same, but jumps straight to the editor's
                     'ai' prompt — same as 'e/ai <file>'
  {C}e/ai <file>{R}           Alias for !!aieditor

{B}FILES & FOLDERS{R}
  {C}/pwd{R}               Show current directory
  {C}/cd <dir>{R}          Change directory
  {C}/ls [dir]{R}          List files with info
  {C}/mkdir <dir>{R}       Create folder
  {C}/tree [dir]{R}        Folder tree
  {C}/file <file>{R}       Open file actions menu (view/AI/run/delete/…)
  {C}/editor <file>{R}     Manual line editor, directly in Termux — has
                     its own 'ai' command to ask/rewrite mid-edit
  {C}/open <file|dir>{R}    Open a file in the editor; if given a folder,
                     lists it and asks which file to open
  {C}/open <file>{R}       Attach file to AI context
  {C}/close <file|all>{R}  Detach file(s) from context
  {C}/files{R}             List attached files
  {C}/lang <f> <lang>{R}   Override detected language

{B}AI EXPLAIN / DEBUG / CHECK{R}
  {C}/explain <f|dir> [-s|-l]{R}   AI explains a file or whole folder
                     -s short (default), -l long/detailed
  {C}/explain{R}          Same as /explain — for use inside editor flows
  {C}/debug <file>{R}      AI finds bugs with line numbers + reasons,
                     then offers to hand off to /edit to fix them
  {C}/debug{R}            Same as /debug
  {C}/check <f|dir>{R}     Direct syntax/compile check, no editor, no run —
                     exact file/line/column + reason per issue
  {C}/check{R}            Same as /check

{B}HISTORY & SESSION{R}
  {C}/history [N]{R}      Show last N chat messages (default 10)
  {C}/clear{R}           Clear chat history
  {C}/retry{R}           Resend last user message
  {C}/copy{R}            Copy last AI reply to clipboard
  {C}/cost{R}            Show estimated session token usage

{B}SEARCH & WEB{R}
  {C}/search <query>{R}  Search DuckDuckGo, show top results, optionally ask AI

{B}CODE TEMPLATES{R}
  {C}/template [name]{R} Generate boilerplate (flask-app, telegram-bot, cli-tool, react-app, fastapi)

{B}GIT SHORTCUTS{R}
  {C}/git <subcmd>{R}    Shortcuts: status/add/commit/push/log/diff/init/clone

{B}FILE OPERATIONS{R}
  {C}/rename <f|dir>{R}     Rename (asks for the new name)
  {C}/reformat <file>{R}    Change format/extension; optionally has AI
                     convert the content to match (e.g. .html → .php)
  {C}/zip <f|dir>{R}        Archive as .zip (built-in) or .7z (needs p7zip)
  {C}/unzip <archive>{R}    Extract a .zip or .7z (asks destination)
  {C}/move <f|dir>{R}       Move (asks destination path)
  {C}/copy <f|dir>{R}       Copy (asks destination path)

{B}AI EDITING{R}
  {C}/edit <file> [instr]{R}   AI modifies file → diff → confirm save
  {C}/new <file> [instr]{R}    AI generates new file → preview → save
  {C}/save-as <file>{R}        Save last AI reply to a file

{B}RUNNING CODE{R}
  {C}/run <file>{R}        Compiles/checks first (exact file/line/column +
                     reason on any error), then runs FULLY INTERACTIVELY —
                     scanf/input()/cin/Scanner all work live, output streams
                     until the program or its loop finishes
                     Supported: Python, Node, Bash, Ruby, PHP, Lua,
                     Perl, R, Julia, Dart, Go, Java, Kotlin, Scala,
                     Elixir, Nim, Zig, Rust (rustc), C (gcc), C++ (g++)
  {C}/run <file>{R}         Same as /run — short alias

{B}RUN ON LOCALHOST (web files){R}
  {C}/serve [dir] [port] [host]{R}
                     Serve a folder on http://HOST:PORT
                     (default: current dir, port 8080, host 127.0.0.1).
                     Shorthand: '/serve :9000' or '/serve 0.0.0.0:9000'.
                     If the port is busy, a free one is picked automatically.
                     Several servers can run at once, each on its own port.
                     Executes .php via PHP's built-in server; serves
                     .html/.css/.js/images/etc. as static files automatically.
  {C}/serve [dir] [port] [host]{R}  Same as /serve — short alias
  {C}/stopserve{R}         Stop ALL running servers
  {C}/stopserve :PORT{R}   Stop only the server on that port
  {C}/servelog{R}          List every server currently running

{B}TELEGRAM BOT BRIDGE{R}
  {C}/tbot-token{R}            Set/change the bot token — asked right here in
                     the terminal, never stored in this file. No argument
                     prompts (hidden input); with a token typed inline it's
                     set instantly: {C}/tbot-token 123456:ABC...{R}
                     {C}/tbot-token clear{R} removes it for this session.
                     Launch flag for a fast start: {C}--tbot-token YOUR_TOKEN{R}
                     (or set TELEGRAM_BOT_TOKEN in the environment).
  {C}/telegram{R}          Connect this AI session to a Telegram bot
                     using the token from tbot-token / --tbot-token / env,
                     or asks once if none is set. /status and /stop
                     work from Telegram; Ctrl+C here also stops it.

{B}TERMINAL{R}
  {C}!<command>{R}           Run any shell command  (e.g. !npm install)
  {C}/terminal{R}          Toggle AI analysis of terminal output (on/off)

{B}SAVED PROMPTS{R}
  {C}/save{R}              Save a reusable prompt
  {C}/list{R}              List saved prompts
  {C}/del <name>{R}        Delete a saved prompt
  {C}-<name>{R}              Run a saved prompt (e.g. -myfix)

{B}GENERAL{R}
  {C}/help{R}              Show this help
  {C}exit / quit{R}          Exit

"""

def print_help(prompts: dict):
    H = BBLUE+BOLD; B = BYELLOW+BOLD; C = BCYAN; R = RESET
    print(HELP_TEXT.format(H=H, B=B, C=C, R=R))
    if prompts:
        print(c(BYELLOW+BOLD, "  Saved prompts:"))
        for name, text in prompts.items():
            preview = text[:55]+"…" if len(text)>55 else text
            print(f"  {c(BCYAN, name)}  {dim(preview)}")
        print()

# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════════
def print_banner(provider_name: str, model: str):
    w = min(term_width(), 80)
    print(c(BBLUE, "╔" + "═"*(w-2) + "╗"))
    title = "  Code With AI  "
    sub   = f"  {provider_name} / {model}  "
    print(c(BBLUE,"║") + c(BBLUE+BOLD, title.center(w-2)) + c(BBLUE,"║"))
    print(c(BBLUE,"║") + c(BBLACK, sub.center(w-2))        + c(BBLUE,"║"))
    print(c(BBLUE, "╚" + "═"*(w-2) + "╝"))
    hints = [
        c(BBLACK,"Type to chat  "),
        c(BCYAN,"!cmd")+c(BBLACK," for terminal  "),
        c(BCYAN,"ai-file <f>")+c(BBLACK," for file actions  "),
        c(BCYAN,"/serve")+c(BBLACK," to run on localhost  "),
        c(BCYAN,"/help")+c(BBLACK," for all commands"),
    ]
    print("  " + "".join(hints))
    if not HAS_PYGMENTS:
        print(c(BYELLOW,"\n  Tip: pip install pygments  for syntax highlighting\n"))
    else:
        print()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def choose_startup_mode() -> str:
    """Ask up front how they want to start: jump straight into a file in the
    manual Code Editor, the full Chat-with-AI experience (AI + every ai-*
    command), or a bare AI-only chat with no file/run/server commands."""
    print(f"\n{header_bar(' Code With AI ', BBLUE)}")
    print(f"  {c(BCYAN,'1')}. Code Editor   — open a file and start editing directly in Termux")
    print(f"  {c(BCYAN,'2')}. Chat with AI  — full experience: AI chat + files + run + serve (recommended)")
    print(f"  {c(BCYAN,'3')}. AI only       — plain chat with the AI, no file/run/server commands")
    choice = input("  Choose (1-3, default 2): ").strip()
    return {"1": "editor", "3": "ai_only"}.get(choice, "chat")


def run_ai_only_chat(session: dict):
    """A stripped-down loop for people who just want to talk to the model —
    no file, run, or server commands; only exit/quit and the AI itself."""
    prov, mod, key, hist = session["provider"], session["model"], session["api_key"], session["history"]
    print(dim("\n  AI-only mode — just type to chat. Type 'exit' to quit, or 'ai-full' to unlock every command.\n"))
    while True:
        try:
            user_input = input(f"{c(BGREEN,'●AI')} {c(BBLUE+BOLD,'❯')} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(c(BBLACK, "\n  Goodbye!\n")); return
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print(c(BBLACK, "\n  Goodbye!\n")); return
        if user_input.lower() == "ai-full":
            print(ok("  Switching to the full command set.\n")); return "full"
        send_message(prov, mod, key, hist, user_input)


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


class _Tee:
    """Writes to real stdout (so the terminal still shows everything) and
    into an in-memory buffer at the same time, so callers can capture what
    a block of code printed — used to relay command output to Telegram."""
    def __init__(self, buf):
        self.buf = buf
        self.real = sys.__stdout__
    def write(self, s):
        self.real.write(s)
        self.buf.write(s)
    def flush(self):
        self.real.flush()



# ═══════════════════════════════════════════════════════════════════════════════
# New Feature Handlers
# ═══════════════════════════════════════════════════════════════════════════════

def handle_ai_replit_bot(session):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        bot_token = input(c(BBLUE, "  Enter Telegram Bot Token: ")).strip()
        if not bot_token:
            print(warn("  Bot token required.\n"))
            return
        os.environ["TELEGRAM_BOT_TOKEN"] = bot_token

    print(ok("  Web server started on :8080 for Replit keep-alive. Connecting Telegram bot...\n"))
    
    if HAS_FLASK:
        app = Flask(__name__)
        @app.route('/')
        def home():
            return "Bot is running!"
        def run_server():
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            app.run(host='0.0.0.0', port=8080)
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
    else:
        print(warn("  Flask not installed, skipping keep-alive server.\n"))

    handle_telegram(session)


def handle_ai_history(session, user_input):
    parts = user_input.split()
    n = 10
    if len(parts) > 1 and parts[1].isdigit():
        n = int(parts[1])
    hist = session["history"]
    if not hist:
        print(dim("  History is empty.\n"))
        return
    print(c(BBLUE, f"  Last {n} Messages:\n"))
    for msg in hist[-n:]:
        role = msg['role'].capitalize()
        content = textwrap.shorten(msg['content'], width=100, placeholder="...")
        color = BGREEN if role == "User" else BMAGENTA
        print(c(color, f"  [{role}]: ") + c(WHITE, content))
    print()

def handle_ai_clear(session):
    conf = input(warn("  Clear chat history? (y/N): ")).strip().lower()
    if conf == 'y':
        session["history"].clear()
        print(ok("  History cleared.\n"))
    else:
        print(dim("  Cancelled.\n"))

def handle_ai_copy():
    global last_reply
    if not last_reply:
        print(warn("  No recent AI reply to copy.\n"))
        return
    text = last_reply
    try:
        if shutil.which("termux-clipboard-set"):
            subprocess.run(["termux-clipboard-set"], input=text.encode(), check=True)
            print(ok("  Copied to Termux clipboard.\n"))
            return
        elif shutil.which("pbcopy"):
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            print(ok("  Copied to Mac clipboard.\n"))
            return
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
            print(ok("  Copied via xclip.\n"))
            return
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
            print(ok("  Copied via xsel.\n"))
            return
    except Exception as e:
        pass
    print(warn("  No clipboard tool found. Text:\n"))
    print(text + "\n")

def handle_ai_search(session, user_input):
    query = user_input[len("/search"):].strip()
    if not query:
        print(warn("  Usage: ai-search <query>\n"))
        return
    print(dim(f"  Searching DuckDuckGo for: {query}..."))
    try:
        url = "https://lite.duckduckgo.com/lite/"
        resp = _requests.post(url, data={"q": query}, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
        # Very rough regex for snippets
        snippets = re.findall(r'<td class="result-snippet">(.+?)</td>', html, flags=re.IGNORECASE)
        if not snippets:
            print(warn("  No results found.\n"))
            return
        results_text = "Search results for {}:\n".format(query)
        for i, snip in enumerate(snippets[:5], 1):
            cln = re.sub(r'<[^>]+>', '', snip).strip()
            print(c(BWHITE, f"  {i}.") + f" {cln}")
            results_text += f"{i}. {cln}\n"
        print()
        ask = input(c(BBLUE, "  Send results to AI? (y/N): ")).strip().lower()
        if ask == 'y':
            session["last_user_message"] = results_text
            send_message(session["provider"], session["model"], session["api_key"], session["history"], "I searched for " + query + " and found:\n" + results_text)
    except Exception as e:
        print(err(f"  Search failed: {e}\n"))

def handle_ai_cost(session):
    hist = session["history"]
    total_chars = sum(len(m["content"]) for m in hist)
    approx_tokens = total_chars // 4
    cost_notes = "(approximate estimate only)"
    print(c(BWHITE, "  Session Usage Estimate:"))
    print(f"    Total Characters: {total_chars}")
    print(f"    Approx. Tokens:   {approx_tokens} {dim(cost_notes)}\n")

def handle_ai_template(user_input):
    parts = user_input.split()
    name = parts[1] if len(parts) > 1 else ""
    templates = {
        "flask-app": "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef index():\n    return 'Hello World'\n\nif __name__ == '__main__':\n    app.run(debug=True)\n",
        "telegram-bot": "import os\nimport telebot\n\nbot = telebot.TeleBot(os.environ.get('BOT_TOKEN'))\n\n@bot.message_handler(commands=['start'])\ndef start(m):\n    bot.reply_to(m, 'Hello')\n\nbot.polling()\n",
        "cli-tool": "import sys\nimport argparse\n\ndef main():\n    parser = argparse.ArgumentParser()\n    args = parser.parse_args()\n    print('Running')\n\nif __name__ == '__main__':\n    main()\n",
        "react-app": "import React from 'react';\n\nexport default function App() {\n  return <div>Hello World</div>;\n}\n",
        "fastapi": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef read_root():\n    return {'Hello': 'World'}\n"
    }
    if not name or name not in templates:
        print(c(BWHITE, "  Available templates:"))
        for t in templates:
            print("    " + t)
        print()
        return
    
    ext_map = {"react-app": "jsx"}
    ext = ext_map.get(name, "py")
    filename = f"{name}.{ext}"
    if os.path.exists(filename):
        print(warn(f"  {filename} already exists.\n"))
        return
    with open(filename, "w") as f:
        f.write(templates[name])
    print(ok(f"  Created {filename} from template '{name}'.\n"))

def handle_ai_git(user_input):
    cmd = user_input[len("/git"):].strip()
    if not cmd:
        print(warn("  Usage: ai-git status/add/commit/push/log/diff/init/clone\n"))
        return
    if cmd == "status":
        subprocess.run(["git", "status"])
    elif cmd == "add":
        subprocess.run(["git", "add", "."])
    elif cmd == "commit":
        msg = input(c(BBLUE, "  Commit message: ")).strip()
        if msg:
            subprocess.run(["git", "commit", "-m", msg])
        else:
            print(warn("  Aborted.\n"))
    elif cmd == "push":
        subprocess.run(["git", "push"])
    elif cmd == "log":
        subprocess.run(["git", "log", "--oneline", "-10"])
    elif cmd == "diff":
        subprocess.run(["git", "diff"])
    elif cmd == "init":
        subprocess.run(["git", "init"])
    elif cmd.startswith("clone "):
        subprocess.run(["git", "clone", cmd[6:].strip()])
    else:
        print(warn(f"  Unknown git subcommand: {cmd}\n"))
    print()

def dispatch_command(user_input: str, session: dict, prompts: dict, via_telegram: bool = False):
    """The single command dispatcher shared by the terminal REPL and the
    Telegram bridge, so anything typed in Telegram — ai-help, ai-new,
    ai-run, ai-serve, plain chat, everything — behaves exactly like typing
    it into the terminal. Returns 'exit' if the caller should end the
    session (terminal only; ignored/blocked when via_telegram)."""
    global ai_on_terminal

    prov = session["provider"]
    mod  = session["model"]
    key  = session["api_key"]
    hist = session["history"]

    user_input = user_input.strip()
    if not user_input:
        return None
        
    if user_input.startswith("ai-"): user_input = "/" + user_input[3:]
    elif user_input.startswith("d-"): user_input = "/" + user_input[2:]
    elif user_input.startswith("!!"): user_input = "/" + user_input[2:]
    elif user_input.startswith("e-"): user_input = "/" + user_input[2:]
    
    lower = user_input.lower()

    # ── Exit / reentrant bridge — blocked when coming from Telegram ────────
    if lower in ("exit", "quit"):
        if via_telegram:
            print(warn("  'exit'/'quit' don't apply here — send /stop in Telegram to end the bridge.\n"))
            return None
        print(c(BBLACK, "\n  Goodbye!\n"))
        return "exit"
    if lower == "/telegram":
        if via_telegram:
            print(warn("  Already bridged to Telegram — can't start another bridge from inside it.\n"))
            return None
        handle_telegram(session); return None

    # ── AI toggle ─────────────────────────────────────────────────────────
    if lower in ("/ai", "ai-on"):
        session["ai_enabled"] = True;  print(ok("  AI responses enabled.\n")); return None
    if lower in ("/noai", "ai-off"):
        session["ai_enabled"] = False; print(warn("  AI responses disabled.\n")); return None

    # ── Mode switches: !!ai / !!editor / !!aieditor ─────────────────────────
    if lower in ("/ai_only",):
        if via_telegram:
            print(warn("  '!!ai' mode is terminal-only — just chat normally here.\n")); return None
        result = run_ai_only_chat(session)
        if result == "full":
            print(ok("  Back to the full command set.\n"))
        return None
    if lower == "/editor" or lower.startswith("!!editor "):
        farg = user_input[len("/editor"):].strip()
        if not farg or farg in ["!find", "/", "\\/"]:
            farg = get_path_interactively() or ""
        if farg:
            handle_view_editor(farg, prov, mod, key, hist, session=session)
        return None
    if lower == "/aieditor" or lower.startswith("!!aieditor ") or lower == "/aieditor" or lower.startswith("e/ai "):
        prefix = "/aieditor" if lower.startswith("/aieditor") else "/aieditor"
        farg = user_input[len(prefix):].strip()
        if not farg or farg in ["!find", "/", "\\/"]:
            farg = get_path_interactively() or ""
        if farg:
            handle_view_editor(farg, prov, mod, key, hist, session=session, start_with_ai=True)
        return None

    # ── e-open: open a file (or pick one from a folder) directly in the editor ──
    if lower.startswith("/open") :
        farg = user_input[len("/open"):].strip()
        if not farg or farg in ["!find", "/", "\\/"]:
            farg = get_path_interactively() or ""
        if not farg:
            return None
        efull = resolve_path(farg)
        if os.path.isdir(efull):
            handle_ls(farg)
            farg = input("  File to edit: ").strip()
            if not farg:
                return None
        handle_view_editor(farg, prov, mod, key, hist, session=session)
        return None

    # ── AI explain / debug / check (eai-* inside the editor context, ai-* generally) ──
    if lower.startswith("/explain") or lower.startswith("/explain"):
        prefix_len = len("/explain") if lower.startswith("/explain") else len("/explain")
        handle_explain(prov, mod, key, hist, user_input[prefix_len:].strip()); return None
    if lower.startswith("/debug") or lower.startswith("/debug"):
        prefix_len = len("/debug") if lower.startswith("/debug") else len("/debug")
        handle_debug(prov, mod, key, hist, user_input[prefix_len:].strip()); return None
    if lower.startswith("/check") or lower.startswith("/check"):
        prefix_len = len("/check") if lower.startswith("/check") else len("/check")
        handle_check(user_input[prefix_len:].strip()); return None

    # ── File operations: rename / reformat / zip / unzip / move / copy ─────────
    if lower.startswith("/rename"):
        handle_rename(user_input[len("/rename"):].strip()); return None
    if lower.startswith("/reformat"):
        handle_reformat(prov, mod, key, hist, user_input[len("/reformat"):].strip()); return None
    if lower.startswith("/zip"):
        handle_zip(user_input[len("/zip"):].strip()); return None
    if lower.startswith("/unzip"):
        handle_unzip(user_input[len("/unzip"):].strip()); return None
    if lower.startswith("/move"):
        handle_move(user_input[len("/move"):].strip()); return None
    if lower.startswith("/copy"):
        handle_copy(user_input[len("/copy"):].strip()); return None

    # ── Help ──────────────────────────────────────────────────────────────
    # ── New commands ──────────────────────────────────────────────────────────
    if lower == "/replit-bot":
        handle_ai_replit_bot(session)
        return None
    if lower.startswith("/history"):
        handle_ai_history(session, user_input)
        return None
    if lower == "/clear":
        handle_ai_clear(session)
        return None
    if lower == "/retry":
        if not session.get("last_user_message"):
            print(warn("  No previous user message to retry.\n"))
            return None
        print(c(BBLACK, "  Retrying..."))
        ensure_ai_ready(session)
        send_message(session["provider"], session["model"], session["api_key"], hist, session["last_user_message"])
        return None
    if lower == "/copy":
        handle_ai_copy()
        return None
    if lower.startswith("/search"):
        handle_ai_search(session, user_input)
        return None
    if lower == "/cost":
        handle_ai_cost(session)
        return None
    if lower.startswith("/template"):
        handle_ai_template(user_input)
        return None
    if lower.startswith("/git"):
        handle_ai_git(user_input)
        return None

    if lower == "/help":
        print_help(prompts); return None

    # ── Status ────────────────────────────────────────────────────────────
    if lower == "/status":
        handle_ai_status(session); return None

    # ── Provider / model / key switching ────────────────────────────────────
    if lower == "/provider":
        handle_ai_provider(session); return None
    if lower == "/model":
        handle_ai_model(session); return None
    if lower == "/key":
        handle_ai_key(session); return None

    # ── Terminal passthrough: ! prefix ───────────────────────────────────────
    if user_input.startswith("!"):
        if via_telegram:
            print(warn("  Shell passthrough ('!command') isn't available from Telegram for safety.\n"))
            return None
        handle_terminal(user_input.split(" ", 1)[1].strip() if " " in user_input else "", prov, mod, key, hist); return None

    # ── Terminal AI toggle ────────────────────────────────────────────────────
    if lower == "ai-terminal":
        ai_on_terminal = not ai_on_terminal
        state = ok("on") if ai_on_terminal else warn("off")
        print(f"  Terminal AI analysis: {state}\n"); return None

    # ── File & folder commands ───────────────────────────────────────────────
    if lower == "/pwd":
        print(f"  {c(BBLUE, os.getcwd())}\n"); return None
    arg = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
    if lower == "/cd" or arg in ["!find", "/", "\\/"]: # catch / and !find
        p = get_path_interactively()
        if p: handle_cd(p)
        return None
    if lower.startswith("/cd "):
        handle_cd(arg); return None
    if lower.startswith("/mkdir "):
        handle_mkdir(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None
    if lower.startswith("/tree"):
        handle_tree(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None
    if lower.startswith("/ls"):
        handle_ls(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None

    # File actions menu
    if lower.startswith("/file ") or lower == "/file":
        farg = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
        if not farg or farg in ["!find", "/", "\\/"]:
            farg = get_path_interactively() or ""
        if farg:
            file_actions_menu(farg, prov, mod, key, hist)
        return None

    if lower.startswith("/open "):
        handle_open(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None
    if lower.startswith("/close ") or lower == "/close":
        handle_close(user_input.split(" ", 1)[1].strip() if " " in user_input else "" if lower.startswith("/close ") else ""); return None
    if lower == "/files":
        handle_files_list(); return None
    if lower.startswith("/lang "):
        handle_lang(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None

    # ── Manual in-Termux editor (with AI available inside it) — checked before
    # 'ai-edit' below since "/editor" would otherwise match that prefix first ──
    if lower.startswith("/editor"):
        farg = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
        if not farg or farg in ["!find", "/", "\\/"]:
            farg = get_path_interactively() or ""
        if farg:
            handle_view_editor(farg, prov, mod, key, hist, session=session)
        return None

    # ── AI editing ────────────────────────────────────────────────────────────
    if lower.startswith("/edit"):
        handle_edit(prov, mod, key, hist, user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None
    if lower.startswith("/new"):
        handle_new(prov, mod, key, hist, user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None
    if lower.startswith("/save-as "):
        handle_save_as(user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None

    # ── Run file ──────────────────────────────────────────────────────────────
    if lower.startswith("/run") or lower.startswith("/run"):
        prefix_len = 6 if lower.startswith("/run") else 5
        parts = user_input[prefix_len:].strip().split()
        file_arg = parts[0] if parts else ""
        extra = parts[1:] if len(parts)>1 else []
        if not file_arg:
            print(warn("Usage: d-run <file> [args…]  (alias: ai-run)\n")); return None
        handle_run(file_arg, extra); return None

    # ── Run on localhost (html/php/css/js/static + PHP execution) ─────────────
    if lower.startswith("/serve") or lower.startswith("/serve"):
        prefix_len = 8 if lower.startswith("/serve") else 7
        handle_serve(user_input[prefix_len:].strip()); return None
    if lower.startswith("/stopserve") or lower.startswith("/stopserve"):
        sarg = user_input[len("/stopserve"):].strip() if lower.startswith("/stopserve") else user_input[len("/stopserve"):].strip()
        handle_stop_serve(sarg); return None
    if lower.startswith("/servelog") or lower.startswith("/servelog"):
        handle_serve_log(); return None

    # ── Telegram token ────────────────────────────────────────────────────────
    if lower == "/tbot-token" or lower.startswith("/tbot-token "):
        if via_telegram:
            print(warn("  Changing the bot token from inside Telegram isn't supported for safety — "
                        "use the terminal.\n"))
            return None
        handle_tbot_token(session, user_input[len("/tbot-token"):].strip()); return None

    # ── Saved prompts / editor preview save ─────────────────────────────────
    if lower == "/save":
        # If the in-editor AI preview workspace has pending changes, /save
        # commits them to disk. Otherwise, /save behaves like the original
        # "save a reusable prompt" command.
        if EDITOR_PREVIEW_CHANGES:
            save_editor_preview_changes_to_disk()
            return None
        handle_save_prompt(prompts); return None
    if lower == "/list":
        if prompts:
            print(c(BYELLOW+BOLD,"\n  Saved prompts:"))
            for name, text in prompts.items():
                preview = text[:58]+"…" if len(text)>58 else text
                print(f"  {c(BCYAN,name)}  {dim(preview)}")
            print()
        else:
            print(warn("  No saved prompts. Use 'ai-save'.\n"))
        return None
    if lower.startswith("/del "):
        handle_delete_prompt(prompts, user_input.split(" ", 1)[1].strip() if " " in user_input else ""); return None

    # Run saved prompt
    if user_input.startswith("-"):
        if user_input in prompts:
            print(c(BBLACK, f"  Running '{user_input}'…"))
            if session["ai_enabled"]:
                ensure_ai_ready(session)
                send_message(session["provider"], session["model"], session["api_key"], hist, prompts[user_input])
            else:
                print(dim(f"  (AI off) Prompt: {prompts[user_input]}\n"))
        else:
            print(warn(f"  No saved prompt '{user_input}'. Type 'ai-list'.\n"))
        return None

    # ── Default: send to AI ──────────────────────────────────────────────────
    session["last_user_message"] = user_input
    if session["ai_enabled"]:
        ensure_ai_ready(session)
        send_message(session["provider"], session["model"], session["api_key"], hist, user_input)
    else:
        print(dim(f"  [AI off] You said: {user_input}\n"))
    return None


def _parse_cli_telegram_token() -> str:
    """Pick up a Telegram token from the command line so it never has to
    live inside this file: `python code_with_ai.py --tbot-token YOUR_TOKEN`
    (also accepts -T). Falls back to TELEGRAM_BOT_TOKEN if neither is given."""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a in ("--tbot-token", "-T") and i + 1 < len(argv):
            return argv[i + 1].strip()
        if a.startswith("--tbot-token="):
            return a.split("=", 1)[1].strip()
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()




def ensure_ai_ready(session):
    if session.get("provider_key") and session.get("api_key"):
        return

    print()
    provider_key = None
    api_key = None
    model = None

    cfg = load_config()
    last_provider_key = cfg.get("last_provider")
    if last_provider_key and last_provider_key in PROVIDERS:
        last_model = get_last_model(last_provider_key)
        last_pname = PROVIDERS[last_provider_key]["name"]
        prompt_str = f"  Last session: {c(BWHITE, last_pname)} / {c(BGREEN, last_model or 'default')}. Continue? [Y/n]: "
        try:
            resume = input(prompt_str).strip().lower()
        except (EOFError, KeyboardInterrupt):
            resume = "n"
        if resume in ("", "y", "yes"):
            provider_key = last_provider_key
            provider = PROVIDERS[provider_key]
            saved_key, _ = get_saved_provider_key(provider_key)
            if saved_key:
                api_key = decrypt_api_key(saved_key)
            else:
                api_key = get_api_key_for(provider)
            model = last_model or provider["default_model"]

    if provider_key is None:
        provider_key = choose_provider_interactive()
        provider = PROVIDERS[provider_key]
        api_key = get_api_key_for(provider)
        model = choose_model_interactive(provider_key, provider, api_key)

    provider = PROVIDERS[provider_key]

    save_provider_key(provider_key, api_key, model)
    save_last_model(provider_key, model)
    cfg = load_config()
    cfg["last_provider"] = provider_key
    save_config(cfg)

    session["provider_key"] = provider_key
    session["provider"] = provider
    session["api_key"] = api_key
    session["model"] = model

    print_banner(provider["name"], model)


def main():
    global ai_on_terminal

    session = {
        "provider_key": None,
        "provider": None,
        "api_key": None,
        "model": None,
        "history": [],
        "last_user_message": "",
        "telegram_token": _parse_cli_telegram_token() or None,
        "ai_enabled": True,
    }

    prompts = load_prompts()
    print_banner("No Provider", "No Model")

    startup_mode = choose_startup_mode()
    if startup_mode == "editor":
        farg = input("  File to open (created if it doesn't exist): ").strip()
        if farg:
            handle_view_editor(farg, None, None, None, session["history"], session=session)
        print(dim("  Dropping into the full chat + command experience now.\n"))
    elif startup_mode == "ai_only":
        ensure_ai_ready(session)
        result = run_ai_only_chat(session)
        if result != "full":
            return
        print_banner(session["provider"]["name"], session["model"])
    elif startup_mode == "chat":
        ensure_ai_ready(session)

    while True:
        ai_badge = c(BGREEN,"●AI") if session.get("ai_enabled") else c(BRED,"●AI-off")
        term_badge = c(BCYAN," T") if ai_on_terminal else ""
        attached_badge = (c(BBLUE, f" [{len(attached_files)}f]") if attached_files else "")
        prompt_line = (
            f"{ai_badge}{term_badge}{attached_badge} "
            f"{c(BBLACK, os.path.basename(os.getcwd())+'/')}"
            f"{c(BBLUE+BOLD,'❯')} "
        )
        try:
            if 'pt_session' not in session:
                try:
                    cmd_dict = _init_commands()
                except:
                    cmd_dict = {}
                completer = CommandPaletteCompleter(cmd_dict)
                session['pt_session'] = PromptSession(completer=completer, complete_while_typing=True, auto_suggest=AutoSuggestFromHistory())
                
            try:
                user_input = session['pt_session'].prompt(ANSI(prompt_line)).strip()
            except TypeError:
                user_input = input(prompt_line).strip()
                
            if user_input in ["/", "/ ", "!find"]:
                user_input = get_path_interactively() or ""
        except (EOFError, KeyboardInterrupt):
            print(c(BBLACK,"\n  Goodbye!\n"))
            break

        if not user_input:
            continue

        if dispatch_command(user_input, session, prompts, via_telegram=False) == "exit":
            break



# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND PALETTE COMPLETER (prompt_toolkit)
# ═══════════════════════════════════════════════════════════════════════════════

class CommandPaletteCompleter(Completer):
    def __init__(self, cmd_dict):
        self.cmd_dict = cmd_dict

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('/'):
            word = text.lower()  # word includes the slash
            for cmd, desc in self.cmd_dict.items():
                if not cmd.startswith('/'):
                    continue
                if not word or word in cmd.lower() or word[1:] in desc.lower():
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc,
                    )
        else:
            word = document.get_word_before_cursor(WORD=False)
            for cmd, desc in self.cmd_dict.items():
                if cmd.lower().startswith(word.lower()) and word:
                    yield Completion(
                        cmd,
                        start_position=-len(word),
                        display_meta=desc,
                    )


def get_path_interactively(start_path="."):
    # global shutil
    current_dir = os.path.abspath(start_path)
    selected_idx = [0]
    entries = [[]]
    error_msg = [""]

    def refresh_entries():
        try:
            items = sorted(os.listdir(current_dir))
            error_msg[0] = ""
        except PermissionError:
            items = []
            error_msg[0] = " (Permission Denied)"
        except OSError as e:
            items = []
            error_msg[0] = f" (Error: {e})"
        
        entries[0] = [".."] + items
        selected_idx[0] = 0

    refresh_entries()

    def get_formatted_text():
        term_h = shutil.get_terminal_size().lines
        max_items = max(5, term_h - 7)
        
        start_idx = max(0, selected_idx[0] - max_items // 2)
        end_idx = start_idx + max_items
        if end_idx > len(entries[0]):
            end_idx = len(entries[0])
            start_idx = max(0, end_idx - max_items)
            
        lines = [("class:title", f" 📂 {current_dir}{error_msg[0]} \n")]
        
        hint = " ↑↓: Move | Enter/→: Select | ←: Back | h: Home | s: Storage | q: Quit"
        lines.append(("class:hint", f" {hint}  [{selected_idx[0]+1}/{len(entries[0])}]\n\n"))
        
        for i in range(start_idx, end_idx):
            e = entries[0][i]
            full = os.path.join(current_dir, e)
            is_dir = os.path.isdir(full) or e == ".."
            icon = "📁 " if is_dir else "📄 "
            if i == selected_idx[0]:
                lines.append(("class:selected", f"  ❯ {icon}{e}\n"))
            else:
                lines.append(("class:entry", f"    {icon}{e}\n"))
        return lines

    text_ctrl = FormattedTextControl(get_formatted_text)
    layout = Layout(HSplit([Window(content=text_ctrl)]))
    kb = KeyBindings()

    @kb.add("up")

    @kb.add("up")
    def _up(event):
        selected_idx[0] = (selected_idx[0] - 1) % max(1, len(entries[0]))

    @kb.add("down")
    def _down(event):
        selected_idx[0] = (selected_idx[0] + 1) % max(1, len(entries[0]))

    @kb.add("enter")
    @kb.add("right")
    def _enter(event):
        nonlocal current_dir
        if not entries[0]:
            event.app.exit(result=current_dir)
            return
        chosen = entries[0][selected_idx[0]]
        full = os.path.normpath(os.path.join(current_dir, chosen))
        if os.path.isdir(full):
            current_dir = full
            refresh_entries()
        else:
            event.app.exit(result=full)

    @kb.add("left")
    def _left(event):
        nonlocal current_dir
        current_dir = os.path.dirname(current_dir)
        refresh_entries()
        
    @kb.add("h")
    def _home(event):
        nonlocal current_dir
        current_dir = os.path.expanduser("~")
        refresh_entries()
        
    @kb.add("s")
    def _storage(event):
        nonlocal current_dir
        storage_path = "/storage/emulated/0"
        if os.path.exists(storage_path):
            current_dir = storage_path
        elif os.path.exists(os.path.expanduser("~/storage")):
            current_dir = os.path.expanduser("~/storage")
        refresh_entries()

    @kb.add("c-c")
    @kb.add("escape")
    @kb.add("q")
    def _cancel(event):
        event.app.exit(result=None)

    _style = Style.from_dict({
        "title":    "fg:cyan bold",
        "hint":     "fg:ansigray",
        "selected": "fg:black bg:ansicyan bold",
        "entry":    "fg:white",
    })

    app = Application(layout=layout, key_bindings=kb, style=_style, full_screen=True, refresh_interval=0.05)
    return app.run()



def _init_commands():
    cmds = {}
    for line in HELP_TEXT.splitlines():
        if "{C}" in line and "{R}" in line:
            m = re.search(r"\{C\}(.*?)\{R\}\s*(.*)", line)
            if m:
                cmd = m.group(1).strip().split(" ")[0]
                desc = m.group(2).strip()
                if cmd != "(just type)":
                    cmds[cmd] = desc
    return cmds
if __name__ == "__main__":
    main()
