# Code With AI - Enhancements Implementation Guide

## Overview
This document describes all enhancements added to Code With AI, including implementation details and usage instructions.

## New Features Implemented

### 1. Local API Key Storage (Encrypted)
**File:** `~/.code_ai_config.json`  
**Encryption:** Fernet (when cryptography library available)  
**Fallback:** Plain JSON (with warning)

**What it does:**
- Stores API keys securely on your device
- Uses machine-specific encryption (hostname + username)
- Automatically loads saved keys on startup
- No need to re-enter keys every session

**Installation:**
```bash
pip install cryptography
```

**Usage:**
- Keys are automatically saved when you enter them
- Config file is created on first run
- To clear: delete `~/.code_ai_config.json`

### 2. Model Memory
**What it does:**
- Remembers the last model you used for each provider
- Highlights last-used model with ★ in selection menu
- Tracks when each model was last used

**Usage:**
- Your last-used model appears with a green star (★)
- Just press Enter to use it again
- Models are sorted by recent usage

### 3. Auto Model Detection
**What it does:**
- Fetches available models from API endpoints automatically
- Works with OpenAI-compatible APIs
- Caches models to avoid repeated fetches

**Usage:**
- When adding custom endpoint, choose "fetch models"
- Works with any API that supports `/v1/models`
- Falls back to manual entry if auto-fetch fails

### 4. Enhanced Startup Menu
**What it does:**
- Choose your preferred mode on launch
- Remembers your last choice
- Three modes: Code Editor / Full Chat / AI-only

**Usage:**
```
1. Code Editor   — Jump straight to editing a file
2. Chat with AI  — Full experience (recommended)
3. AI only       — Just chat, no file commands
```

**Remember choice:**
```bash
python code_with_ai.py --remember-mode
```

### 5. Enhanced Error Detection
**What it does:**
- Extracts exact error locations (file, line, column)
- Supports 10+ compilers/interpreters
- Stores errors for AI analysis

**Supported formats:**
- GCC/G++/Clang: `file.c:10:5: error: message`
- Rustc: `error[E0308]: --> src/main.rs:10:5`
- Python: `File "script.py", line 10`
- Node.js: `file.js:10:5`
- Java: `Main.java:10: error: message`
- Go: `file.go:10:5: error message`
- PHP: `Parse error: ... in file.php on line 10`

**What you get:**
- File name
- Line number
- Column number (when available)
- Error level (error/warning)
- Full error message

### 6. AI Error Solver ⭐ NEW
**Command:** `ai-solve-errors`

**What it does:**
- Analyzes your last compilation/runtime errors
- Provides specific fix suggestions with code examples
- Works with all error formats

**Usage:**
```bash
# Run your code (errors occur)
ai-run buggy.py

# Ask AI to solve the errors
ai-solve-errors
```

**Example workflow:**
```
ai-run main.c
  ✗ main.c — line 10, col 5 (error)
      undeclared identifier 'cout'

ai-solve-errors
  ╭─ AI ─────────────
  The error shows 'cout' is undeclared. This is a C file
  but you're using C++ syntax. Solutions:
  
  1. Rename to main.cpp, or
  2. Use printf instead:
     printf("Hello\n");
  ╰───────────────────
```

### 7. Custom API Endpoints ⭐ NEW
**Commands:**
- `ai-endpoint-add` — Add new endpoint
- `ai-endpoint-list` — List all custom endpoints
- `ai-endpoint-remove` — Remove endpoint

**What it does:**
- Connect to any OpenAI-compatible API
- Support for Anthropic, Gemini, Cohere formats
- Encrypted API key storage
- Auto-fetch available models

**Supported API types:**
1. OpenAI-compatible (LM Studio, Ollama, vLLM, etc.)
2. Anthropic format
3. Google Gemini format
4. Cohere format

**Usage example:**
```
ai-endpoint-add
  Endpoint name: Local Ollama
  API endpoint URL: http://localhost:11434/v1/chat/completions
  API type: 1 (OpenAI-compatible)
  API key: [optional]
  Default model: llama3.2
  Try to fetch models? [Y/n]: y
  
  ✓ Custom endpoint 'Local Ollama' added successfully.
```

**Common endpoints:**
```bash
# LM Studio
http://localhost:1234/v1/chat/completions

# Ollama
http://localhost:11434/v1/chat/completions

# LocalAI
http://localhost:8080/v1/chat/completions

# vLLM
http://localhost:8000/v1/chat/completions
```

### 8. Integrated Editor Enhancements
**New commands in editor:**
- `r` — Run file directly (compile + execute)
- `c` — Check syntax/compile only
- Errors automatically forwarded to AI

**Usage in editor:**
```
ai-editor script.py
  [viewing code]
  
editor> r         # Run the file
  ✗ Error found at line 10
  Forward to AI for solving? [Y/n]: y
  
  ╭─ AI suggests ─────
  The issue is...
  ╰───────────────────
  
editor> w         # Save fix
editor> r         # Run again
  ✓ Success!
```

### 9. Multi-Language Expansion
**New languages added:**
- V (`v run`)
- F# (`.fs`, `.fsx`)
- Groovy (`.groovy`)
- Pascal (`.pas`, `.pp`)
- D (`.d`)

**Total supported: 45+ languages**

### 10. Error Tracking for AI
**What it does:**
- Every compile/run error is tracked
- AI can reference errors in follow-up questions
- Persistent across commands

**Usage:**
```bash
ai-run broken.cpp
  # Errors appear

# Later, even after other commands:
How do I fix that compilation error?
  # AI remembers and references it
```

## Configuration File Structure

