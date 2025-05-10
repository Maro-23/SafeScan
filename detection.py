from ultralytics import YOLO
import cv2
import yaml
import torch

# Configure PyTorch for optimal CPU performance
torch.set_num_threads(1)  # Reduce CPU thrashing
torch.set_flush_denormal(True)  # Improve float32 performance

# Load models with explicit CPU device
person_model = YOLO("yolov8m.pt").to('cpu')  # Standard COCO model for person detection
ppe_model = YOLO("best.pt").to('cpu')        # Custom model for PPE detection

# Load class names from YAML (for PPE only)
with open("data.yaml", "r") as f:
    data_yaml = yaml.safe_load(f)
ppe_class_names = data_yaml["names"]

# Colors for detection
class_colors = {
    "Safety-Helmet": (0, 0, 255),      # Green
    "Reflective-Jacket": (255, 0, 0),  # Red
    "person": (1, 255, 31)            # Blue
}

# Detection cache for frame skipping
detection_cache = {
    'person_boxes': [],
    'person_ids': [],
    'ppe_boxes': None,
    'frame_count': 0,
    'last_full_frame': None
}

def draw_person_boxes(frame, boxes, ids, draw_person):
    person_count = 0
    for box, track_id in zip(boxes, ids):
        x1, y1, x2, y2 = box
        if draw_person:
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
    return person_count

def draw_ppe_boxes(frame, boxes, class_ids, draw_helmet, draw_vest):
    if boxes is None:
        return
        
    for box, class_id in zip(boxes, class_ids):
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
        label = f"{class_name}"
        cv2.putText(
            frame, label, (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA
        )
        cv2.putText(
            frame, label, (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA
        )

def run_detection(frame, draw_person=True, draw_helmet=True, draw_vest=True):
    global detection_cache
    # Initialize default return values
    person_count = 0
    person_boxes = []
    person_ids = []
    ppe_boxes_data = None
    
    # Only process every 3rd frame but use cached results for others
    if detection_cache['frame_count'] % 3 != 0:
        detection_cache['frame_count'] += 1
        
        # Create fresh frame with cached detections
        output_frame = frame.copy()
        person_count = draw_person_boxes(output_frame, 
                                      detection_cache['person_boxes'], 
                                      detection_cache['person_ids'], 
                                      draw_person)
        
        # Handle PPE drawing with cache
        if detection_cache['ppe_boxes']:
            draw_ppe_boxes(output_frame, 
                         detection_cache['ppe_boxes'][0], 
                         detection_cache['ppe_boxes'][1], 
                         draw_helmet, 
                         draw_vest)
            ppe_boxes_data = detection_cache['ppe_boxes']
        
        return (
            output_frame,
            person_count,
            detection_cache['person_boxes'],
            detection_cache['person_ids'],
            ppe_boxes_data
        )
    
    # Actual processing for this frame
    with torch.no_grad():
        # Person detection with tracking
        person_results = person_model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.4,
            classes=[0],  # 0 is person class in COCO
            verbose=False,
            device="cpu",
            imgsz=320,
            half=False
        )
        
        # PPE detection
        ppe_results = ppe_model(
            frame,
            conf=0.4,
            verbose=False,
            device="cpu",
            imgsz=320,
            half=False
        )
    
    # Process person detections
    if person_results[0].boxes.id is not None:
        boxes = person_results[0].boxes.xyxy.cpu().numpy().astype(int)
        track_ids = person_results[0].boxes.id.cpu().numpy().astype(int)
        
        person_boxes = [box for box in boxes]
        person_ids = [tid for tid in track_ids]
        person_count = len(person_boxes)
        
        # Draw person boxes
        draw_person_boxes(frame, person_boxes, person_ids, draw_person)
    
    # Process PPE detections
    if ppe_results[0].boxes is not None:
        boxes = ppe_results[0].boxes.xyxy.cpu().numpy().astype(int)
        class_ids = ppe_results[0].boxes.cls.cpu().numpy().astype(int)
        ppe_boxes_data = (boxes, class_ids)        
        # Draw PPE boxes
        draw_ppe_boxes(frame, boxes, class_ids, draw_helmet, draw_vest)
    
    # Update cache
    detection_cache = {
        'person_boxes': person_boxes,
        'person_ids': person_ids,
        'ppe_boxes': ppe_boxes_data,
        'frame_count': detection_cache['frame_count'] + 1,
        'last_full_frame': frame.copy()
    }   
    # Always return 5 values
    return (
        frame,          # Processed frame with drawings
        person_count,   # Number of people detected
        person_boxes,   # List of person bounding boxes
        person_ids,     # List of tracking IDs
        ppe_boxes_data  # Tuple of (ppe_boxes, ppe_classes) or None
    )
# Warm up models on startup
def warmup_models():
    dummy_frame = torch.zeros((320, 320, 3), dtype=torch.uint8).numpy()
    run_detection(dummy_frame)
    print("Models warmed up")

# Perform warmup
warmup_models()