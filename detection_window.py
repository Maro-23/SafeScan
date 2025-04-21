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
history_window = None
history_table = None

# Email init
email_service = EmailService(
    sender="marwanhatem1234@gmail.com",
    receiver="marwanhatemalt1234@gmail.com",
    password="fgmyjbnplmmtcanv"
)

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

def update_station_people_count():
    global last_people_boxes
    if station_manager.rectangles:
        station_counts = [0] * len(station_manager.rectangles)
        for (px, py) in last_people_boxes:
            for i, ((x1, y1), (x2, y2)) in enumerate(station_manager.rectangles):
                if x1 <= px <= x2 and y1 <= py <= y2:
                    station_counts[i] += 1
        
        # Clear and update the text widget
        station_display.config(state="normal")
        station_display.delete(1.0, tk.END)
        
        # Format the station counts
        for i in range(len(station_manager.rectangles)):
            station_display.insert(tk.END, f"{station_manager.station_names[i]}: {station_counts[i]}\n")
        
        station_display.config(state="disabled")
        station_display.see(tk.END)  # Auto-scroll to bottom
    else:
        station_display.config(state="normal")
        station_display.delete(1.0, tk.END)
        station_display.insert(tk.END, "Draw stations to begin tracking")
        station_display.config(state="disabled")

def show_history_window():
    global history_window, history_table
    
    if history_window is None or not history_window.winfo_exists():
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
        
        # Add refresh button
        refresh_button = tk.Button(history_window, text="Refresh", command=update_history_table)
        refresh_button.pack(pady=10)
        
        # Update table initially
        update_history_table()
    else:
        history_window.lift()

def update_history_table():
    if history_table:
        history_table.delete(*history_table.get_children())
        current_time = time.time()
        
        for track_id, data in tracker.history.items():
            # Calculate CURRENT station time (not yet recorded in history)
            current_station_time = 0
            if data['current_station']:
                current_station_time = current_time - data['last_update']
            
            # Sum all time spent in current + previous stations
            total_station_time = sum(t for _, t in data['station_history']) + current_station_time
            
            # Ensure never exceeds total_time
            display_station_time = min(total_station_time, data['total_time'])
            
            history_table.insert("", "end", values=(
                track_id,
                f"{data['total_time']:.1f}s",
                data['current_station'] or "None",
                f"{display_station_time:.1f}s" if data['current_station'] else "N/A"
            ))
            
def send_alert_email():
    def _send_thread():
        try:
            email_status_label.config(text="Sending email...", fg="blue")
            email_status_label.update_idletasks()  # Force UI update
            
            success, message = email_service.send_alert(
                subject="Safety Alert: Person Detected",
                body="Alert!\n\nPerson detected in monitored area.\n\nSafeScan Monitoring System"
            )
            print(f"Email result - {success}")  # <-- ADD THIS
            
            email_status_label.config(text=message, fg="green" if success else "red")
        except Exception as e:
            print(f"Error in thread: {str(e)}")  # <-- ADD THIS
        finally:
            root.after(3000, lambda: email_status_label.config(text=""))
    
    threading.Thread(target=_send_thread, daemon=True).start()

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
        for i, rect in enumerate(station_manager.rectangles):
            (x1, y1), (x2, y2) = rect
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, station_manager.station_names[i], (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        people_count_label.config(text=f"👥 People Count: {last_person_count}")
        update_border_color(last_person_count)
        update_station_people_count()

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
    command=send_alert_email,
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