#!/bin/bash
set -e

echo "Setting up 'cwai' universal command..."
chmod +x "$(pwd)/code_with_ai.py"

BIN_DIR="${PREFIX:-/usr}/bin"
if [ ! -w "$BIN_DIR" ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

ln -sf "$(pwd)/code_with_ai.py" "$BIN_DIR/cwai"

echo "Done! You can now run 'cwai' from any folder to start Code With AI."