**Location:** `~/.code_ai_config.json`

**Structure:**
```json
{
  "providers": {
    "anthropic": {
      "api_key": "encrypted_key_here",
      "last_model": "claude-sonnet-4-6",
      "last_used": 1727467200.0
    },
    "groq": {
      "api_key": "encrypted_key_here",
      "last_model": "llama-3.3-70b-versatile",
      "last_used": 1727380800.0
    }
  },
  "custom_endpoints": [
    {
      "name": "Local Ollama",
      "endpoint": "http://localhost:11434/v1/chat/completions",
      "type": "openai",
      "default_model": "llama3.2",
      "api_key": "",
      "models": ["llama3.2", "codellama", "mistral"],
      "custom": true
    }
  ],
  "startup_mode": "chat",
  "last_error_check": 1727467200.0
}
```

## New Commands Summary

### Configuration Commands
```bash
ai-config              # View current configuration
ai-config-reset        # Reset to defaults
```

### Endpoint Commands
```bash
ai-endpoint-add        # Add custom API endpoint
ai-endpoint-list       # List custom endpoints
ai-endpoint-remove     # Remove endpoint
```

### Error Commands
```bash
ai-solve-errors        # Ask AI to solve last errors
ai-clear-errors        # Clear error history
```

### Enhanced Existing Commands
```bash
ai-run <file>          # Now tracks all errors
ai-check <file>        # Enhanced error extraction
ai-debug <file>        # Works with stored errors
ai-editor <file>       # New: r, c commands
```

## Installation & Setup

### 1. Install Dependencies
```bash
# Required
pip install requests pygments

# For encryption (recommended)
pip install cryptography
```

### 2. First Run
```bash
python code_with_ai.py
```

The tool will:
1. Ask for provider selection
2. Prompt for API key (saved encrypted)
3. Ask for model (remembers choice)
4. Show startup mode menu
5. Create config file automatically

### 3. Verify Setup
```bash
# Check config was created
ls -la ~/.code_ai_config.json

# Inside the tool
ai-status
```

## Migration from Original Version

If you're upgrading from the original version:

1. **No data loss:** Old workflow works identically
2. **New features optional:** All enhancements are opt-in
3. **Config auto-created:** First run creates new config
4. **Keys auto-saved:** Enter once, saved forever

**Quick migration:**
```bash
# Keep old version as backup
cp code_with_ai.py code_with_ai_original.py

# Use enhanced version
python code_with_ai.py
```

## Security Notes

### API Key Encryption
- Uses Fernet symmetric encryption
- Key derived from machine-specific data
- Salt: Fixed per-installation
- **Security level:** Protects against casual inspection
- **Not suitable for:** Multi-user systems with untrusted users

### Recommendation
For maximum security:
```bash
# Use environment variables instead
export ANTHROPIC_API_KEY="your-key"
python code_with_ai.py
```

Or:
```bash
# Keep config file permissions tight
chmod 600 ~/.code_ai_config.json
```

## Troubleshooting

### Encryption errors
```bash
# If encryption fails
pip install --upgrade cryptography

# Or disable encryption (will warn)
rm ~/.code_ai_config.json
# Tool falls back to plain JSON
```

### Custom endpoint not working
```bash
# Test endpoint manually
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'

# Check models endpoint
curl http://localhost:11434/v1/models
```

### Model memory not working
```bash
# Clear and rebuild
rm ~/.code_ai_config.json
python code_with_ai.py
# Re-enter API keys
```

### Errors not being tracked
```bash
# Clear error cache
ai-clear-errors

# Run code again
ai-run test.py

# Check if errors stored
ai-solve-errors
```

## Performance Considerations

### Config File Size
- Typical size: 1-5 KB
- Grows with custom endpoints
- Negligible impact on startup

### Encryption Overhead
- First access: ~10-50ms (key derivation)
- Subsequent: <1ms (cached cipher)
- No impact on AI requests

### Model Fetching
- Only on endpoint addition
- Cached indefinitely
- Manual refresh: `ai-endpoint-refresh`

## Changelog

### v2.0 - Enhanced Edition (2026-09-27)
- ✅ Local encrypted API key storage
- ✅ Model memory and highlighting
- ✅ Auto model detection from endpoints
- ✅ Enhanced startup menu with memory
- ✅ Advanced error detection (line, col, file)
- ✅ AI error solver command
- ✅ Custom API endpoint management
- ✅ Model loading from custom endpoints
- ✅ Integrated editor enhancements (r, c commands)
- ✅ Multi-language expansion (5 new languages)
- ✅ Enhanced error handling throughout

### v1.0 - Original
- Base functionality
- 8 providers
- File manager
- Code editor
- AI integration

## FAQ

**Q: Do I need to enter my API key every time?**  
A: No! It's saved encrypted and auto-loaded.

**Q: Can I use multiple custom endpoints?**  
A: Yes! Add as many as you want with `ai-endpoint-add`.

**Q: Does this work offline?**  
A: Editor and file features yes, AI features require internet (or local API).

**Q: How do I use with Ollama?**  
A: `ai-endpoint-add` → `http://localhost:11434/v1/chat/completions` → No API key needed.

**Q: Can I export/backup my config?**  
A: Yes! Copy `~/.code_ai_config.json`. Keys are encrypted to your machine.

**Q: How do I reset everything?**  
A: `rm ~/.code_ai_config.json` then restart.

## Support

For issues or questions:
1. Check this documentation
2. Review error messages (now more detailed!)
3. Use `ai-solve-errors` for code problems
4. Check GitHub issues

---

**Enhanced by the community, powered by AI** 🚀
