# Code With AI - Integration Patches

## Overview
This document provides specific code patches to integrate all enhancements into the original `code_with_ai.py`.

## Patch 1: Add Enhanced Imports (After line 41)

**Location:** After `except ImportError: sys.exit(1)`

```python
# ─── Enhanced dependencies ─────────────────────────────────────────────
try:
    from pathlib import Path
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    from cryptography.hazmat.backends import default_backend
    import base64
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    Path = type('Path', (), {'exists': lambda s: False, 'read_text': lambda s: ''})
```

## Patch 2: Add Configuration System (After line 210)

**Location:** After `MAX_HISTORY_MESSAGES = 12` section

```python
# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENT CONFIGURATION WITH ENCRYPTION
# ═══════════════════════════════════════════════════════════════════════════════
CONFIG_FILE = os.path.expanduser("~/.code_ai_config.json")
ENCRYPTION_SALT = b'code_with_ai_salt_v1'

def _get_cipher():
    """Generate encryption cipher from machine-specific data"""
    if not HAS_CRYPTO:
        return None
    try:
        machine_id = Path("/etc/machine-id").read_text().strip() if Path("/etc/machine-id").exists() else socket.gethostname()
    except:
        machine_id = socket.gethostname()
    
    password = f"{machine_id}_{getpass.getuser()}".encode()
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ENCRYPTION_SALT,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return Fernet(key)

def encrypt_value(value: str) -> str:
    """Encrypt sensitive value"""
    if not HAS_CRYPTO:
        return value
    try:
        cipher = _get_cipher()
        return cipher.encrypt(value.encode()).decode()
    except:
        return value

def decrypt_value(encrypted: str) -> str:
    """Decrypt sensitive value"""
    if not HAS_CRYPTO:
        return encrypted
    try:
        cipher = _get_cipher()
        return cipher.decrypt(encrypted.encode()).decode()
    except:
        return encrypted

def load_config() -> dict:
    """Load configuration with encrypted API keys"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                if "providers" in config:
                    for provider_key, provider_data in config["providers"].items():
                        if "api_key" in provider_data and provider_data["api_key"]:
                            provider_data["api_key"] = decrypt_value(provider_data["api_key"])
                if "custom_endpoints" in config:
                    for endpoint in config["custom_endpoints"]:
                        if "api_key" in endpoint and endpoint["api_key"]:
                            endpoint["api_key"] = decrypt_value(endpoint["api_key"])
                return config
        except Exception:
            return {}
    return {}

def save_config(config: dict):
    """Save configuration with encryption"""
    config_copy = json.loads(json.dumps(config))
    if "providers" in config_copy:
        for provider_key, provider_data in config_copy["providers"].items():
            if "api_key" in provider_data and provider_data["api_key"]:
                provider_data["api_key"] = encrypt_value(provider_data["api_key"])
    if "custom_endpoints" in config_copy:
        for endpoint in config_copy["custom_endpoints"]:
            if "api_key" in endpoint and endpoint["api_key"]:
                endpoint["api_key"] = encrypt_value(endpoint["api_key"])
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_copy, f, indent=2)
    except Exception:
        pass

def get_stored_api_key(provider_key: str, config: dict) -> str:
    """Get stored API key for provider"""
    return config.get("providers", {}).get(provider_key, {}).get("api_key", "")

def store_api_key(provider_key: str, api_key: str, config: dict):
    """Store API key for provider"""
    if "providers" not in config:
        config["providers"] = {}
    if provider_key not in config["providers"]:
        config["providers"][provider_key] = {}
    config["providers"][provider_key]["api_key"] = api_key
    save_config(config)

def get_last_used_model(provider_key: str, config: dict) -> str:
    """Get last used model for provider"""
    return config.get("providers", {}).get(provider_key, {}).get("last_model", "")

def store_last_used_model(provider_key: str, model: str, config: dict):
    """Store last used model for provider"""
    if "providers" not in config:
        config["providers"] = {}
    if provider_key not in config["providers"]:
        config["providers"][provider_key] = {}
    config["providers"][provider_key]["last_model"] = model
    config["providers"][provider_key]["last_used"] = time.time()
    save_config(config)
```

## Patch 3: Add Error Tracking Globals (After line 198)

**Location:** After `attached_files: dict = {}`

```python
# Error tracking (ENHANCED)
last_error_output: str = ""
last_error_locations: list = []
```

## Patch 4: Enhanced Error Extraction (Replace lines 1381-1407)

**Location:** Replace `_extract_error_locations` function

