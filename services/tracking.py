import time

class PeopleTracker:
    def __init__(self):
        self.history = {}  # Format: {track_id: {data}}
        self.last_update_time = time.time()  # Track last global update

    def update(self, people_positions, person_ids, station_rectangles, station_names):
        current_time = time.time()
        time_elapsed = current_time - self.last_update_time
        self.last_update_time = current_time

        # 1. Update or create tracks
        for track_id in person_ids:
            if track_id not in self.history:
                self.history[track_id] = {
                    'total_time': 0.0,  # Total time visible
                    'station_time': 0.0, # Time specifically in stations
                    'current_station': None,
                    'station_history': [],  # List of (station_name, duration)
                    'last_seen': current_time,
                    'last_station_update': current_time
                }

        # 2. Update all tracks
        for track_id, data in self.history.items():
            if track_id in person_ids:
                # Person is visible - update total time
                data['total_time'] += time_elapsed
                data['last_seen'] = current_time

                # Find current station (if any)
                current_station = None
                idx = person_ids.index(track_id)
                x, y = people_positions[idx]
                
                for i, ((x1, y1), (x2, y2)) in enumerate(station_rectangles):
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        current_station = station_names[i]
                        break

                # Handle station changes
                if data['current_station'] != current_station:
                    if data['current_station'] is not None:
                        # Record time spent in previous station
                        elapsed = current_time - data['last_station_update']
                        data['station_history'].append((
                            data['current_station'],
                            elapsed
                        ))
                        data['station_time'] += elapsed
                    
                    data['current_station'] = current_station
                    data['last_station_update'] = current_time

            # Else: person not currently visible, don't update times

        # 3. Clean up old tracks (5 minute timeout)
        self.history = {
            tid: data for tid, data in self.history.items()
            if current_time - data['last_seen'] <= 300
        }

    def get_history_table_data(self):
        """Returns formatted data for history table"""
        current_time = time.time()
        table_data = []
        
        for track_id, data in self.history.items():
            # Calculate current station time if still in station
            current_station_time = 0.0
            if data['current_station'] is not None:
                current_station_time = current_time - data['last_station_update']
                total_station_time = data['station_time'] + current_station_time
            else:
                total_station_time = data['station_time']

            table_data.append((
                track_id,
                f"{data['total_time']:.1f}s",  # Total time visible
                data['current_station'] or "None",
                f"{total_station_time:.1f}s" if data['current_station'] else f"{data['station_time']:.1f}s"
            ))
        
        return table_data