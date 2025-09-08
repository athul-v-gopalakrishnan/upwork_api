def get_cursor_tracking_script(x, y) -> str:
    """
    Returns a JS script that creates a black dot at (initial_x, initial_y),
    tracks the cursor movement, and exposes mouse position.
    Does not hide the native cursor.
    """
    return f"""
    (() => {{
        // Initialize mouse position
        window._mousePosition = {{ x: {x}, y: {y} }};

        // Avoid duplicates
        if (!document.getElementById('cursor-dot')) {{
            // Create dot
            const dot = document.createElement('div');
            dot.id = 'cursor-dot';
            Object.assign(dot.style, {{
                position: 'fixed',
                width: '18px',
                height: '18px',
                backgroundColor: 'black',
                borderRadius: '50%',
                pointerEvents: 'none',
                zIndex: '9999',
                transform: 'translate(-50%, -50%)',
                left: window._mousePosition.x + 'px',
                top: window._mousePosition.y + 'px'
            }});
            document.body.appendChild(dot);

            // Update position on mouse move
            window.addEventListener('mousemove', (event) => {{
                window._mousePosition.x = event.clientX;
                window._mousePosition.y = event.clientY;
                dot.style.left = event.clientX + 'px';
                dot.style.top = event.clientY + 'px';
            }});
        }}

        // Expose mouse position getter
        window.getMousePosition = () => window._mousePosition;
    }})();
    """

if __name__== "__main__":
    print(generate_cursor_tracking_script(200, 300))