```python
def _extract_error_locations(output: str):
    """Enhanced error location extraction with line/column/file tracking"""
    global last_error_output, last_error_locations
    
    if not output:
        return []
    
    results = []
    
    # Pattern 1: file:line:col: error/warning: message
    for m in re.finditer(r'([^\s:()][^:\n]*):(\d+):(\d+):\s*(error|warning|fatal error|Error)?:?\s*(.+)', output):
        results.append({
            "file": m.group(1), "line": int(m.group(2)), "col": int(m.group(3)),
            "level": (m.group(4) or "error").lower(), "msg": m.group(5).strip()
        })
    
    if results:
        last_error_locations = results
        last_error_output = output
        return results
    
    # Pattern 2: file:line: error/warning: message
    for m in re.finditer(r'([^\s:()][^:\n]*):(\d+):\s*(error|warning|Error)?:?\s*(.+)', output):
        results.append({
            "file": m.group(1), "line": int(m.group(2)), "col": None,
            "level": (m.group(3) or "error").lower(), "msg": m.group(4).strip()
        })
    
    if results:
        last_error_locations = results
        last_error_output = output
        return results
    
    # PHP Parse error
    m = re.search(r'PHP Parse error:\s*(.+?) in (.+?) on line (\d+)', output)
    if m:
        results = [{"file": m.group(2), "line": int(m.group(3)), "col": None,
                   "level": "error", "msg": m.group(1).strip()}]
        last_error_locations = results
        last_error_output = output
        return results
    
    # Python traceback
    file_lines = re.findall(r'File "(.+?)", line (\d+)', output)
    if file_lines:
        f, ln = file_lines[-1]
        tail = [l for l in output.strip().splitlines() if l.strip()]
        msg = tail[-1] if tail else "error"
        results = [{"file": f, "line": int(ln), "col": None, "level": "error", "msg": msg}]
        last_error_locations = results
        last_error_output = output
        return results
    
    if re.search(r'\berror\b|\bError\b|\bfatal\b', output, re.IGNORECASE):
        last_error_output = output
    
    return []
```

## Patch 5: Add AI Error Solver (New function, before line 1152)

**Location:** Before `def handle_debug`

```python
def handle_ai_solve_errors(provider, model, api_key, history):
    """Ask AI to analyze and solve recent compilation/runtime errors"""
    global last_error_output, last_error_locations
    
    if not last_error_output:
        print(warn("  No recent errors to solve. Run some code first!\n"))
        return
    
    if not last_error_locations:
        prompt = (
            f"I encountered this error output:\n\n```\n{last_error_output[:2000]}\n```\n\n"
            "Please analyze the error and suggest how to fix it."
        )
    else:
        error_summary = "\n".join([
            f"- {e['file']}:{e['line']}" + (f":{e['col']}" if e.get('col') else "") + f" → {e['msg']}"
            for e in last_error_locations[:5]
        ])
        prompt = (
            f"I encountered these errors:\n\n{error_summary}\n\n"
            f"Full output:\n```\n{last_error_output[:2000]}\n```\n\n"
            "Please analyze and suggest specific fixes with code examples."
        )
    
    print(c(BBLUE, "\n  Asking AI to solve errors...\n"))
    send_message(provider, model, api_key, history, prompt)
```

## Patch 6: Update Editor with Run/Compile Commands (Line 748-888)

**Location:** In `handle_view_editor`, update the commands help text and add handlers

Find this line:
```python
        print(dim("  Commands: [e]dit line  [i]nsert  [d]elete line  [p]aste whole file  "
                  "[ai] ask AI  [v]iew again  [w]rite save  [q]uit"))
```

Replace with:
```python
        print(dim("  Commands: [e]dit  [i]nsert  [d]elete  [p]aste  [ai] AI  [r]un  [c]heck  [v]iew  [w]rite  [q]uit"))
```

Then add these handlers after the existing command handlers:

```python
        elif cmd in ("r", "run"):
            full = resolve_path(path)
            write_text_file(path, content)
            dirty = False
            handle_run(path)
            render()

        elif cmd in ("c", "check"):
            full = resolve_path(path)
            lang = detect_lang(path)
            ok_s, check_out = _run_syntax_check(lang, full)
            if ok_s:
                print(ok(f"  ✓ No syntax errors"))
            else:
                print(err(f"  ✗ Syntax errors found:"))
                _print_errors(_extract_error_locations(check_out), check_out)
```

## Patch 7: Add Custom Endpoints Management (New section, line ~1100)

**Location:** Add before `handle_explain`

