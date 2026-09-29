import os
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

def get_path_interactively(start_path="."):
    current_dir = os.path.abspath(start_path)
    selected_idx = 0
    entries = []
    
    def refresh_entries():
        nonlocal entries, selected_idx
        try:
            items = os.listdir(current_dir)
        except PermissionError:
            items = []
        entries = [".."] + sorted(items)
        selected_idx = 0

    refresh_entries()

    text_control = FormattedTextControl()

    def get_formatted_text():
        result = [("class:title", f" Select File/Folder: {current_dir} \n")]
        result.append(("", " Use Up/Down arrows to move. Enter to open. Esc/Ctrl-C to cancel.\n\n"))
        for i, e in enumerate(entries):
            full_path = os.path.join(current_dir, e)
            is_dir = os.path.isdir(full_path)
            icon = "📁 " if is_dir else "📄 "
            style = "class:selected" if i == selected_idx else "class:entry"
            if i == selected_idx:
                result.append((style, f"  > {icon}{e}  \n"))
            else:
                result.append((style, f"    {icon}{e}  \n"))
        return result

    text_control.text = get_formatted_text

    window = Window(content=text_control)
    layout = Layout(HSplit([window]))

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        nonlocal selected_idx
        selected_idx = (selected_idx - 1) % max(1, len(entries))
        text_control.text = get_formatted_text

    @kb.add("down")
    def _(event):
        nonlocal selected_idx
        selected_idx = (selected_idx + 1) % max(1, len(entries))
        text_control.text = get_formatted_text
        
    @kb.add("right")
    @kb.add("enter")
    def _(event):
        nonlocal current_dir
        if not entries:
            event.app.exit(result=current_dir)
            return
        chosen = entries[selected_idx]
        full_path = os.path.normpath(os.path.join(current_dir, chosen))
        if os.path.isdir(full_path):
            current_dir = full_path
            refresh_entries()
            text_control.text = get_formatted_text
        else:
            event.app.exit(result=full_path)

    @kb.add("c-c")
    @kb.add("escape")
    @kb.add("q")
    def _(event):
        event.app.exit(result=None)

    style = Style.from_dict({
        "title": "fg:cyan bold",
        "selected": "fg:black bg:cyan bold",
        "entry": "fg:white",
    })

    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=True)
    return app.run()

if __name__ == "__main__":
    print(get_path_interactively())
