from ultralytics import YOLO
import cv2
import yaml

# Load models
person_model = YOLO("yolov8m.pt")  # Standard COCO model for person detection
ppe_model = YOLO("best.pt")        # Custom model for PPE detection

# Load class names from YAML (for PPE only)
with open("data.yaml", "r") as f:
    data_yaml = yaml.safe_load(f)
ppe_class_names = data_yaml["names"]

# Colors for detection
class_colors = {
    "Safety-Helmet": (0, 255, 0),      # Green
    "Reflective-Jacket": (255, 0, 0),  # Red
    "person": (1, 255, 31)            # Blue
}

def run_detection(frame, draw_person=True, draw_helmet=True, draw_vest=True):
    person_count = 0
    person_boxes = []
    person_ids = []
    
    # Run person detection with tracking (using COCO model)
    person_results = person_model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=0.4,
        classes=[0],  # 0 is person class in COCO
        verbose=False,
        half=False,
        device="cpu"
    )
    
    # Run PPE detection without tracking
    ppe_results = ppe_model(
        frame,
        conf=0.4,
        verbose=False,
        half=False,
        device="cpu"
    )
    
    # Process person detections
    if person_results[0].boxes.id is not None:
        boxes = person_results[0].boxes.xyxy.cpu().numpy().astype(int)
        confidences = person_results[0].boxes.conf.cpu().numpy()
        class_ids = person_results[0].boxes.cls.cpu().numpy().astype(int)
        track_ids = person_results[0].boxes.id.cpu().numpy().astype(int)
        
        for box, conf, class_id, track_id in zip(boxes, confidences, class_ids, track_ids):
            x1, y1, x2, y2 = box
            
            # Only process person detections (class_id 0 in COCO)
            if class_id != 0 or not draw_person:
                continue
                
            # Draw person bounding box
            color = class_colors.get("person", (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
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
    
    # Process PPE detections
    if ppe_results[0].boxes is not None:
        boxes = ppe_results[0].boxes.xyxy.cpu().numpy().astype(int)
        confidences = ppe_results[0].boxes.conf.cpu().numpy()
        class_ids = ppe_results[0].boxes.cls.cpu().numpy().astype(int)
        
        for box, conf, class_id in zip(boxes, confidences, class_ids):
            x1, y1, x2, y2 = box
            
            if class_id < len(ppe_class_names):
                class_name = ppe_class_names[class_id]
            else:
                continue
                
            # Skip if this class detection is disabled in UI
            if (class_name == "Safety-Helmet" and not draw_helmet) or \
               (class_name == "Reflective-Jacket" and not draw_vest):
                continue
                
            # Draw PPE bounding box
            color = class_colors.get(class_name, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Add label for PPE items
            label = f"{class_name} {conf:.2f}"
            cv2.putText(
                frame, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA
            )
            cv2.putText(
                frame, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA
            )
    
    return frame, person_count, person_boxes, person_ids