```python
def list_custom_endpoints(config: dict):
    """List all custom endpoints"""
    endpoints = config.get("custom_endpoints", [])
    if not endpoints:
        print(warn("  No custom endpoints configured.\n"))
        return
    print(f"\n{header_bar('Custom Endpoints', BBLUE)}")
    for i, ep in enumerate(endpoints, 1):
        print(f"  {c(BCYAN, str(i))}. {c(BWHITE, ep['name'])}")
        print(f"     {dim(ep['endpoint'])}")
        print(f"     Type: {ep.get('type', 'openai')} | Models: {len(ep.get('models', []))}")
    print()

def add_custom_endpoint(config: dict):
    """Add a new custom API endpoint"""
    print(f"\n{header_bar('Add Custom Endpoint', BBLUE)}")
    name = input("  Endpoint name: ").strip()
    if not name:
        print(dim("  Cancelled.\n")); return
    
    endpoint_url = input("  API endpoint URL: ").strip()
    if not endpoint_url:
        print(dim("  Cancelled.\n")); return
    
    print("  API type: ")
    print("    1. OpenAI-compatible (default)")
    print("    2. Anthropic")
    print("    3. Gemini")
    print("    4. Cohere")
    api_type = input("  Choose (1-4, default 1): ").strip()
    type_map = {"1": "openai", "2": "anthropic", "3": "gemini", "4": "cohere"}
    api_type = type_map.get(api_type, "openai")
    
    api_key = getpass.getpass("  API key (optional, press Enter to skip): ").strip()
    default_model = input("  Default model name: ").strip() or "gpt-3.5-turbo"
    
    models = [default_model]
    if api_key and input("  Try to fetch available models? [Y/n]: ").strip().lower() != "n":
        try:
            models_url = endpoint_url.replace("/chat/completions", "/models")
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = _requests.get(models_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    models = [m["id"] for m in data["data"]]
                    print(ok(f"  Found {len(models)} models"))
        except:
            print(warn("  Could not fetch models automatically."))
    
    endpoint_data = {
        "name": name, "endpoint": endpoint_url, "type": api_type,
        "default_model": default_model, "api_key": api_key,
        "models": models, "custom": True
    }
    
    if "custom_endpoints" not in config:
        config["custom_endpoints"] = []
    config["custom_endpoints"].append(endpoint_data)
    save_config(config)
    print(ok(f"  Custom endpoint '{name}' added successfully.\n"))

def remove_custom_endpoint(config: dict):
    """Remove a custom endpoint"""
    endpoints = config.get("custom_endpoints", [])
    if not endpoints:
        print(warn("  No custom endpoints to remove.\n"))
        return
    
    list_custom_endpoints(config)
    choice = input("  Enter number to remove (or 0 to cancel): ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(endpoints):
        print(dim("  Cancelled.\n"))
        return
    
    removed = endpoints.pop(int(choice) - 1)
    config["custom_endpoints"] = endpoints
    save_config(config)
    print(ok(f"  Removed '{removed['name']}'.\n"))
```

## Patch 8: Add Commands to Dispatcher (After line 2417)

**Location:** In `dispatch_command`, add these before the "Default: send to AI" section (before line 2566)

```python
    # ── Error solving (NEW) ────────────────────────────────────────────────
    if lower == "ai-solve-errors":
        handle_ai_solve_errors(prov, mod, key, hist); return None
    if lower == "ai-clear-errors":
        global last_error_output, last_error_locations
        last_error_output = ""
        last_error_locations = []
        print(ok("  Error history cleared.\n")); return None
    
    # ── Custom endpoints (NEW) ─────────────────────────────────────────────
    if lower == "ai-endpoint-add":
        config = load_config()
        add_custom_endpoint(config); return None
    if lower == "ai-endpoint-list":
        config = load_config()
        list_custom_endpoints(config); return None
    if lower == "ai-endpoint-remove":
        config = load_config()
        remove_custom_endpoint(config); return None
```

## Patch 9: Update Help Text (Line ~2172)

**Location:** In HELP_TEXT, add these sections:

```python
{B}ERROR SOLVING (NEW){R}
  {C}ai-solve-errors{R}      Analyze and solve last compilation/runtime errors
                     with AI suggestions and code fixes
  {C}ai-clear-errors{R}      Clear error history

{B}CUSTOM API ENDPOINTS (NEW){R}
  {C}ai-endpoint-add{R}      Add a custom API endpoint (OpenAI-compatible,
                     Anthropic, Gemini, or Cohere)
  {C}ai-endpoint-list{R}     List all custom endpoints
  {C}ai-endpoint-remove{R}   Remove a custom endpoint
```

## Patch 10: Update Main Function (Line 2587)

**Location:** At the very start of `main()`, load config

Add after `global ai_on_terminal`:
```python
    global ai_on_terminal
    
    # Load persistent configuration
    config = load_config()
```

And before provider selection, use stored keys:
```python
    # Try to use stored API key
    stored_key = get_stored_api_key(provider_key, config)
    if stored_key:
        api_key = stored_key
    else:
        api_key = get_api_key_for(provider)
```

And after model selection, store choices:
```python
    store_api_key(provider_key, api_key, config)
    store_last_used_model(provider_key, model, config)
```

## Integration Instructions

1. **Backup original:**
   ```bash
   cp code_with_ai.py code_with_ai.py.backup
   ```

2. **Apply patches in order:**
   - Patch 1: Imports
   - Patch 2: Configuration system
   - Patch 3: Globals
   - Patch 4-10: Features in order

3. **Install dependencies:**
   ```bash
   pip install cryptography
   ```

4. **Test:**
   ```bash
   python code_with_ai.py
   ```

5. **Verify features work:**
   ```
   ai-endpoint-list
   ai-solve-errors  (should say no errors yet)
   ai-run test.py   (then ai-solve-errors)
   ```

## Minimal Integration

If applying patches manually is complex, you can:

1. Keep original untouched
2. Use enhanced version alongside
3. Copy individual functions as needed

The features are designed to be modular and backward-compatible.

---

**All features are optional and additive - existing code continues to work unchanged.**
