import os
import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import win32con
import win32api
from PIL import Image, ImageTk, ImageSequence
import keyboard  # Add this import at the top
from pyvda import VirtualDesktop, AppView, get_virtual_desktops
import pystray
import threading
import time

class GifMinimizer:
    def __init__(self, root, hwnd=None):
        self.root = root
        self.hwnd = hwnd
        self.gif_path = "windowsfloat.gif"
        self.speed_multiplier = 1.5
        self.properties_shown = False
        self.minimized_windows = {}
        self.hidden_desktop = None
        self.original_desktop = None
        self.target_window = None
        self.animation_id = None  # Add this to track animation callbacks
        self.is_dragging = False  # Add this flag
        self.current_notification = None  # Add this to track active notifications
        
        # Create system tray icon
        self.setup_tray()
        
        # Replace the hotkey line with this:
        keyboard.on_press_key('e', self.check_hotkey, suppress=False)
        
        # Initially hide the window until hotkey is pressed
        self.root.withdraw()
        
        # Set window to not appear in taskbar or switcher
        self.root.wm_attributes("-toolwindow", 1)
        self.root.wm_attributes("-topmost", True)
        
        # Load GIF first to get dimensions
        if not self.load_gif():
            return
            
        # Then set up the GUI with the correct dimensions
        self.setup_gui()
        
        # Set default settings
        self.set_opacity(0.75)
        self.set_size((72, 90))
        
        # Start the animation
        self.animate_gif(0)
        
        # Add drag functionality
        self.setup_drag()
        
        # Start monitoring window state
        self.monitor_window_state()
        
        self.setup_virtual_desktop()

    def setup_gui(self):
        # Make the window always on top
        self.root.attributes('-topmost', True)
        
        # Remove window decorations
        self.root.overrideredirect(True)
        
        # Set transparent background
        self.root.wm_attributes("-transparentcolor", "white")
        
        # Create a canvas for the GIF with the correct dimensions
        self.canvas = tk.Canvas(
            self.root, 
            bg='white', 
            highlightthickness=0, 
            bd=0,
            width=self.gif_width,
            height=self.gif_height
        )
        self.canvas.pack()
        
        # Add hover binding
        self.canvas.bind("<Enter>", self.on_hover_enter)
        self.canvas.bind("<Leave>", self.on_hover_leave)
        
        # Add right-click menu
        self.setup_menu()

    def setup_tray(self):
        """Setup system tray icon and menu"""
        # Load all frames for tray animation
        self.tray_frames = []
        with Image.open(self.gif_path) as gif:
            # Get frame duration (in milliseconds)
            self.frame_duration = gif.info.get('duration', 100)  # default to 100ms if not specified
            
            for frame in ImageSequence.Iterator(gif):
                # Convert frame to RGBA and resize to larger tray icon size
                frame = frame.convert('RGBA')
                frame = frame.resize((32, 32), Image.Resampling.LANCZOS)
                self.tray_frames.append(frame)

        # Create tray icon menu with just Exit option
        menu = (
            pystray.MenuItem("Exit", self.exit_app),
        )

        # Create tray icon with first frame
        self.tray_icon = pystray.Icon(
            "GifMinimizer",
            self.tray_frames[0],
            "Windows FLoat",
            menu
        )

        # Start animation thread
        self.tray_animation_running = True
        self.tray_animation_thread = threading.Thread(target=self.animate_tray_icon)
        self.tray_animation_thread.daemon = True
        self.tray_animation_thread.start()

        # Run the tray icon detached
        self.tray_icon.run_detached()

    def animate_tray_icon(self):
        """Animate the tray icon by cycling through frames"""
        frame_index = 0
        while self.tray_animation_running:
            # Update icon with current frame
            self.tray_icon.icon = self.tray_frames[frame_index]
            
            # Move to next frame
            frame_index = (frame_index + 1) % len(self.tray_frames)
            
            # Wait for frame duration
            time.sleep(self.frame_duration / 1000)  # Convert ms to seconds

    def show_window(self, icon=None, item=None):
        """Show the main window from tray"""
        self.root.deiconify()
        self.root.lift()

    def hide_window(self, icon=None, item=None):
        """Hide the main window to tray"""
        self.root.withdraw()

    def setup_menu(self):
        # Create dark themed menu
        self.menu = tk.Menu(self.root, tearoff=0, bg="#333333", fg="white", 
                          activebackground="#444444", activeforeground="white")
        
        # Add Restore button at the top of the menu
        self.menu.add_command(
            label="Restore Window",
            command=self.restore_from_menu,
            foreground="#00ff00"
        )
        self.menu.add_separator()
        
        # Opacity submenu
        opacity_menu = tk.Menu(self.menu, tearoff=0, bg="#333333", fg="white", 
                          activebackground="#444444", activeforeground="white")
        for value in [5, 10, 15, 20, 25, 50, 75, 100]:
            opacity_menu.add_command(
                label=f"{value}%",
                command=lambda v=value: self.set_opacity(v/100)
            )
        self.menu.add_cascade(label="Opacity", menu=opacity_menu)
        
        # Size submenu
        size_menu = tk.Menu(self.menu, tearoff=0, bg="#333333", fg="white", 
                           activebackground="#444444", activeforeground="white")
        for size in [(360, 450), (288, 360), (216, 270), (144, 180), (72, 90), (56, 70)]:
            size_menu.add_command(
                label=f"{size[0]}×{size[1]} px",
                command=lambda s=size: self.set_size(s)
            )
        self.menu.add_cascade(label="Size", menu=size_menu)
        
        # Speed submenu
        speed_menu = tk.Menu(self.menu, tearoff=0, bg="#333333", fg="white", 
                            activebackground="#444444", activeforeground="white")
        for speed in [0.25, 0.5, 1, 1.5, 2]:
            speed_menu.add_command(
                label=f"{speed}x",
                command=lambda s=speed: self.set_speed(s)
            )
        self.menu.add_cascade(label="Speed", menu=speed_menu)
        
        # Add exit option
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)
        
        # Bind right-click to show menu
        self.canvas.bind("<Button-3>", self.show_menu)
        self.root.bind("<Button-1>", self.hide_menu)

    def show_menu(self, event):
        # Show menu at mouse position
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def hide_menu(self, event):
        # Hide the menu
        self.menu.unpost()

    def set_opacity(self, value):
        # Set window opacity
        self.root.attributes("-alpha", value)

    def set_size(self, size):
        # Set window size
        width, height = size
        self.root.geometry(f"{width}x{height}")
        self.canvas.config(width=width, height=height)
        self.gif_width, self.gif_height = width, height
        
        # Resize all frames of the GIF with edge preservation
        self.resized_frames = []
        for frame in ImageSequence.Iterator(self.gif):
            # Ensure the frame is in RGBA mode
            if frame.mode != 'RGBA':
                frame = frame.convert('RGBA')
            
            # Create a mask from the alpha channel
            mask = frame.split()[-1]
            
            # Resize the image with high-quality downscaling
            resized_img = frame.resize((width, height), Image.Resampling.LANCZOS)
            
            # Resize the mask separately
            resized_mask = mask.resize((width, height), Image.Resampling.LANCZOS)
            
            # Apply the mask to remove any semi-transparent edge pixels
            resized_img.putalpha(resized_mask.point(lambda p: 255 if p > 128 else 0))
            
            # Create new PhotoImage
            resized_frame = ImageTk.PhotoImage(resized_img)
            self.resized_frames.append(resized_frame)
        
        # Use the resized frames for animation
        self.frames = self.resized_frames
        self.animate_gif(0)  # Restart animation with new frames

    def load_gif(self):
        if not os.path.exists(self.gif_path):
            messagebox.showerror("Error", f"GIF file not found: {self.gif_path}")
            self.root.destroy()
            return False
            
        self.gif = Image.open(self.gif_path)
        self.gif_width, self.gif_height = self.gif.size
        
        # Convert frames to PhotoImage
        self.frames = []
        for frame in ImageSequence.Iterator(self.gif):
            if frame.mode != 'RGBA':
                frame = frame.convert('RGBA')
            photo = ImageTk.PhotoImage(frame)
            self.frames.append(photo)
            
        return True

    def animate_gif(self, frame_num):
        # Clear previous frame
        self.canvas.delete("all")
        
        # Update the GIF frame with proper transparency
        self.canvas.create_image(
            self.gif_width//2, 
            self.gif_height//2, 
            image=self.frames[frame_num], 
            anchor=tk.CENTER
        )
        
        # Calculate delay based on speed multiplier
        delay = int(self.gif.info['duration'] / self.speed_multiplier)
        
        # Store the animation ID so we can cancel it later
        self.animation_id = self.root.after(delay, self.animate_gif, (frame_num + 1) % len(self.frames))

    def minimize_to_gif(self, hwnd):
        # Minimize the window
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        
        # Store the window handle
        self.minimized_windows[hwnd] = True

    def restore_window(self, hwnd):
        # Restore the window
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        
        # Remove from minimized list
        if hwnd in self.minimized_windows:
            del self.minimized_windows[hwnd]

    def setup_drag(self):
        # Variables to store drag start position
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        # Add double-click to restore window
        self.canvas.bind("<Double-Button-1>", lambda e: self.restore_from_menu())

    def start_drag(self, event):
        """Start dragging the window"""
        self.is_dragging = True
        # Destroy any existing notification when starting to drag
        self.destroy_notification()
        # Record the start position of the drag
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()
        self._drag_data["dragging"] = True

    def stop_drag(self, event):
        """Stop dragging the window"""
        self.is_dragging = False
        self._drag_data["dragging"] = False

    def on_drag(self, event):
        if self._drag_data["dragging"]:
            # Calculate new position
            x = event.x_root - self._drag_data["x"]
            y = event.y_root - self._drag_data["y"]
            self.root.geometry(f"+{x}+{y}")

    def set_speed(self, multiplier):
        # Adjust animation speed
        self.speed_multiplier = multiplier

    def exit_app(self, icon=None, item=None):
        """Exit the application cleanly"""
        # Stop GIF animation first
        if hasattr(self, 'animation_id'):
            try:
                self.root.after_cancel(self.animation_id)
                self.animation_id = None
            except:
                pass

        # Stop tray animation and wait for thread to finish
        self.tray_animation_running = False
        if hasattr(self, 'tray_animation_thread'):
            try:
                self.tray_animation_thread.join(timeout=1.0)
            except:
                pass

        # Stop and remove tray icon
        if hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except:
                pass

        try:
            # Stop any pending Tkinter events
            self.root.after_idle(self._destroy_app)
        except:
            pass

    def _destroy_app(self):
        """Helper method to destroy the app after all animations are stopped"""
        try:
            # Hide window first to prevent visual glitches
            self.root.withdraw()
            # Destroy all widgets
            for widget in self.root.winfo_children():
                widget.destroy()
            # Finally destroy the root window
            self.root.quit()
            self.root.destroy()
            # Force exit the program
            import sys
            sys.exit(0)
        except:
            pass

    def show_properties(self, text):
        if not self.properties_shown:
            self.canvas.create_text(
                self.gif_width//2, 
                self.gif_height//2, 
                text=text, 
                fill="white", 
                font=("Arial", 8),
                tags="properties"
            )
            self.properties_shown = True

    def hide_properties(self):
        self.canvas.delete("properties")
        self.properties_shown = False
        self.animate_gif(0)  # Restart animation

    def restore_from_menu(self):
        if self.target_window is not None:
            # Move window back to original desktop
            app_view = AppView(self.target_window)
            app_view.move(self.original_desktop)
            
            # Bring it to the foreground
            win32gui.SetForegroundWindow(self.target_window)
            
            # Hide the GIF window
            self.root.withdraw()
            
            # Clear the handle
            self.target_window = None

    def handle_hotkey(self):
        # Get the currently active window
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return
        
        # Get mouse position
        cursor_pos = win32gui.GetCursorPos()
        x, y = cursor_pos[0], cursor_pos[1]
        
        # If there's already a hidden window, restore it first
        if self.target_window is not None:
            try:
                # Move the previously hidden window back
                old_app_view = AppView(self.target_window)
                old_app_view.move(self.original_desktop)
                
                # Try to bring it to the foreground
                try:
                    win32gui.ShowWindow(self.target_window, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(self.target_window)
                except:
                    pass  # Ignore if window can't be brought to foreground
            except:
                pass  # Ignore if old window is no longer valid
        
        # Store the new window handle
        self.target_window = hwnd
        
        try:
            # Move new window to hidden desktop
            app_view = AppView(hwnd)
            app_view.move(self.hidden_desktop)
            
            # Schedule the Tkinter operations to run in the main thread
            self.root.after(0, self._show_gif_window, x, y, hwnd)
        except:
            # If we can't hide the new window, clear the target
            self.target_window = None

    def monitor_window_state(self):
        if self.target_window is not None:
            try:
                # Check if window exists and is visible on current desktop
                if win32gui.IsWindowVisible(self.target_window) and VirtualDesktop.current() == self.original_desktop:
                    # Hide the floating window
                    self.root.withdraw()
                    self.target_window = None
            except win32gui.error:
                # Window was closed
                self.root.withdraw()
                self.target_window = None
        
        # Check every 500ms
        self.root.after(500, self.monitor_window_state)

    def _show_gif_window(self, x, y, hwnd):
        # Show our GIF window at the same position
        self.root.deiconify()
        self.root.geometry(f"+{x}+{y}")
        
        # Store the window handle
        self.hwnd = hwnd
        
        # Get window title
        window_title = win32gui.GetWindowText(hwnd)
        
        # Create and show notification window
        self.show_notification(f"{window_title} floated", x, y + 20)  # 20 pixels below cursor
        
        # Load GIF and setup if not already done
        if not hasattr(self, 'frames'):
            if not self.load_gif():
                return
            self.setup_gui()
            self.set_opacity(0.75)
            self.set_size((72, 90))
            self.animate_gif(0)
            self.setup_drag()
            
            # Add hover binding
            self.canvas.bind("<Enter>", self.on_hover_enter)
            self.canvas.bind("<Leave>", self.on_hover_leave)

    def show_notification(self, text, x, y):
        """Show a temporary notification window"""
        # Destroy any existing notification first
        if self.current_notification and self.current_notification.winfo_exists():
            self.current_notification.destroy()
        
        notification = tk.Toplevel(self.root)
        notification.overrideredirect(True)
        notification.attributes('-topmost', True)
        notification.configure(bg='#333333')
        
        # Create label with padding
        label = tk.Label(
            notification,
            text=text,
            fg='white',
            bg='#333333',
            padx=10,
            pady=5,
            font=('Arial', 9)
        )
        label.pack()
        
        # Position the notification
        notification.geometry(f"+{x}+{y}")
        
        # Store current notification
        self.current_notification = notification
        
        # Auto-destroy after 2 seconds
        self.root.after(2000, self.destroy_notification)

    def destroy_notification(self):
        """Safely destroy the current notification"""
        if self.current_notification and self.current_notification.winfo_exists():
            self.current_notification.destroy()
            self.current_notification = None

    def on_hover_enter(self, event=None):
        """Show floating window info on hover"""
        if self.target_window and not self.is_dragging:
            try:
                window_title = win32gui.GetWindowText(self.target_window)
                
                # Get float window position and size
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                float_width = self.root.winfo_width()
                float_height = self.root.winfo_height()
                
                # Get screen dimensions
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                
                # Calculate notification position
                # Try positions in this order: above, below, right, left
                positions = [
                    (x, y - 30),  # above
                    (x, y + float_height + 5),  # below
                    (x + float_width + 5, y),  # right
                    (x - 200, y)  # left (assuming ~200px notification width)
                ]
                
                # Find first position that fits on screen
                for nx, ny in positions:
                    if (0 <= nx <= screen_width - 200 and  # 200px is approximate notification width
                        0 <= ny <= screen_height - 30):    # 30px is approximate notification height
                        self.show_notification(f"Float - {window_title}", nx, ny)
                        break
                else:
                    # If no position works, default to mouse cursor position
                    cursor_pos = win32gui.GetCursorPos()
                    self.show_notification(f"Float - {window_title}", cursor_pos[0], cursor_pos[1])
                    
            except:
                pass

    def on_hover_leave(self, event=None):
        """Clean up any hover-related displays"""
        # The notification will auto-destroy itself
        pass

    def setup_virtual_desktop(self):
        """Setup virtual desktop for hiding windows"""
        # Get current desktop
        self.original_desktop = VirtualDesktop.current()
        
        # Create new desktop for hiding windows
        desktops = get_virtual_desktops()
        if len(desktops) == 1:
            self.hidden_desktop = VirtualDesktop.create()
        else:
            # Use the second desktop if it exists
            self.hidden_desktop = desktops[1]

    def hide_target_window(self):
        """Hide the target window by moving it to another virtual desktop"""
        # Find the target window
        self.target_window = win32gui.FindWindow(None, self.target_window_title)
        if self.target_window:
            # Create AppView for the window
            app_view = AppView(self.target_window)
            # Move it to hidden desktop
            app_view.move(self.hidden_desktop)

    def show_target_window(self):
        """Show the target window by moving it back to the original desktop"""
        if self.target_window:
            app_view = AppView(self.target_window)
            app_view.move(self.original_desktop)
            # Bring window to front
            win32gui.SetForegroundWindow(self.target_window)

    def on_double_click(self, event):
        """Handle double click event"""
        # ... existing code ...
        self.show_target_window()

    def create_window(self):
        # ... existing code ...
        # After creating the window, hide the target
        self.hide_target_window()

    def check_hotkey(self, e):
        """Check if Win+Shift+E is pressed"""
        if keyboard.is_pressed('windows') and keyboard.is_pressed('shift'):
            self.handle_hotkey()

if __name__ == "__main__":
    root = tk.Tk()
    app = GifMinimizer(root)
    root.mainloop() 