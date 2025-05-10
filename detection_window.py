import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import detection
from services.tracking import PeopleTracker
from services.email import EmailService
from services.stations import StationManager
from services.config import ConfigManager
from services.violation import PPEViolationDetector
from threading import Thread, Lock
from queue import Queue
import time

cap = cv2.VideoCapture(1) 

# Set desired resolution (optional)
original_width = 1280  # Example resolution
original_height = 720
cap.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)

# Verify webcam opened
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

# Get actual resolution (may differ from requested)
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
video_width = int(actual_width)
video_height = int(actual_height)

# Window setup
padding = 20
window_width = video_width + 400
window_height = video_height + 250  # Increased height for better station display

# Tkinter init
root = tk.Tk()
root.title("SafeScan")
root.geometry(f"{window_width}x{window_height}")
root.minsize(window_width, window_height)  # Prevent window from shrinking
root.state('zoomed')

# Backend variables
font_style = ("Arial", 10)
station_selection_enabled = tk.BooleanVar(value=False)
frame_counter = 0
last_detection_result = None
last_person_count = 0
last_people_boxes = []
last_person_ids = []
TARGET_FPS = 15
FRAME_SKIP = 3  # Must match detection.py's skip value
MAX_QUEUE_SIZE = 2  # Number of frames to buffer
frame_queue = Queue(maxsize=2)  # Small buffer to prevent memory buildup
processing_lock = Lock()
last_processed_frame = None
processor_running = True

# Tracking history variables
tracker = PeopleTracker()

# Drawing variables
station_manager = StationManager()
rectangle_start = None

from services.config import ConfigManager
config = ConfigManager()
settings = config.load()

# Initialize UI variables
people_detect = tk.BooleanVar(value=settings["people"])
helmets_detect = tk.BooleanVar(value=settings["helmets"])
vests_detect = tk.BooleanVar(value=settings["vests"])
critical_var = tk.BooleanVar(value=False)


# Function definitions

def save_settings():
    config.save({
        "people": people_detect.get(),
        "helmets": helmets_detect.get(),
        "vests": vests_detect.get(),
    })
    print("Settings saved.")

def update_station_display():
    station_display.config(state="normal")
    station_display.delete(1.0, tk.END)
    if station_manager.rectangles:
        station_display.insert(tk.END, f"{len(station_manager.rectangles)} stations active")
    else:
        station_display.insert(tk.END, "Draw stations to begin tracking")
    station_display.config(state="disabled")

def toggle_station_selection():
    station_selection_enabled.set(not station_selection_enabled.get())
    update_station_display()
    if station_selection_enabled.get():
        station_button.config(text="📌 Station Selection: ON", relief=tk.SUNKEN, bg="#cce5ff")
    else:
        station_button.config(text="📌 Station Selection: OFF", relief=tk.RAISED, bg="#e1e1e1")

def remove_stations():
    station_manager.clear()
    update_station_display()
    station_text.set("Draw stations to begin tracking")
    print("All stations removed")

def record_click(event):
    if not station_selection_enabled.get():
        return
    
    if station_manager.rectangle_start is None:  # Use the manager's variable
        station_manager.rectangle_start = (event.x, event.y)
    else:
        rectangle_end = (event.x, event.y)
        station_manager.add_station(station_manager.rectangle_start, rectangle_end)
        station_manager.rectangle_start = None  # Reset

def show_history_window():
    history_window = tk.Toplevel(root)
    history_window.title("Tracking History")
    history_window.geometry("800x600")
    
    # Create table
    columns = ("ID", "Total Time", "Current Station", "Time in Station")
    history_table = ttk.Treeview(history_window, columns=columns, show="headings")
    
    for col in columns:
        history_table.heading(col, text=col)
        history_table.column(col, width=150, anchor="center")
    
    history_table.pack(fill="both", expand=True)
    
    # Add scrollbar
    scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=history_table.yview)
    scrollbar.pack(side="right", fill="y")
    history_table.configure(yscrollcommand=scrollbar.set)
    
    # Refresh button
    def refresh_table():
        history_table.delete(*history_table.get_children())
        for row in tracker.get_history_table_data():
            history_table.insert("", "end", values=row)
    
    refresh_btn = tk.Button(history_window, text="Refresh", command=refresh_table)
    refresh_btn.pack(pady=10)
    
    # Initial data load
    refresh_table()
    
