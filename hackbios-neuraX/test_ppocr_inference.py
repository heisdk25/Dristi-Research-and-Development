import os
import cv2
import numpy as np
import onnxruntime as ort
import pyclipper
from shapely.geometry import Polygon

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ppocrv4")
DET_MODEL = os.path.join(MODELS_DIR, "ch_PP-OCRv4_det_infer.onnx")
REC_MODEL = os.path.join(MODELS_DIR, "en_PP-OCRv4_rec_infer.onnx")
DICT_PATH = os.path.join(MODELS_DIR, "en_dict.txt")

def load_dict(dict_path):
    with open(dict_path, "r", encoding="utf-8") as f:
        chars = [line.strip("\r\n") for line in f.readlines()]
    # Remove any empty trailing line
    chars = [c for c in chars if c != ""]
    # Check if space is in chars
    # PaddleOCR CTC: blank is at index 0
    # Let's inspect size
    character_list = ["<blank>"] + chars
    # If character_list length is 96, and model output is 97, what is index 96?
    # In PaddleOCR, if use_space_char=True, an extra space ' ' is appended:
    if len(character_list) == 96:
        character_list.append(" ") # index 96
    print(f"Loaded dictionary with {len(character_list)} tokens (0 to {len(character_list)-1})")
    return character_list

