import os
import hashlib
import json
from huggingface_hub import hf_hub_download
import onnx
import onnxruntime as ort

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ppocrv4")
os.makedirs(MODELS_DIR, exist_ok=True)

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def inspect_model(path, name):
    print(f"\n==================================================================")
    print(f"MODEL: {name}")
    print(f"Path: {path}")
    print(f"File Size: {os.path.getsize(path)} bytes")
    print(f"SHA-256: {sha256_file(path)}")
    model = onnx.load(path)
    print(f"IR Version: {model.ir_version}, Producer: {model.producer_name} {model.producer_version}")
    
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    print("Inputs:")
    for i in session.get_inputs():
        print(f"  Name: '{i.name}', Type: {i.type}, Shape: {i.shape}")
    print("Outputs:")
    for o in session.get_outputs():
        print(f"  Name: '{o.name}', Type: {o.type}, Shape: {o.shape}")
    return session

if __name__ == "__main__":
    print("Downloading detector ONNX from cycloneboy/ch_PP-OCRv4_det_infer...")
    det_path = hf_hub_download(repo_id="cycloneboy/ch_PP-OCRv4_det_infer", filename="model.onnx", local_dir=MODELS_DIR)
    det_target = os.path.join(MODELS_DIR, "ch_PP-OCRv4_det_infer.onnx")
    if os.path.exists(det_target):
        os.remove(det_target)
    os.rename(det_path, det_target)

    print("Downloading recognizer ONNX from cycloneboy/en_PP-OCRv4_rec_infer...")
    rec_path = hf_hub_download(repo_id="cycloneboy/en_PP-OCRv4_rec_infer", filename="model.onnx", local_dir=MODELS_DIR)
    rec_target = os.path.join(MODELS_DIR, "en_PP-OCRv4_rec_infer.onnx")
    if os.path.exists(rec_target):
        os.remove(rec_target)
    os.rename(rec_path, rec_target)

    inspect_model(det_target, "PP-OCRv4 Detector")
    inspect_model(rec_target, "PP-OCRv4 English Recognizer")

    # Check tobiichioriguchi models for comparison
    print("\nDownloading tobiichioriguchi/PP-OCRv4_mobile_det_onnx for verification...")
    tobi_det_path = hf_hub_download(repo_id="tobiichioriguchi/PP-OCRv4_mobile_det_onnx", filename="inference.onnx", local_dir=os.path.join(MODELS_DIR, "tobi_det"))
    inspect_model(tobi_det_path, "Tobiichioriguchi Mobile Detector")

    print("\nDownloading tobiichioriguchi/en_PP-OCRv4_mobile_rec_onnx for verification...")
    tobi_rec_path = hf_hub_download(repo_id="tobiichioriguchi/en_PP-OCRv4_mobile_rec_onnx", filename="inference.onnx", local_dir=os.path.join(MODELS_DIR, "tobi_rec"))
    inspect_model(tobi_rec_path, "Tobiichioriguchi English Recognizer")
