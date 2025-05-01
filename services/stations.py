import json
import os
import cv2

class StationManager:
    def __init__(self):
        self.rectangles = []  # Format: [((x1, y1), (x2, y2)), ...]
        self.station_names = []  # Format: ["Station 1", "Station 2", ...]
        self.stations_file = "services/stations.json"
        self.rectangle_start = None

    def save(self):
        """Save stations to file with data validation"""
        validated_rectangles = []
        for rect in self.rectangles:
            if len(rect) == 2 and len(rect[0]) == 2 and len(rect[1]) == 2:
                validated_rectangles.append(rect)
        
        data = {
            "rectangles": validated_rectangles,
            "station_names": self.station_names
        }
        with open(self.stations_file, "w") as file:
            json.dump(data, file, indent=2)

    def load(self):
        """Load stations with data validation"""
        if os.path.exists(self.stations_file):
            with open(self.stations_file, "r") as file:
                data = json.load(file)
                self.rectangles = [
                    ((int(x1), int(y1)), (int(x2), int(y2)))
                    for ((x1, y1), (x2, y2)) in data.get("rectangles", [])
                    if all(isinstance(v, (int, float)) for v in [x1, y1, x2, y2])
                ]
                self.station_names = data.get("station_names", [])

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
        if not self.rectangles:
            return "Draw stations to begin tracking"
        
        try:
            counts = [0] * len(self.rectangles)
            
            for (px, py) in people_positions:
                for i, ((x1, y1), (x2, y2)) in enumerate(self.rectangles):
                    if x1 <= px <= x2 and y1 <= py <= y2:
                        counts[i] += 1
                        break  # A person can only be in one station
            
            # Build the display text
            display_text = ""
            for name, count in zip(self.station_names, counts):
                display_text += f"{name}: {count} person(s)\n"
                
            return display_text.strip()
            
        except Exception as e:
            print(f"Count error: {e}")
            return "Error counting people in stations"

    def draw_stations(self, frame):
        """Draws all stations on the frame"""
        try:
            for i, (start_pos, end_pos) in enumerate(self.rectangles):
                # Ensure we have exactly two points
                if len(start_pos) == 2 and len(end_pos) == 2:
                    x1, y1 = start_pos
                    x2, y2 = end_pos
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(frame, self.station_names[i], (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            return frame
        except Exception as e:
            print(f"Station drawing error: {e}")
            return frame  # Return original frame if error occurs