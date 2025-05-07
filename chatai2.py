import pyautogui
import pyperclip
import time
import tkinter as tk
from tkinter import ttk
import threading
import queue

# --- Global Control Objects ---
pause_event = threading.Event()
stop_event = threading.Event()
status_queue = queue.Queue()

# --- Helper Functions ---

def check_events(pause_ev, stop_ev):
    """Checks for stop/pause events. Returns True if stopped."""
    if stop_ev.is_set():
        return True
    pause_ev.wait() # Blocks if pause_event is clear (paused)
    if stop_ev.is_set(): # Check again after wait
        return True
    return False

def controlled_sleep(duration, pause_ev, stop_ev, status_q=None, status_prefix=""):
    """
    Sleeps for duration, checking events frequently.
    Optionally updates status_q with a countdown timer.
    Returns True if completed, False if stopped early.
    """
    end_time = time.monotonic() + duration
    last_update_time = 0
    # Send initial countdown message immediately if applicable
    if status_q and status_prefix:
        initial_remaining = max(0, round(end_time - time.monotonic()))
        put_status(status_q, f"{status_prefix}{initial_remaining}s...")
        last_update_time = time.monotonic()

    while time.monotonic() < end_time:
        if check_events(pause_ev, stop_ev): return False # Stop requested

        current_time = time.monotonic()
        remaining_time = max(0, round(end_time - current_time))

        # Update status roughly every second if queue provided and time changed
        if status_q and status_prefix and (current_time - last_update_time >= 1.0):
            put_status(status_q, f"{status_prefix}{remaining_time}s...")
            last_update_time = current_time
            # Optimization: if remaining time is 0, we can break early after updating
            if remaining_time == 0:
                break

        # Sleep for a short interval to remain responsive
        # Ensure sleep doesn't overshoot the next potential update time
        actual_sleep = min(0.1, end_time - current_time, (last_update_time + 1.0) - current_time if status_prefix else 0.1)
        if actual_sleep > 0:
            time.sleep(actual_sleep)

    # Final check after loop
    if check_events(pause_ev, stop_ev): return False

    return True # Completed sleep


def press_keys(*keys):
    """Presses and releases a sequence of keys (used by automation_task)."""
    # No pause/stop check needed here as pyautogui calls are quick
    pyautogui.hotkey(*keys)
    time.sleep(0.1) # Short delay needed by pyautogui

def type_text(text):
    """Types text using pyautogui (used by automation_task)."""
    # No pause/stop check needed here as pyautogui calls are quick
    pyautogui.write(text, interval=0.01) # Faster interval
    time.sleep(0.1)

def copy_to_clipboard(text):
    """Copies text to the clipboard (used by automation_task)."""
    pyperclip.copy(text)
    time.sleep(0.1)

def put_status(q, message):
    """Safely puts a message into the status queue."""
    try:
        q.put_nowait(message)
    except queue.Full:
        print(f"Warning: Status queue full. Dropping message: {message}")


# --- Automation Logic ---

