import cv2

backends = [
    ("CAP_AVFOUNDATION", cv2.CAP_AVFOUNDATION),
    ("CAP_ANY", cv2.CAP_ANY),
    ("CAP_V4L2", cv2.CAP_V4L2),
]

for name, backend in backends:
    try:
        cap = cv2.VideoCapture(0, backend)
        opened = cap.isOpened()
        print(f"{name}: opened={opened}")
        if opened:
            ret, frame = cap.read()
            print(f"  frame read={ret}, shape={frame.shape if ret else None}")
        cap.release()
    except Exception as e:
        print(f"{name}: error={e}")
