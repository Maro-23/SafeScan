import time
from services.email import EmailService
from threading import Thread, Lock
import cv2

class PPEViolationDetector:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
        self.violation_timers = {}  # {track_id: {'helmet': timer, 'vest': timer}}
        self.lock = Lock()
        self.detection_threshold = 3  # Seconds of continuous violation before email
        self.check_interval = 1.0  # How often to check for violations
        
    def update(self, person_boxes, person_ids, ppe_boxes, ppe_classes, check_helmet=True, check_vest=True):
        """Update detection with current frame data"""
        with self.lock:
            current_time = time.time()
            
            # Reset all timers for detected people
            for track_id in person_ids:
                if track_id not in self.violation_timers:
                    self.violation_timers[track_id] = {
                        'helmet': {'start': None, 'reported': False},
                        'vest': {'start': None, 'reported': False}
                    }
            
            # Check for PPE violations
            for i, track_id in enumerate(person_ids):
                person_box = person_boxes[i]
                has_helmet = False
                has_vest = False
                
                # Check if person has required PPE
                print(ppe_boxes)
                print(ppe_classes)
                if len(ppe_boxes) >= 1:
                    for i, ppe_box in enumerate(ppe_boxes):
                        if self._boxes_overlap(person_box, ppe_box):
                            class_id = ppe_classes[i]
                            if class_id == 0:  # Helmet class ID
                                has_helmet = True
                            elif class_id == 1:  # Vest class ID
                                has_vest = True
                
                # Update violation timers
                if check_helmet and not has_helmet:
                    self._update_violation_timer(track_id, 'helmet', current_time)
                else:
                    self._reset_violation_timer(track_id, 'helmet')
                    
                if check_vest and not has_vest:
                    self._update_violation_timer(track_id, 'vest', current_time)
                else:
                    self._reset_violation_timer(track_id, 'vest')
    
    def _boxes_overlap(self, box1, box2):
        """Check if two bounding boxes overlap"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # Check if one rectangle is to the left of the other
        if x1_1 > x2_2 or x1_2 > x2_1:
            return False
            
        # Check if one rectangle is above the other
        if y1_1 > y2_2 or y1_2 > y2_1:
            return False
            
        return True
    
    def _update_violation_timer(self, track_id, ppe_type, current_time):
        """Update violation timer for a specific PPE type"""
        timer = self.violation_timers[track_id][ppe_type]
        
        if timer['start'] is None:
            timer['start'] = current_time
        elif not timer['reported'] and current_time - timer['start'] >= self.detection_threshold:
            self._send_violation_alert(track_id, ppe_type)
            timer['reported'] = True
    
    def _reset_violation_timer(self, track_id, ppe_type):
        """Reset the violation timer"""
        self.violation_timers[track_id][ppe_type] = {'start': None, 'reported': False}
    
    def _send_violation_alert(self, track_id, ppe_type):
        """Send email alert for PPE violation"""
        ppe_name = "helmet" if ppe_type == "helmet" else "reflective vest"
        subject = f"PPE Violation Alert - ID {track_id}"
        message = f"Person with ID {track_id} detected without {ppe_name} for more than {self.detection_threshold} seconds."
        
        # Send email in a separate thread
        Thread(target=self.email_service.send_alert, args=(subject, message), daemon=True).start()
        
    # Add to PPEViolationDetector class:

    def draw_violation_indicators(self, frame, person_boxes, person_ids):
        """Draw visual indicators for violations"""
        with self.lock:
            for i, track_id in enumerate(person_ids):
                if track_id in self.violation_timers:
                    violations = []
                    timer = self.violation_timers[track_id]
                    
                    if timer['helmet']['start'] is not None:
                        violations.append("NO HELMET")
                    if timer['vest']['start'] is not None:
                        violations.append("NO VEST")
                    
                    if violations:
                        x1, y1, x2, y2 = person_boxes[i]
                        # Draw warning background
                        # Draw violation text
                        text = " | ".join(violations)
                        cv2.putText(frame, text, (x1, y1+20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 4, cv2.LINE_AA)
                        cv2.putText(frame, text, (x1, y1+20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (206, 32, 41), 2, cv2.LINE_AA)
        return frame