def automation_task(pause_ev, stop_ev, status_q):
    """The main automation sequence running in a separate thread."""
    try:
        # Step 2: ctrl + T
        put_status(status_q, "Opening new tab (Ctrl+T)...")
        if check_events(pause_ev, stop_ev): return
        press_keys('ctrl', 't')
        if not controlled_sleep(1, pause_ev, stop_ev): return

        # Step 3: Type URL 1
        put_status(status_q, "Typing ChatGPT URL...")
        if check_events(pause_ev, stop_ev): return
        type_text("https://chatgpt.com/")
        if not controlled_sleep(0.5, pause_ev, stop_ev): return

        # Step 4: Enter
        put_status(status_q, "Loading ChatGPT...")
        if check_events(pause_ev, stop_ev): return
        press_keys('enter')
        if not controlled_sleep(5, pause_ev, stop_ev): return # Page load

        # Step 5: Copy initial prompt
        put_status(status_q, "Copying initial prompt...")
        if check_events(pause_ev, stop_ev): return
        initial_prompt = "Hello"
        copy_to_clipboard(initial_prompt)
        if not controlled_sleep(0.2, pause_ev, stop_ev): return

        # Step 6: Paste
        put_status(status_q, "Pasting initial prompt...")
        if check_events(pause_ev, stop_ev): return
        press_keys('ctrl', 'v')
        if not controlled_sleep(0.5, pause_ev, stop_ev): return

        # Step 7: Enter and Wait with Countdown
        put_status(status_q, "Sending initial prompt...")
        if check_events(pause_ev, stop_ev): return
        press_keys('enter')
        if not controlled_sleep(60, pause_ev, stop_ev, status_q, "Waiting (ChatGPT)... "): return
        put_status(status_q, "Scrolling down on ChatGPT page...")
        if check_events(pause_ev, stop_ev): return
        pyautogui.scroll(-1000000) # Scroll down significantly
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        pyautogui.scroll(-1000000)
        
        if not controlled_sleep(0.5, pause_ev, stop_ev): return

        # Steps 8 & 9: Locate and Click ChatGPT Copy Button using Image Recognition
        put_status(status_q, "Locating ChatGPT Copy button (Image)...")
        if check_events(pause_ev, stop_ev): return
        try:
            copy_button_location = None
            attempts = 0
            while copy_button_location is None and attempts < 5:
                if check_events(pause_ev, stop_ev): return
                copy_button_location = pyautogui.locateOnScreen('chatgpt_copy.png', grayscale=True, confidence=0.9)
                if copy_button_location is None:
                    attempts += 1
                    if not controlled_sleep(0.5, pause_ev, stop_ev): return

            if copy_button_location:
                put_status(status_q, "Clicking ChatGPT Copy button...")
                if check_events(pause_ev, stop_ev): return
                copy_button_center = pyautogui.center(copy_button_location)
                pyautogui.click(copy_button_center)
                if not controlled_sleep(1, pause_ev, stop_ev): return # Wait briefly after click

                # <<< NEW: Move mouse to center after clicking copy >>>
                put_status(status_q, "Moving mouse to screen center...")
                if check_events(pause_ev, stop_ev): return
                screenWidth, screenHeight = pyautogui.size()
                pyautogui.moveTo(screenWidth / 2, screenHeight / 2, duration=0.2)
                if not controlled_sleep(0.2, pause_ev, stop_ev): return # Short pause after move
                # <<< END NEW >>>

            else:
                put_status(status_q, "Error: ChatGPT Copy button not found on screen after multiple attempts.")
                stop_ev.set()
                return

        except pyautogui.PyAutoGUIException as img_err:
             put_status(status_q, f"Error during image search (ChatGPT): {img_err}")
             stop_ev.set()
             return
        except FileNotFoundError:
             put_status(status_q, "Error: chatgpt_copy.png not found in script directory.")
             stop_ev.set()
             return

        # Step 10: ctrl + T
        put_status(status_q, "Opening new tab for DeepSeek...")
        if check_events(pause_ev, stop_ev): return
        press_keys('ctrl', 't')
        if not controlled_sleep(1, pause_ev, stop_ev): return

        # Step 11: Type URL 2
        put_status(status_q, "Typing DeepSeek URL...")
        if check_events(pause_ev, stop_ev): return
        type_text("https://chat.deepseek.com/")
        if not controlled_sleep(0.5, pause_ev, stop_ev): return

        # Step 12: Enter
        put_status(status_q, "Loading DeepSeek...")
        if check_events(pause_ev, stop_ev): return
        press_keys('enter')
        if not controlled_sleep(5, pause_ev, stop_ev): return # Page load

        # Step 13: Paste
        put_status(status_q, "Pasting prompt to DeepSeek...")
        if check_events(pause_ev, stop_ev): return
        press_keys('ctrl', 'v')
        if not controlled_sleep(0.5, pause_ev, stop_ev): return

        # Step 14: Enter and Wait with Countdown
        put_status(status_q, "Sending prompt to DeepSeek...")
        if check_events(pause_ev, stop_ev): return
        press_keys('enter')
        # Countdown handled by controlled_sleep
        if not controlled_sleep(60, pause_ev, stop_ev, status_q, "Waiting (DeepSeek)... "): return
        # Put next status message *after* sleep completes (if any)

        # --- Main Loop ---
        put_status(status_q, "Starting interaction loop...")
        while True:
            if stop_ev.is_set(): break

            # === DeepSeek Interaction (Copy Response) ===
            # Step 15: Navigate Copy Button (DeepSeek)
            put_status(status_q, "Navigating to DeepSeek Copy button...")
            if check_events(pause_ev, stop_ev): return
            pyautogui.keyDown('shift')
            for i in range(4):
                if check_events(pause_ev, stop_ev): return
                pyautogui.press('tab')
                if not controlled_sleep(0.2, pause_ev, stop_ev): return
            pyautogui.keyUp('shift')
            if not controlled_sleep(0.5, pause_ev, stop_ev): return

            # Step 16: Press Copy Button (DeepSeek)
            put_status(status_q, "Copying DeepSeek response...")
            if check_events(pause_ev, stop_ev): return
            press_keys('enter') # Deepseek might use Enter
            if not controlled_sleep(1, pause_ev, stop_ev): return

            # === Switch to ChatGPT ===
            # Step 17: Ctrl+Shift+Tab
            put_status(status_q, "Switching to ChatGPT tab...")
            if check_events(pause_ev, stop_ev): return
            press_keys('ctrl', 'shift', 'tab')
            if not controlled_sleep(1, pause_ev, stop_ev): return

            # === ChatGPT Interaction (Paste and Send) ===
            # Step 18: Refresh Page (ChatGPT)
            put_status(status_q, "Refreshing ChatGPT page (F5)...")
            if check_events(pause_ev, stop_ev): return
            pyautogui.press('f5')
            if not controlled_sleep(5, pause_ev, stop_ev): return # Page refresh

            # Step 19: Paste
            put_status(status_q, "Pasting DeepSeek response to ChatGPT...")
            if check_events(pause_ev, stop_ev): return
            press_keys('ctrl', 'v')
            if not controlled_sleep(0.5, pause_ev, stop_ev): return

            # Step 20: Enter, Wait with Countdown, Scroll
            put_status(status_q, "Sending prompt to ChatGPT...")
            if check_events(pause_ev, stop_ev): return
            press_keys('enter')
            if not controlled_sleep(60, pause_ev, stop_ev, status_q, "Waiting (ChatGPT)... "): return
            put_status(status_q, "Scrolling down on ChatGPT page...")
            if check_events(pause_ev, stop_ev): return
            pyautogui.scroll(-1000000) # Scroll down significantly
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            pyautogui.scroll(-1000000)
            
            if not controlled_sleep(0.5, pause_ev, stop_ev): return

            # === ChatGPT Interaction (Copy Response) ===
            # Steps 21 & 22: Locate and Click ChatGPT Copy Button using Image Recognition
            put_status(status_q, "Locating ChatGPT Copy button (Image)...")
            if check_events(pause_ev, stop_ev): return
            try:
                copy_button_location = None
                attempts = 0
                while copy_button_location is None and attempts < 5:
                    if check_events(pause_ev, stop_ev): return
                    copy_button_location = pyautogui.locateOnScreen('chatgpt_copy.png', grayscale=True, confidence=0.9)
                    if copy_button_location is None:
                        attempts += 1
                        if not controlled_sleep(0.5, pause_ev, stop_ev): return

                if copy_button_location:
                    put_status(status_q, "Clicking ChatGPT Copy button...")
                    if check_events(pause_ev, stop_ev): return
                    copy_button_center = pyautogui.center(copy_button_location)
                    pyautogui.click(copy_button_center)
                    if not controlled_sleep(1, pause_ev, stop_ev): return # Wait briefly after click

                    # <<< NEW: Move mouse to center after clicking copy >>>
                    put_status(status_q, "Moving mouse to screen center...")
                    if check_events(pause_ev, stop_ev): return
                    screenWidth, screenHeight = pyautogui.size()
                    pyautogui.moveTo(screenWidth / 2, screenHeight / 2, duration=0.2)
                    if not controlled_sleep(0.2, pause_ev, stop_ev): return # Short pause after move
                    # <<< END NEW >>>

                else:
                    put_status(status_q, "Error: ChatGPT Copy button not found on screen after multiple attempts.")
                    stop_ev.set()
                    return

            except pyautogui.PyAutoGUIException as img_err:
                 put_status(status_q, f"Error during image search (ChatGPT): {img_err}")
                 stop_ev.set()
                 return
            except FileNotFoundError:
                 put_status(status_q, "Error: chatgpt_copy.png not found in script directory.")
                 stop_ev.set()
                 return

            # === Switch to DeepSeek ===
            # Step 23: Ctrl+Tab
            put_status(status_q, "Switching to DeepSeek tab...")
            if check_events(pause_ev, stop_ev): return
            press_keys('ctrl', 'tab')
            if not controlled_sleep(1, pause_ev, stop_ev): return

            # === DeepSeek Interaction (Paste and Send) ===
            # Step 24: Refresh Page (DeepSeek)
            put_status(status_q, "Refreshing DeepSeek page (F5)...")
            if check_events(pause_ev, stop_ev): return
            pyautogui.press('f5')
            if not controlled_sleep(5, pause_ev, stop_ev): return # Page refresh

            # Step 25: Paste
            put_status(status_q, "Pasting ChatGPT response to DeepSeek...")
            if check_events(pause_ev, stop_ev): return
            press_keys('ctrl', 'v')
            if not controlled_sleep(0.5, pause_ev, stop_ev): return

            # Step 26: Enter and Wait with Countdown
            put_status(status_q, "Sending prompt to DeepSeek...")
            if check_events(pause_ev, stop_ev): return
            press_keys('enter')
            # Countdown handled by controlled_sleep
            if not controlled_sleep(60, pause_ev, stop_ev, status_q, "Waiting (DeepSeek)... "): return
            # Put next status message *after* sleep completes (if any)

            put_status(status_q, "Repeating loop...")
            if not controlled_sleep(1, pause_ev, stop_ev): return # Small delay before looping

    except Exception as e:
        put_status(status_q, f"Error in automation thread: {e}")
    finally:
        put_status(status_q, "Automation task finished.")
        # Ensure stop_event is set if the task finishes naturally or errors out
        stop_ev.set()

