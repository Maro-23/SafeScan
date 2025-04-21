import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
import json
import smtplib
import ssl
from email.message import EmailMessage
import detection
import threading
import time
from services.tracking import PeopleTracker
from services.email import EmailService
from services.stations import StationManager

# Load video
video_path = "sample_vid1.mp4"
if not os.path.exists(video_path):
    print(f"Error: Video file '{video_path}' not found.")
    exit()

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open CCTV stream.")
    exit()

# Video dimensions
original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
video_width = original_width // 2
video_height = original_height // 2

# Window setup
padding = 20
window_width = video_width + 400
window_height = video_height + 250  # Increased height for better station display

# Tkinter init
root = tk.Tk()
root.title("SafeScan Detection System")
root.geometry(f"{window_width}x{window_height}")
root.minsize(window_width, window_height)  # Prevent window from shrinking

# Backend variables
font_style = ("Arial", 10)
threshold = tk.IntVar(value=5)
station_selection_enabled = tk.BooleanVar(value=False)
people_detect = tk.BooleanVar(value=True)
helmets_detect = tk.BooleanVar(value=True)
vests_detect = tk.BooleanVar(value=True)
frame_counter = 0
last_detection_result = None
last_person_count = 0
last_people_boxes = []
last_person_ids = []

# Tracking history variables
tracker = PeopleTracker()

# Drawing variables
station_manager = StationManager()
rectangle_start = None
settings_file = "settings.json"

# Function definitions

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r") as file:
            data = json.load(file)
            people_detect.set(data.get("people", True))
            helmets_detect.set(data.get("helmets", True))
            vests_detect.set(data.get("vests", True))

def save_settings():
    with open(settings_file, "w") as file:
        json.dump({"people": people_detect.get(), "helmets": helmets_detect.get(), "vests": vests_detect.get()}, file)
    print("Settings saved.")

def update_border_color(person_count):
    color = "red" if person_count >= threshold.get() else "blue"
    border_frame.config(bg=color, highlightbackground=color)

def increase_threshold():
    threshold.set(threshold.get() + 1)
    threshold_label.config(text=f"Threshold: {threshold.get()}")

def decrease_threshold():
    if threshold.get() > 1:
        threshold.set(threshold.get() - 1)
        threshold_label.config(text=f"Threshold: {threshold.get()}")

def toggle_station_selection():
    station_selection_enabled.set(not station_selection_enabled.get())
    if station_selection_enabled.get():
        station_button.config(text="📌 Station Selection: ON", relief=tk.SUNKEN, bg="#cce5ff")
    else:
        station_button.config(text="📌 Station Selection: OFF", relief=tk.RAISED, bg="#e1e1e1")

def remove_stations():
    station_manager.clear()
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
            
def update_frame():
    global frame_counter, last_detection_result, last_person_count, last_people_boxes, last_person_ids

    ret, frame = cap.read()
    if ret:
        frame = cv2.resize(frame, (video_width, video_height))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if frame_counter % 2 == 0:
            frame, person_count, people_boxes, person_ids = detection.run_detection(
                frame,
                draw_person=people_detect.get(),
                draw_helmet=helmets_detect.get(),
                draw_vest=vests_detect.get()
            )
            last_detection_result = frame.copy()
            last_person_count = person_count
            last_people_boxes = [(int((x1 + x2) / 2), int((y1 + y2) / 2)) for (x1, y1, x2, y2) in people_boxes]
            last_person_ids = person_ids
            
            # Update tracking history
            tracker.update(
                last_people_boxes,
                last_person_ids,
                station_manager.rectangles,
                station_manager.station_names
            )
        else:
            frame = last_detection_result if last_detection_result is not None else frame

        # Draw stations
        frame = station_manager.draw_stations(frame)
        
        people_count_label.config(text=f"👥 People Count: {last_person_count}")
        update_border_color(last_person_count)
        station_display_text = station_manager.get_station_counts_text(last_people_boxes)
        station_display.config(state="normal")
        station_display.delete(1.0, tk.END)
        station_display.insert(tk.END, station_display_text)
        station_display.config(state="disabled")

        img = Image.fromarray(frame)
        imgtk = ImageTk.PhotoImage(img)
        video_label.config(image=imgtk)
        video_label.image = imgtk

        frame_counter += 1
        root.after(33, update_frame)  # ~30fps
    else:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        update_frame()

