import sys

packages = ["onnxruntime", "onnx", "paddle2onnx", "paddle", "cv2", "torch"]
for p in packages:
    try:
        mod = __import__(p)
        print(f"{p}: {getattr(mod, '__version__', 'installed')}")
    except ImportError:
        print(f"{p}: NOT INSTALLED")
