import tkinter as tk
from threading import Event

# Global variables
auto_mode_enabled = False
user_response_event = Event()
user_decision = None

def prompt_trade_decision(symbol, direction, confidence, reasons, timeout=180):
    """
    Prompts the user to approve or reject a trade using a Tkinter window.
    If no response in `timeout` seconds, the trade is skipped.
    """

    def approve():
        nonlocal root
        global user_decision
        user_decision = True
        user_response_event.set()
        root.destroy()

    def reject():
        nonlocal root
        global user_decision
        user_decision = False
        user_response_event.set()
        root.destroy()

    def auto_reject():
        if not user_response_event.is_set():
            print(f"[TIMEOUT] No response for {symbol} after {timeout}s — skipping.")
            reject()

    global user_decision
    user_decision = None
    user_response_event.clear()

    root = tk.Tk()
    root.title("Trade Confirmation")
    root.geometry("400x400")

    tk.Label(root, text=f"Pair: {symbol}", font=("Helvetica", 14)).pack(pady=5)
    tk.Label(root, text=f"Direction: {direction}", font=("Helvetica", 12)).pack()
    tk.Label(root, text=f"Confidence: {confidence}%", font=("Helvetica", 12)).pack()
    tk.Label(root, text="Reasons:", font=("Helvetica", 12, "underline")).pack(pady=10)

    reasons_text = "\n".join(reasons)
    text_widget = tk.Text(root, wrap=tk.WORD, height=10, width=45)
    text_widget.insert(tk.END, reasons_text)
    text_widget.config(state=tk.DISABLED)
    text_widget.pack()

    tk.Button(root, text="Approve Trade", command=approve, bg="green", fg="white").pack(pady=10)
    tk.Button(root, text="Reject Trade", command=reject, bg="red", fg="white").pack()

    # Auto close after timeout
    root.after(timeout * 1000, auto_reject)
    root.mainloop()

    return user_decision


def toggle_auto_mode():
    """
    Toggles automatic mode ON/OFF through a small persistent interface.
    """
    def update_state():
        global auto_mode_enabled
        auto_mode_enabled = bool(auto_mode_var.get())

    root = tk.Tk()
    root.title("Auto Mode Control")
    root.geometry("200x100")

    auto_mode_var = tk.BooleanVar(value=False)
    check = tk.Checkbutton(root, text="Enable Auto Mode", variable=auto_mode_var, command=update_state)
    check.pack(pady=20)

    root.mainloop()
