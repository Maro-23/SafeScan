from ultralytics import YOLO
import cv2
import yaml

# Single combined model for all detections
detection_model = YOLO("yolov8m.pt")  # Using your custom model that should detect all classes

# Load class names from YAML
with open("data.yaml", "r") as f:
    data_yaml = yaml.safe_load(f)
custom_class_names = data_yaml["names"]

# Colors for detection
class_colors = {
    "helmet": (0, 255, 0),  # Green
    "vest": (255, 0, 0),    # Red
    "person": (1, 255, 31)  # Blue
}

def run_detection(frame, draw_person=True, draw_helmet=True, draw_vest=True):
    person_count = 0
    person_boxes = []
    person_ids = []
    
    # Single inference pass for all detections
    results = detection_model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=0.4,
        verbose=False, 
        half = False,
        device = "cpu"
        # Disable logging for better performance
    )
    
    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        confidences = results[0].boxes.conf.cpu().numpy()
        class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)
        for box, conf, class_id, track_id in zip(boxes, confidences, class_ids, track_ids):
            x1, y1, x2, y2 = box
            
            # Get class name
            if class_id < len(custom_class_names):
                class_name = custom_class_names[class_id]
            else:
                continue  # Skip unknown classes
            # Skip if this class detection is disabled in UI
            if (class_name == "person" and not draw_person) or \
               (class_name == "helmet" and not draw_helmet) or \
               (class_name == "vest" and not draw_vest):
                continue
                
            # Draw bounding box
            color = class_colors.get(class_name, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Special handling for person class
            if class_name == "person":
                # Draw ID text with background for visibility
                cv2.putText(
                    frame, f"ID: {track_id}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA
                )
                cv2.putText(
                    frame, f"ID: {track_id}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA
                )
                person_count += 1
                person_boxes.append((x1, y1, x2, y2))
                person_ids.append(track_id)
    
    return frame, person_count, person_boxes, person_ids