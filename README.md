# Code With AI

A complete AI-powered coding IDE for your terminal. Built for Termux and any Python 3 environment, this tool brings professional development capabilities to your mobile device or desktop terminal.

## Features

### AI-Powered Development
- **Multi-Provider AI Support**: Works with 17 AI providers!
  - Anthropic Claude
  - Groq
  - Google Gemini
  - OpenAI
  - OpenRouter
  - Together AI
  - Mistral
  - Cohere
  - **Pollinations AI** (Free!)
  - **HuggingFace**
  - **GitHub Models**
  - **Cerebras**
  - **SambaNova**
  - **Hyperbolic**
  - **Novita AI**
  - **Chutes AI**
  - **Custom Provider** (Connect to any open-source local server. Auto-detects local models available at `http://127.0.0.1:20128/v1/models`!)
- **Hot-swap providers, models, and API keys** mid-session without restarting
- **Intelligent context management**: Attach files to chat context for AI-aware editing
- **AI code generation**: Create new files or edit existing ones with natural language
- **AI debugging**: Find bugs with exact line numbers and reasons

### Full-Featured Code Editor
- **Syntax highlighting** for 40+ languages (via Pygments)
- **In-terminal editor** with line editing, insertion, deletion
- **AI assistance inside the editor**: Ask questions or request rewrites without leaving
- **Multi-file management**: Open, create, delete, rename, copy files
- **Language detection**: Automatic syntax highlighting based on file extension

### Code Execution
- **Universal file runner**: Automatically detects and runs files with the correct tool
- **Compilation support**: gcc/g++ for C/C++, rustc for Rust
- **Pre-flight syntax checking**: Catches errors before execution
- **Fully interactive execution**: stdin/stdout/stderr work natively
- **Supported languages**: Python, JavaScript, TypeScript, Java, Kotlin, C, C++, Rust, Go, Ruby, PHP, Lua, Perl, R, Julia, Dart, Scala, Elixir, Nim, Zig, Bash, and more

### Web Development
- **Built-in localhost server**: Serve HTML/CSS/JS projects instantly
- **PHP support**: Executes PHP files via PHP's built-in server
- **Multiple servers**: Run several projects on different ports simultaneously
- **LAN access**: Optional 0.0.0.0 binding for testing on other devices

### File Operations
- **File manager**: List, tree view, navigation
- **Batch operations**: Zip/unzip, move, copy, rename
- **Format conversion**: Change file extensions with optional AI content conversion
- **Smart compression**: Built-in ZIP support, optional 7z

### Advanced Features
- **Terminal passthrough**: Run any shell command
- **Optional AI analysis** of terminal output
- **Telegram bot bridge**: Control the IDE from Telegram
- **Saved prompts**: Store frequently used AI prompts
- **Session persistence**: Provider, model, and key settings preserved
- **Request size management**: Smart history and context limits to avoid rate limits

## Installation

### Requirements
- Python 3.7 or higher
- `requests` library (required)
- `pygments` library (optional but highly recommended for syntax highlighting)

### Install Dependencies

```bash
pip install requests pygments
```

For Termux users:
```bash
pkg install python
pip install requests pygments
```

### Download and Run

```bash
# Download the script
wget https://raw.githubusercontent.com/YOUR_USERNAME/code-with-ai/main/code_with_ai.py

# Make it executable
chmod +x code_with_ai.py

# Run it
python code_with_ai.py
```

## Quick Start

1. **Launch the application**:
   ```bash
   python code_with_ai.py
   ```

2. **Choose an AI provider** (on first run):
   - Select from 8 providers
   - Enter your API key
   - Choose a model

3. **Start coding**:
   ```
   ai-new hello.py create a hello world script
   ai-run hello.py
   ```

4. **Chat with AI**:
   ```
   How do I read a CSV file in Python?
   ```

5. **Edit files with AI**:
   ```
   ai-edit hello.py add error handling
   ```

## Command Reference

### Chat & AI
- **Just type**: Send messages to AI
- `/ai` / `/noai`: Toggle AI responses
- `ai-status`: Show current provider/model/key
- `ai-provider`: Switch AI provider
- `ai-model`: Switch model
- `ai-key`: Update API key

### File Management
- `ai-ls [dir]`: List files with info
- `ai-tree [dir]`: Show folder tree
- `ai-cd <dir>`: Change directory
- `ai-mkdir <dir>`: Create folder
- `ai-file <file>`: Open file actions menu

### AI File Operations
- `ai-open <file>`: Attach file to AI context
- `ai-close <file|all>`: Detach files
- `ai-files`: List attached files
- `ai-new <file> [instructions]`: AI generates new file
- `ai-edit <file> [instructions]`: AI modifies file
- `ai-explain <file|dir> [-s|-l]`: AI explains code
- `ai-debug <file>`: AI finds bugs

### Code Editor
- `ai-editor <file>`: Open in-terminal editor
- `e-open <file>`: Quick editor access
- **Editor commands**:
  - `e`: Edit line
  - `i`: Insert line
  - `d`: Delete line
  - `p`: Paste entire file content
  - `ai`: Ask AI or request rewrite
  - `w`: Write/save
  - `q`: Quit

### Running Code
- `ai-run <file>`: Compile/check and run file
- `d-run <file>`: Same as ai-run

