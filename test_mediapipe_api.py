"""
Test MediaPipe API structure for version 0.10.31
Run this to find correct import paths
"""

print("=" * 60)
print("MediaPipe API Structure Test")
print("=" * 60)

try:
    import mediapipe
    print(f"\n✅ MediaPipe version: {mediapipe.__version__}")
    print(f"✅ MediaPipe location: {mediapipe.__file__}")
except ImportError as e:
    print(f"\n❌ MediaPipe not installed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("Testing import paths...")
print("=" * 60)

# Test 1: Old API (pre 0.10)
print("\n1. Testing old API: import mediapipe as mp; mp.solutions")
try:
    import mediapipe as mp
    solutions = mp.solutions
    print(f"   ✅ mp.solutions exists: {solutions}")
    print(f"   Available: {dir(solutions)}")
except AttributeError as e:
    print(f"   ❌ Failed: {e}")

# Test 2: mediapipe.python.solutions (suggested fix)
print("\n2. Testing: from mediapipe.python.solutions import face_mesh")
try:
    from mediapipe.python.solutions import face_mesh
    print(f"   ✅ mediapipe.python.solutions.face_mesh works!")
except (ImportError, ModuleNotFoundError) as e:
    print(f"   ❌ Failed: {e}")

# Test 3: mediapipe.solutions (direct)
print("\n3. Testing: from mediapipe.solutions import face_mesh")
try:
    from mediapipe.solutions import face_mesh
    print(f"   ✅ mediapipe.solutions.face_mesh works!")
except (ImportError, AttributeError) as e:
    print(f"   ❌ Failed: {e}")

# Test 4: New tasks API (0.10+)
print("\n4. Testing new API: from mediapipe.tasks.python import vision")
try:
    from mediapipe.tasks.python import vision
    print(f"   ✅ mediapipe.tasks.python.vision works!")
    print(f"   Available: {dir(vision)}")
except (ImportError, ModuleNotFoundError) as e:
    print(f"   ❌ Failed: {e}")

# Test 5: Check package structure
print("\n5. Checking MediaPipe package contents:")
try:
    import mediapipe
    import os
    mp_dir = os.path.dirname(mediapipe.__file__)
    print(f"   MediaPipe directory: {mp_dir}")
    contents = os.listdir(mp_dir)
    print(f"   Contents: {[item for item in contents if not item.startswith('_')]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