# --- GUI Class ---

class ControlWindow(tk.Tk):
    def __init__(self, pause_ev, stop_ev, status_q):
        super().__init__()
        self.pause_event = pause_ev
        self.stop_event = stop_ev
        self.status_queue = status_q

        self.title("Automation Control")
        self.geometry("350x100") # Adjusted size
        self.attributes("-topmost", True) # Keep window on top

        # Prevent resizing
        self.resizable(False, False)

        # Frame for buttons
        button_frame = ttk.Frame(self, padding="10 5 10 5")
        button_frame.pack(side=tk.TOP, fill=tk.X)

        # Buttons
        self.play_button = ttk.Button(button_frame, text="▶ Play", command=self.resume_automation, state=tk.DISABLED)
        self.pause_button = ttk.Button(button_frame, text="⏸ Pause", command=self.pause_automation)
        self.stop_button = ttk.Button(button_frame, text="❌ Stop", command=self.stop_automation)

        self.play_button.pack(side=tk.LEFT, padx=5, expand=True)
        self.pause_button.pack(side=tk.LEFT, padx=5, expand=True)
        self.stop_button.pack(side=tk.LEFT, padx=5, expand=True)

        # Status Label
        self.status_label = ttk.Label(self, text="Initializing...", padding="10 10 10 10", wraplength=330, justify=tk.LEFT)
        self.status_label.pack(side=tk.TOP, fill=tk.X, expand=True)

        # Set initial state
        self.pause_event.set() # Start in running state

        # Handle window closing
        self.protocol("WM_DELETE_WINDOW", self.stop_automation)

        # Start checking status queue
        self.update_status()

    def toggle_pause_buttons(self, is_paused):
        """Enable/disable play/pause buttons based on state."""
        if is_paused:
            self.pause_button.config(state=tk.DISABLED)
            self.play_button.config(state=tk.NORMAL)
        else:
            self.pause_button.config(state=tk.NORMAL)
            self.play_button.config(state=tk.DISABLED)

    def pause_automation(self):
        if self.pause_event.is_set(): # If running
            self.pause_event.clear() # Clear event to pause
            put_status(self.status_queue, "Automation Paused.")
            self.toggle_pause_buttons(True)

    def resume_automation(self):
        if not self.pause_event.is_set(): # If paused
            self.pause_event.set() # Set event to resume
            put_status(self.status_queue, "Automation Resumed.")
            self.toggle_pause_buttons(False)

    def stop_automation(self):
        if not self.stop_event.is_set():
            put_status(self.status_queue, "Stopping automation...")
            self.stop_event.set()
            # Ensure automation thread unblocks if paused
            if not self.pause_event.is_set():
                self.pause_event.set()
            # Disable buttons after stopping
            self.play_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            # Optionally close window after a short delay
            self.after(500, self.destroy)


    def update_status(self):
        """Checks the queue and updates the status label."""
        try:
            while True: # Process all messages in queue
                message = self.status_queue.get_nowait()
                self.status_label.config(text=message)
                if message == "Automation task finished." or "Stopping automation..." in message or "Error" in message:
                     self.stop_automation() # Trigger stop logic if task ends

        except queue.Empty:
            pass # No new messages

        # Schedule next check only if stop hasn't been requested
        if not self.stop_event.is_set():
            self.after(100, self.update_status)


# --- Main Execution ---

if __name__ == "__main__":
    print("Starting script...")
    print("Step 1: Switching to browser (Alt+Tab)...")
    pyautogui.hotkey('alt', 'tab')
    time.sleep(1.5) # Slightly longer sleep for window switch

    print("Setting up control window and automation thread...")
    # Set pause event initially (running state)
    pause_event.set()
    stop_event.clear()

    # Create and start the automation thread
    automation_thread = threading.Thread(
        target=automation_task,
        args=(pause_event, stop_event, status_queue),
        daemon=True # Allows main thread to exit even if this thread is running
    )
    automation_thread.start()

    # Create and run the GUI
    root = ControlWindow(pause_event, stop_event, status_queue)
    root.mainloop()

    print("GUI closed. Script finished.")
    # Ensure stop is signalled if GUI closes unexpectedly
    stop_event.set()
    # Give the automation thread a moment to recognize the stop signal
    time.sleep(0.5) 