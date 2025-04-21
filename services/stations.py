import json
import os

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