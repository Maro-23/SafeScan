import json
import os
import cv2

class StationManager:
    def __init__(self):
        self.rectangles = []  # Format: [((x1, y1), (x2, y2)), ...]
        self.station_names = []  # Format: ["Station 1", "Station 2", ...]
        self.stations_file = "services/stations.json"
        self.rectangle_start = None

    def load(self):
        print(f"Attempting to load stations from {self.stations_file}")  # Debug
        if os.path.exists(self.stations_file):
            print("File exists, loading...")  # Debug
            with open(self.stations_file, "r") as file:
                data = json.load(file)
                self.rectangles = data.get("rectangles", [])
                self.station_names = data.get("station_names", [])
                print(f"Loaded data: {data}")  # Debug
        else:
            print("No stations file found")  # Debug

    def save(self):
        print(f"Saving stations to {self.stations_file}")  # Debug
        data = {"rectangles": self.rectangles, "station_names": self.station_names}
        print(f"Data being saved: {data}")  # Debug
        with open(self.stations_file, "w") as file:
            json.dump(data, file, indent=2)  # Added indent for readability
        print("Save completed")  # Debug

    def add_station(self, start_pos, end_pos):
        """Add a new station rectangle."""
        self.rectangles.append((start_pos, end_pos))
        self.station_names.append(f"Station {len(self.station_names) + 1}")

    def clear(self):
        """Remove all stations."""
        self.rectangles = []
        self.station_names = []
        
    def count_people_in_stations(self, people_positions):
        """Returns station counts and formatted display text"""
        station_counts = [0] * len(self.rectangles)
        
        for (px, py) in people_positions:
            for i, ((x1, y1), (x2, y2)) in enumerate(self.rectangles):
                if x1 <= px <= x2 and y1 <= py <= y2:
                    station_counts[i] += 1
        
        # Generate formatted text
        display_text = ""
        for i, count in enumerate(station_counts):
            display_text += f"{self.station_names[i]}: {count}\n"
        
        return station_counts, display_text.strip()
    
    def get_station_counts_text(self, people_positions):
        """Returns formatted text of people counts per station"""
        counts, text = self.count_people_in_stations(people_positions)
        return text or "Draw stations to begin tracking"

    def draw_stations(self, frame):
        """Draws all stations on the frame"""
        for i, ((x1, y1), (x2, y2)) in enumerate(self.rectangles):
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, self.station_names[i], (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        return frame