class DBPostProcess:
    def __init__(self, thresh=0.3, box_thresh=0.6, max_candidates=1000, unclip_ratio=1.6):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio

    def __call__(self, pred, orig_shape):
        # pred: [1, 1, H, W]
        segmentation = pred[0, 0] >= self.thresh
        mask = (segmentation * 255).astype(np.uint8)
        
        orig_h, orig_w = orig_shape
        pred_h, pred_w = pred.shape[2], pred.shape[3]
        scale_x = orig_w / float(pred_w)
        scale_y = orig_h / float(pred_h)

        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        scores = []

        for contour in contours[:self.max_candidates]:
            if len(contour) < 3:
                continue
            
            # Score calculation
            c_mask = np.zeros((pred_h, pred_w), dtype=np.uint8)
            cv2.drawContours(c_mask, [contour], -1, 1, -1)
            score = cv2.mean(pred[0, 0], mask=c_mask)[0]
            if score < self.box_thresh:
                continue

            # Unclip
            poly = contour.reshape(-1, 2)
            polygon = Polygon(poly)
            distance = polygon.area * self.unclip_ratio / polygon.length if polygon.length > 0 else 0
            offset = pyclipper.PyclipperOffset()
            offset.AddPath(poly, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
            unclipped = offset.Execute(distance)
            if not unclipped:
                continue
            
            unclipped_poly = np.array(unclipped[0])
            rect = cv2.minAreaRect(unclipped_poly)
            box = cv2.boxPoints(rect)
            
            # Scale back to original coordinates
            box[:, 0] *= scale_x
            box[:, 1] *= scale_y
            
            # Sort box points: top-left, top-right, bottom-right, bottom-left
            box = self.order_points(box)
            boxes.append(box)
            scores.append(score)

        return boxes, scores

    def order_points(self, pts):
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

def crop_roi(img, pts):
    # pts: 4x2 ordered [TL, TR, BR, BL]
    w = int(max(np.linalg.norm(pts[0] - pts[1]), np.linalg.norm(pts[2] - pts[3])))
    h = int(max(np.linalg.norm(pts[0] - pts[3]), np.linalg.norm(pts[1] - pts[2])))
    if w <= 0 or h <= 0:
        return None
    dst_pts = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(pts.astype(np.float32), dst_pts)
    warped = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return warped

def preprocess_det(img, target_size=640):
    # PP-OCRv4 detection expects [1, 3, H, W] normalized with mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
    h, w = img.shape[:2]
    # Resize preserving aspect ratio or multiples of 32
    scale = min(target_size / float(h), target_size / float(w))
    new_h = int(round(h * scale / 32) * 32)
    new_w = int(round(w * scale / 32) * 32)
    new_h = max(32, new_h)
    new_w = max(32, new_w)

    resized = cv2.resize(img, (new_w, new_h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    norm = (rgb - mean) / std
    tensor = norm.transpose(2, 0, 1)[np.newaxis, :, :, :]
    return tensor

def preprocess_rec(crop, target_h=48, max_w=320):
    # crop BGR -> RGB
    h, w = crop.shape[:2]
    aspect_w = int(round((w / float(h)) * target_h))
    target_w = min(max_w, max(16, aspect_w))
    # Pad to target_w or keep
    resized = cv2.resize(crop, (target_w, target_h))
    
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    std = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    norm = (rgb - mean) / std
    tensor = norm.transpose(2, 0, 1)[np.newaxis, :, :, :]
    return tensor

def ctc_decode(logits, character_list):
    # logits: [1, T, 97]
    probs = logits[0]
    preds = np.argmax(probs, axis=1)
    confidences = np.max(probs, axis=1)

    decoded = []
    scores = []
    last_idx = -1
    for idx, conf in zip(preds, confidences):
        if idx != 0 and idx != last_idx:
            if idx < len(character_list):
                decoded.append(character_list[idx])
                scores.append(conf)
        last_idx = idx

    text = "".join(decoded).strip()
    avg_score = float(np.mean(scores)) if len(scores) > 0 else 0.0
    return text, avg_score, preds

def create_test_image():
    # 640x480 test image with distinct English signs
    img = np.ones((480, 640, 3), dtype=np.uint8) * 240
    # Add title bar / sign
    cv2.rectangle(img, (40, 40), (600, 120), (30, 30, 30), -1)
    cv2.putText(img, "DRISHTI ASSISTIVE OCR", (60, 95), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)

    # Add medicine sign
    cv2.rectangle(img, (40, 160), (360, 240), (220, 240, 220), -1)
    cv2.rectangle(img, (40, 160), (360, 240), (0, 120, 0), 2)
    cv2.putText(img, "ASPIRIN 100MG", (55, 215), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 100, 0), 2, cv2.LINE_AA)

    # Add warning sign
    cv2.rectangle(img, (40, 280), (450, 360), (200, 230, 255), -1)
    cv2.rectangle(img, (40, 280), (450, 360), (0, 0, 200), 2)
    cv2.putText(img, "CAUTION WET FLOOR", (55, 335), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 180), 2, cv2.LINE_AA)

    # Add exit sign
    cv2.rectangle(img, (40, 390), (200, 450), (40, 160, 40), -1)
    cv2.putText(img, "EXIT", (70, 435), cv2.FONT_HERSHEY_DUPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)

    test_img_path = os.path.join(MODELS_DIR, "test_ocr_scene.png")
    cv2.imwrite(test_img_path, img)
    print(f"Created test image at: {test_img_path}")
    return test_img_path, img

if __name__ == "__main__":
    char_dict = load_dict(DICT_PATH)

    print("\nLoading ONNX Sessions...")
    det_session = ort.InferenceSession(DET_MODEL, providers=["CPUExecutionProvider"])
    rec_session = ort.InferenceSession(REC_MODEL, providers=["CPUExecutionProvider"])
    print("Sessions loaded successfully!")

    test_path, img = create_test_image()

    # Detection inference
    print("\n--- RUNNING PP-OCRv4 DETECTION ---")
    det_input = preprocess_det(img, target_size=640)
    input_name_det = det_session.get_inputs()[0].name
    det_outputs = det_session.run(None, {input_name_det: det_input})
    pred_map = det_outputs[0]
    print(f"Detector output shape: {pred_map.shape}, min={pred_map.min():.4f}, max={pred_map.max():.4f}")

    db_post = DBPostProcess(thresh=0.3, box_thresh=0.5, unclip_ratio=1.6)
    boxes, det_scores = db_post(pred_map, (img.shape[0], img.shape[1]))
    print(f"Detected {len(boxes)} text regions!")

    # Sort boxes top-to-bottom for reading order
    boxes_with_y = [(b, s, np.mean(b[:, 1])) for b, s in zip(boxes, det_scores)]
    boxes_with_y.sort(key=lambda x: x[2])

    print("\n--- RUNNING PP-OCRv4 SELECTIVE RECOGNITION ---")
    annotated = img.copy()
    rec_input_name = rec_session.get_inputs()[0].name

    for i, (box, det_score, _) in enumerate(boxes_with_y):
        crop = crop_roi(img, box)
        if crop is None or crop.shape[0] < 5 or crop.shape[1] < 5:
            continue

        rec_input = preprocess_rec(crop, target_h=48)
        rec_outputs = rec_session.run(None, {rec_input_name: rec_input})
        logits = rec_outputs[0]
        
        text, text_conf, preds = ctc_decode(logits, char_dict)
        print(f"Region {i+1} [DetConf: {det_score:.3f}]: Recognized '{text}' [RecConf: {text_conf:.3f}] (Argmax: {preds[:15]})")

        # Draw on annotated
        pts = box.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
        cv2.putText(annotated, text, (int(box[0][0]), max(15, int(box[0][1]) - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    annotated_path = os.path.join(MODELS_DIR, "test_ocr_annotated.png")
    cv2.imwrite(annotated_path, annotated)
    print(f"\nSaved annotated visualization to: {annotated_path}")
