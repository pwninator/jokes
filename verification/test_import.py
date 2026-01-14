
import sys
import os
sys.path.append(os.path.abspath('py_quill'))
print("Path added")
try:
    from common import image_generation
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