def video_processing_thread():
    global processor_running, last_processed_frame, last_people_boxes
    
    while processor_running:
        try:
            ret, frame = cap.read()
            if not ret:
                continue
                
            frame = cv2.resize(frame, (video_width, video_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get detection results - now properly handles all 5 return values
            try:
                processed_frame, person_count, people_boxes, person_ids, ppe_data = detection.run_detection(
                    frame,
                    people_detect.get(),
                    helmets_detect.get(),
                    vests_detect.get()
                )
            except ValueError as e:
                print(f"Detection returned wrong number of values: {e}")
                continue

                
            # Update tracking and violation detection
            last_people_boxes = [(int((x1 + x2) // 2), int((y1 + y2) // 2)) 
                               for (x1, y1, x2, y2) in people_boxes]
            
            tracker.update(
                last_people_boxes,
                person_ids,
                [(start, end) for start, end in station_manager.rectangles],
                station_manager.station_names
            )
            
            # Check for PPE violations if detection is enabled
            if people_detect.get() and (helmets_detect.get() or vests_detect.get()):
                ppe_boxes = ppe_data[0] if ppe_data else None
                ppe_classes = ppe_data[1] if ppe_data else None
                
                violation_detector.update(
                    people_boxes,
                    person_ids,
                    ppe_boxes,
                    ppe_classes,
                    helmets_detect.get(),
                    vests_detect.get()
                )
                
                # Add visual indicators
                processed_frame = violation_detector.draw_violation_indicators(
                    processed_frame,
                    people_boxes,
                    person_ids
                )
            
            # Add stations to the frame
            processed_frame = station_manager.draw_stations(processed_frame)
            
            # Update global variables
            last_people_boxes = people_boxes
                        
            if frame_queue.qsize() < 2:
                frame_queue.put(processed_frame)
                
            time.sleep(0.01)
            
        except Exception as e:
            print(f"Processing error: {str(e)}")
            continue
            
def update_frame():
    try:
        if not frame_queue.empty():
            frame = frame_queue.get_nowait()
            
            # Update video display
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            video_label.imgtk = imgtk
            video_label.config(image=imgtk)
            people_count_label.config(text=f"👥 People Count: {len(last_people_boxes)}")
            
            # Critical operation logic
            if critical_var.get():  # Only if checkbox is checked
                if len(last_people_boxes) > 0:
                    border_frame.config(
                        highlightbackground="red",
                        highlightthickness=4,  # Thicker border
                        bg="red"
                    )
                    critical_warning.config(text="WARNING: PERSON DETECTED!")
                else:
                    border_frame.config(
                        highlightbackground="blue",
                        highlightthickness=2,  # Normal thickness
                        bg="blue"
                    )
                    critical_warning.config(text="")
            else:  # If checkbox isn't checked
                critical_warning.config(text="")
                border_frame.config(
                    highlightbackground="blue",
                    highlightthickness=2,
                    bg="blue"
                )
            
            # Update station counts - Fixed version
            if hasattr(station_manager, 'rectangles') and station_manager.rectangles:
                # Convert bounding boxes to center points
                people_positions = [(int((x1 + x2) // 2), int((y1 + y2) // 2)) 
                                  for (x1, y1, x2, y2) in last_people_boxes]
                counts_text = station_manager.get_station_counts_text(people_positions)
            else:
                counts_text = "Draw stations to begin tracking"
                
            station_display.config(state="normal")
            station_display.delete(1.0, tk.END)
            station_display.insert(tk.END, counts_text)
            station_display.config(state="disabled")

    
    finally:
        root.after(int(1000/TARGET_FPS), update_frame)

# Create main container frames
left_panel = tk.Frame(root, width=150, padx=10, bg="#f0f0f0")
left_panel.pack(side="left", fill="y", expand=False)

right_panel = tk.Frame(root)
right_panel.pack(side="right", fill="both", expand=True)

# Video frame container
video_container = tk.Frame(right_panel, width=video_width+4, height=video_height+4)
video_container.pack_propagate(False)
video_container.pack(pady=10, anchor='nw')

border_frame = tk.Frame(video_container, width=video_width, height=video_height,
                       bg="blue", highlightbackground="blue", highlightthickness=2)
border_frame.pack_propagate(False)
border_frame.pack()

video_label = tk.Label(border_frame)
video_label.pack()
video_label.lift()  # Bring to front

# Create sections in left panel
control_section = tk.LabelFrame(left_panel, text="🛠️ Controls", font=("Arial", 10, "bold"),
                               padx=5, pady=5, bg="#f0f0f0")
control_section.pack(fill="x", pady=5)

settings_section = tk.LabelFrame(left_panel, text="⚙️ Detection Settings", font=("Arial", 10, "bold"),
                               padx=5, pady=5, bg="#f0f0f0")
settings_section.pack(fill="x", pady=5)

critical_section = tk.LabelFrame(left_panel, text="⚠️ Critical Operation", font=("Arial", 10, "bold"),
                               padx=5, pady=5, bg="#f0f0f0")
critical_section.pack(fill="x", pady=5)

station_display_section = tk.LabelFrame(left_panel, text="📋 Station Status", font=("Arial", 10, "bold"),
                                padx=5, pady=5, bg="#f0f0f0")
station_display_section.pack(fill="x", expand=True, pady=5)  # Fill available space

email_section = tk.LabelFrame(left_panel, text="📧 Email Alerts", font=("Arial", 10, "bold"),
                            padx=5, pady=5, bg="#f0f0f0")
email_section.pack(fill="x", pady=5)

# UI Elements - Controls Section
station_button = tk.Button(control_section, text="📌 Station Selection: OFF",
                          command=toggle_station_selection,
                          width=0, font=font_style, bg="#e1e1e1")
station_button.pack(fill="x", pady=2)

remove_button = tk.Button(control_section, text="❌ Remove Stations",
                         command=remove_stations, width=0, font=font_style, bg="#ffcccc")
remove_button.pack(fill="x", pady=2)

save_button = tk.Button(control_section, text="💾 Save Stations",
                       command=station_manager.save, width=0, font=font_style, bg="#ccffcc")
save_button.pack(fill="x", pady=2)

history_button = tk.Button(control_section, text="📜 View History",
                          command=show_history_window, width=0, font=font_style, bg="#cce5ff")
history_button.pack(fill="x", pady=2)

# UI Elements - Settings Section
people_checkbox = tk.Checkbutton(settings_section, text="👥 Detect People",
                                variable=people_detect, command=save_settings,
                                font=font_style, bg="#f0f0f0", anchor="w")
people_checkbox.pack(fill="x", pady=2)

helmets_checkbox = tk.Checkbutton(settings_section, text="⛑️ Detect Helmets",
                                 variable=helmets_detect, command=save_settings,
                                 font=font_style, bg="#f0f0f0", anchor="w")
helmets_checkbox.pack(fill="x", pady=2)

vests_checkbox = tk.Checkbutton(settings_section, text="🦺 Detect Vests",
                               variable=vests_detect, command=save_settings,
                               font=font_style, bg="#f0f0f0", anchor="w")
vests_checkbox.pack(fill="x", pady=2)

# Critical operation checkbox
critical_checkbox = tk.Checkbutton(critical_section, text="Enable Critical Monitoring",
                                 variable=critical_var,
                                 font=font_style, bg="#f0f0f0", anchor="w")
critical_checkbox.pack(fill="x", pady=2)

# Warning label (initially empty)
critical_warning = tk.Label(critical_section, text="",
                           font=font_style, fg="red", bg="#f0f0f0",wraplength="140")
critical_warning.pack(fill="x", pady=2)

# Station display with scrollable text widget
station_text = tk.StringVar()
station_text.set("Draw stations to begin tracking")

people_count_frame = tk.Frame(left_panel, bg="#f0f0f0")
people_count_frame.pack(fill="x", pady=(0, 5))  # Small bottom padding

people_count_label = tk.Label(people_count_frame, 
                            text="👥 People Count: 0", 
                            font=("Arial", 12, "bold"),
                            bg="#f0f0f0")
people_count_label.pack(side="left", padx=5)

# Create a frame for the station display with fixed height
station_display_frame = tk.Frame(station_display_section, bg="white", relief="sunken", borderwidth=2, width = 150)
station_display_frame.pack(fill="both", expand=True)

station_display = tk.Text(station_display_frame, 
                        wrap=tk.WORD, 
                        font=font_style, 
                        bg="white", 
                        fg="black",
                        width = 30,
                        height = 8,
                        padx=5, 
                        pady=5)
station_display.pack(side="left", fill="both", expand=True)

# Add scrollbar
scrollbar = tk.Scrollbar(station_display_frame)
scrollbar.pack(side="right", fill="y")
station_display.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=station_display.yview)

email_status_label = tk.Label(
    email_section,
    text="",  # Initial empty text
    font=font_style,
    fg="black",
    bg="#f0f0f0",
    wraplength=280,  # Match station display width
    anchor="w",
    justify="left"
)
email_status_label.pack(fill="x", padx=5, pady=2)

# Email init
email_service = EmailService(
    sender="marwanhatem1234@gmail.com",
    receiver="marwanhatemalt1234@gmail.com",
    password="fgmyjbnplmmtcanv",
    status_label=email_status_label  # Pass the label for automatic updates
)

# PPE Violation Detector
violation_detector = PPEViolationDetector(email_service)

processor_running = True
processing_thread = Thread(target=video_processing_thread, daemon=True)
processing_thread.start()

def cleanup():
    global processor_running
    
    # Signal thread to stop
    processor_running = False
    
    # Wait for thread to finish (with timeout)
    if processing_thread.is_alive():
        processing_thread.join(timeout=1.0)
    
    # Release video capture
    cap.release()
    
    # Destroy window
    root.destroy()

# Event binding
video_label.bind("<Button-1>", record_click)

root.protocol("WM_DELETE_WINDOW", cleanup)

# Initialization
station_manager.load()

# Start video playback
update_frame()

# Run GUI
root.mainloop()