# Create main container frames
left_panel = tk.Frame(root, width=220, padx=10, bg="#f0f0f0")
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

threshold_section = tk.LabelFrame(left_panel, text="🔔 Alert Threshold", font=("Arial", 10, "bold"),
                                padx=5, pady=5, bg="#f0f0f0")
threshold_section.pack(fill="x", pady=5)

# Info section in right panel
info_section = tk.LabelFrame(right_panel, text="📊 Live Information", font=("Arial", 10, "bold"),
                            padx=10, pady=10)
info_section.pack_propagate(False)
info_section.pack(fill="both", expand=True, padx=10, pady=10)

# UI Elements - Controls Section
station_button = tk.Button(control_section, text="📌 Station Selection: OFF",
                          command=toggle_station_selection,
                          width=22, font=font_style, bg="#e1e1e1")
station_button.pack(fill="x", pady=2)

remove_button = tk.Button(control_section, text="❌ Remove Stations",
                         command=remove_stations, width=22, font=font_style, bg="#ffcccc")
remove_button.pack(fill="x", pady=2)

save_button = tk.Button(control_section, text="💾 Save Stations",
                       command=station_manager.save, width=22, font=font_style, bg="#ccffcc")
save_button.pack(fill="x", pady=2)

history_button = tk.Button(control_section, text="📜 View History",
                          command=show_history_window, width=22, font=font_style, bg="#cce5ff")
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

# UI Elements - Threshold Section
threshold_label = tk.Label(threshold_section, text=f"Threshold: {threshold.get()}",
                          font=font_style, bg="#f0f0f0")
threshold_label.pack(pady=5)

threshold_buttons = tk.Frame(threshold_section, bg="#f0f0f0")
threshold_buttons.pack()

decrease_button = tk.Button(threshold_buttons, text="-", command=decrease_threshold,
                           width=3, font=font_style, bg="#e1e1e1")
decrease_button.pack(side="left", padx=5)

increase_button = tk.Button(threshold_buttons, text="+", command=increase_threshold,
                           width=3, font=font_style, bg="#e1e1e1")
increase_button.pack(side="left", padx=5)

# UI Elements - Info Section
people_count_label = tk.Label(info_section, text="👥 People Count: 0",
                             font=("Arial", 12, "bold"))
people_count_label.pack(pady=5)

# Station display with scrollable text widget
station_text = tk.StringVar()
station_text.set("Draw stations to begin tracking")

# Create a frame for the station display with fixed height
station_display_frame = tk.Frame(info_section, height=100,  # Fixed height
                               bg="white", relief="sunken", borderwidth=2)
station_display_frame.pack(fill="x", pady=5)  # Only fill horizontally

# Text widget for stations display
station_display = tk.Text(station_display_frame, wrap=tk.WORD, 
                         font=font_style, bg="white", fg="black",
                         height=4,  # Show 4 lines max
                         padx=5, pady=5)
station_display.pack(side="left", fill="both", expand=True)

# Add scrollbar
scrollbar = tk.Scrollbar(station_display_frame)
scrollbar.pack(side="right", fill="y")
station_display.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=station_display.yview)

# Email Alert Section
# Create a container frame for the button and label
control_row = tk.Frame(info_section)
control_row.pack(side="bottom", pady=10, fill="x")

# Place button on the LEFT
email_button = tk.Button(
    control_row,  # Changed parent to control_row
    text="🚨 Send Alert",
    command=lambda: email_service.send_alert(
        "Safety Alert: Person Detected",
        "Alert!\n\nPerson detected in monitored area.\n\nSafeScan Monitoring System"
    ),
    width=15,
    font=font_style,
    bg="#ff9999"
)
email_button.pack(side="left")

# Place label on the RIGHT
email_status_label = tk.Label(
    control_row,  # Changed parent to control_row
    font=font_style,
    fg="black",
    bg="#f0f0f0",  # Light gray background
    padx=10
)
email_status_label.pack(side="right")

# Email init
email_service = EmailService(
    sender="marwanhatem1234@gmail.com",
    receiver="marwanhatemalt1234@gmail.com",
    password="fgmyjbnplmmtcanv",
    status_label=email_status_label  # Pass the label for automatic updates
)

# Event binding
video_label.bind("<Button-1>", record_click)

# Initialization
station_manager.load()
load_settings()

# Start video playback
update_frame()

# Run GUI
root.mainloop()

# Release video when window closes
cap.release()