### Web Server
- `ai-serve [dir] [port] [host]`: Start localhost server
- `ai-serve :8080`: Shorthand for port
- `ai-stopserve [port]`: Stop server(s)

### File Operations
- `d-rename <file|dir>`: Rename
- `d-reformat <file>`: Change format/extension
- `d-zip <file|dir>`: Create archive
- `d-unzip <archive>`: Extract archive
- `d-move <file|dir>`: Move
- `d-copy <file|dir>`: Copy

### Terminal
- `!<command>`: Run shell command
- `ai-terminal`: Toggle AI analysis of terminal output

### Advanced
- `ai-telegram`: Connect to Telegram bot
- `tbot-token <token>`: Set Telegram bot token
- `ai-prompt-save`: Save frequently used prompt
- `ai-help`: Show full help

## Supported Languages

Python, JavaScript, TypeScript, Java, Kotlin, C, C++, C#, Go, Rust, Ruby, PHP, Swift, Objective-C, Bash, Zsh, PowerShell, HTML, CSS, SCSS, JSON, XML, YAML, TOML, SQL, Markdown, R, Julia, Lua, Perl, Dart, Scala, Vue, Elixir, Haskell, Clojure, Erlang, Nim, Zig, Terraform

## New Features (Latest Update)

### Session & Cost Management
- `ai-history [N]`: Show the last N (default 10) messages in the chat.
- `ai-clear`: Clear chat history to save tokens.
- `ai-retry`: Resend the last user message to the AI.
- `ai-cost`: Show estimated session token usage.

### Clipboard & External Web
- **Browser Copy Button**: In web terminals (ttyd), AI outputs are instantly copied to your clipboard via OSC 52.
- `ai-copy`: Copy the last AI reply to your clipboard via native tools (xclip, pbcopy, termux-clipboard-set).
- `ai-search <query>`: Search DuckDuckGo from the terminal, display the plain text results, and send them seamlessly to AI.

### Tools & Hosting
- `ai-template [name]`: Generate immediate project boilerplate for templates like `flask-app`, `telegram-bot`, `cli-tool`, `react-app`, and `fastapi`.
- `ai-replit-bot`: Designed for cloud hosting (like Replit). Starts a Keep-alive Web server on `:8080` while launching your Telegram bot bridge loop.
- `ai-git <subcmd>`: Direct shortcut mapped to your local git commands (`status`, `add`, `commit`, `push`, `log`, `diff`, `init`, `clone`).

## API Keys

Get your API keys from:
- **Anthropic**: console.anthropic.com/settings/keys
- **Groq**: console.groq.com/keys
- **Gemini**: aistudio.google.com/apikey
- **OpenAI**: platform.openai.com/api-keys
- **OpenRouter**: openrouter.ai/keys
- **Together AI**: api.together.ai/settings/api-keys
- **Mistral**: console.mistral.ai/api-keys
- **Cohere**: dashboard.cohere.com/api-keys

Set API keys via:
1. Environment variables (e.g., `ANTHROPIC_API_KEY`)
2. Interactive prompt on first use
3. `ai-key` command to change anytime

## Examples

### Generate a Web Server
```
ai-new server.py create a simple Flask web server with hello world endpoint
ai-run server.py
```

### Debug Existing Code
```
ai-open buggy_script.py
ai-debug buggy_script.py
```

### Serve a Website
```
ai-serve ./my-website :8080
# Visit http://localhost:8080
```

### Multi-File AI Chat
```
ai-open main.py
ai-open utils.py
How can I refactor the duplicate code in these files?
```

### Convert File Format
```
d-reformat script.sh
# Choose new extension: py
# AI converts bash to Python
```

## Telegram Bot Integration

Control the entire IDE from Telegram:

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your bot token
3. In the app: `tbot-token <your-token>`
4. Run: `ai-telegram`
5. Message your bot - all commands work identically!

## Tips

- **Attach files** before asking AI about them: `ai-open file.py`
- **Use short flags**: Many commands have aliases (e.g., `d-run` = `ai-run`)
- **Editor AI mode**: Press `ai` inside the editor to get help without leaving
- **Multiple servers**: Run different projects on different ports simultaneously
- **Smart context**: Tool automatically manages context size to avoid rate limits
- **Interactive execution**: All programs run with full stdin/stdout - input() and scanf work!

## License

MIT License - Feel free to use, modify, and distribute.

## Contributing

Contributions welcome! This is a single-file application for easy deployment and modification.

## Troubleshooting

### No syntax highlighting?
```bash
pip install pygments
```

### Command not found (Java, Kotlin, etc.)?
Install the respective compiler/interpreter:
```bash
# Termux examples
pkg install nodejs      # For JavaScript
pkg install openjdk-17  # For Java
pkg install rust        # For Rust
pkg install php         # For PHP
```

### Rate limits?
The tool automatically manages request size and retries 429 errors. If you hit limits:
- Use `ai-close all` to detach large files
- Switch to a different provider with `ai-provider`
- The tool only sends recent messages and caps context size

### Server won't start?
- Port busy: Tool auto-selects a free port
- Check with `ai-stopserve` to stop old servers

## Support

For issues, suggestions, or contributions, please open an issue on GitHub.

---

**Built with ❤️ for developers who code anywhere, anytime.**
