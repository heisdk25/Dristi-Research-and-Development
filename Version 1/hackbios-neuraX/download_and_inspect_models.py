import os
import hashlib
import tarfile
import urllib.request
import onnx
import onnxruntime as ort

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ppocrv4")
os.makedirs(MODELS_DIR, exist_ok=True)

URLS = {
    "det_tar": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar",
    "rec_en_tar": "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar",
    "rec_ch_tar": "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar",
    "en_dict": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.7/ppocr/utils/en_dict.txt",
    "ppocr_keys_v1": "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.7/ppocr/utils/ppocr_keys_v1.txt",
    "det_onnx": "https://huggingface.co/xberg-io/paddleocr-onnx-models/resolve/main/ch_PP-OCRv4_det_infer.onnx",
    "rec_en_onnx": "https://huggingface.co/xberg-io/paddleocr-onnx-models/resolve/main/en_PP-OCRv4_rec_infer.onnx"
}

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def download_file(url, target_path):
    print(f"Downloading {url} -> {target_path} ...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response, open(target_path, "wb") as out_file:
        data = response.read()
        out_file.write(data)
    print(f"Downloaded {os.path.basename(target_path)} ({len(data)} bytes, SHA-256: {sha256_file(target_path)})")
    return target_path

def inspect_onnx_model(onnx_path):
    print(f"\n=======================================================")
    print(f"INSPECTING ONNX MODEL: {os.path.basename(onnx_path)}")
    print(f"Path: {onnx_path}")
    print(f"Size: {os.path.getsize(onnx_path)} bytes")
    print(f"SHA-256: {sha256_file(onnx_path)}")
    print(f"=======================================================")

    model = onnx.load(onnx_path)
    print(f"IR Version: {model.ir_version}, Producer: {model.producer_name} {model.producer_version}")
    
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    
    print("\n[INPUTS]:")
    for i in session.get_inputs():
        print(f"  Name: '{i.name}', Type: {i.type}, Shape: {i.shape}")

    print("\n[OUTPUTS]:")
    for o in session.get_outputs():
        print(f"  Name: '{o.name}', Type: {o.type}, Shape: {o.shape}")

if __name__ == "__main__":
    # 1. Download official Paddle inference tarballs
    det_tar = os.path.join(MODELS_DIR, "ch_PP-OCRv4_det_infer.tar")
    rec_tar = os.path.join(MODELS_DIR, "en_PP-OCRv4_rec_infer.tar")
    en_dict = os.path.join(MODELS_DIR, "en_dict.txt")

    if not os.path.exists(det_tar):
        download_file(URLS["det_tar"], det_tar)
    if not os.path.exists(rec_tar):
        download_file(URLS["rec_en_tar"], rec_tar)
    if not os.path.exists(en_dict):
        download_file(URLS["en_dict"], en_dict)

    # Extract tarballs
    for tar_file in [det_tar, rec_tar]:
        print(f"\nExtracting {tar_file}...")
        with tarfile.open(tar_file) as tar:
            tar.extractall(path=MODELS_DIR)
            for m in tar.getmembers():
                full_path = os.path.join(MODELS_DIR, m.name)
                if os.path.isfile(full_path):
                    print(f"  {m.name} -> Size: {os.path.getsize(full_path)} bytes, SHA-256: {sha256_file(full_path)}")

    # 2. Download verified pre-converted ONNX models
    det_onnx = os.path.join(MODELS_DIR, "ch_PP-OCRv4_det_infer.onnx")
    rec_en_onnx = os.path.join(MODELS_DIR, "en_PP-OCRv4_rec_infer.onnx")

    if not os.path.exists(det_onnx):
        download_file(URLS["det_onnx"], det_onnx)
    if not os.path.exists(rec_en_onnx):
        download_file(URLS["rec_en_onnx"], rec_en_onnx)

    # 3. Inspect ONNX models
    inspect_onnx_model(det_onnx)
    inspect_onnx_model(rec_en_onnx)

    # 4. Inspect dictionary length vs model classes
    with open(en_dict, "r", encoding="utf-8") as f:
        lines = [line.strip("\r\n") for line in f.readlines()]
    print(f"\nen_dict.txt lines count: {len(lines)}")
    print(f"Sample characters (first 20): {lines[:20]}")
    print(f"Sample characters (last 10): {lines[-10:]}")
