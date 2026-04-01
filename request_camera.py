"""Request camera permission via AVFoundation the proper macOS way."""
import objc
from AVFoundation import AVCaptureDevice, AVMediaTypeVideo, AVAuthorizationStatusAuthorized, AVAuthorizationStatusNotDetermined
import time

status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
print(f"Current camera auth status: {status}  (0=not determined, 1=denied, 2=authorized)")

if status == 0:  # not determined
    print("Requesting camera permission — click Allow in the popup...")
    result = [None]
    def handler(granted):
        result[0] = granted
        print(f"Permission granted: {granted}")
    AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeVideo, handler)
    # wait for callback
    for _ in range(30):
        time.sleep(0.5)
        if result[0] is not None:
            break
elif status == 1:
    print("Camera permission DENIED. Go to System Settings → Privacy & Security → Camera and enable your terminal.")
elif status == 2:
    print("Camera permission already AUTHORIZED.")

# Final check
status2 = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
print(f"Final status: {status2}")
