import time

class PeopleTracker:
    def __init__(self):
        self.history = {}  # Format: {track_id: {data}}

    def update(self, people_positions, person_ids, station_rectangles, station_names):
      current_time = time.time()
      
      # 1. Update or create tracks
      for track_id in person_ids:
          if track_id not in self.history:
              self.history[track_id] = {
                  'first_seen': current_time,
                  'last_seen': current_time,
                  'total_time': 0,
                  'station_history': [],
                  'current_station': None,
                  'last_update': current_time
              }

      # 2. Update stations and time
      for i, track_id in enumerate(person_ids):
          data = self.history[track_id]
          x, y = people_positions[i]
          
          # Calculate elapsed time since last update
          elapsed = current_time - data['last_update']
          data['total_time'] += elapsed
          data['last_seen'] = current_time
          
          # Check current station
          current_station = None
          for j, ((x1, y1), (x2, y2)) in enumerate(station_rectangles):
              if x1 <= x <= x2 and y1 <= y <= y2:
                  current_station = station_names[j]
                  break
          
          # Handle station changes
          if data['current_station'] != current_station:
              if data['current_station'] is not None:
                  # Only record time spent when leaving a station
                  data['station_history'].append((
                      data['current_station'],
                      elapsed  # Time spent in PREVIOUS station
                  ))
              data['current_station'] = current_station
              data['last_update'] = current_time
      
      # 3. Clean up old tracks
      self.history = {
          tid: data for tid, data in self.history.items()
          if current_time - data['last_seen'] <= 300
      }
    
    def get_history_table_data(self):
      """Returns formatted data for history table"""
      current_time = time.time()
      table_data = []
      
      for track_id, data in self.history.items():
          current_station_time = current_time - data['last_update'] if data['current_station'] else 0
          total_station_time = sum(t for _, t in data['station_history']) + current_station_time
          display_station_time = min(total_station_time, data['total_time'])
          
          table_data.append((
              track_id,
              f"{data['total_time']:.1f}s",
              data['current_station'] or "None",
              f"{display_station_time:.1f}s" if data['current_station'] else "N/A"
          ))
      
      return table_data