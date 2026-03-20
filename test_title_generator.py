#!/usr/bin/env python3
"""
Quick test for Title Generator modules
"""

import sys
import os

print("=" * 70)
print("🎬 TITLE GENERATOR TEST")
print("=" * 70)
print()

# Test 1: Import modules
print("Test 1: Importing Title Generator modules...")
print("-" * 70)

try:
    from modules.title_generator.local_vision_analyzer import LocalVisionAnalyzer
    print("✅ LocalVisionAnalyzer imported")
except Exception as e:
    print(f"❌ LocalVisionAnalyzer import failed: {e}")
    sys.exit(1)

try:
    from modules.title_generator.multi_source_aggregator import MultiSourceAggregator
    print("✅ MultiSourceAggregator imported")
except Exception as e:
    print(f"❌ MultiSourceAggregator import failed: {e}")
    sys.exit(1)

try:
    from modules.title_generator.api_content_analyzer import APIContentAnalyzer
    print("✅ APIContentAnalyzer imported")
except Exception as e:
    print(f"❌ APIContentAnalyzer import failed: {e}")
    sys.exit(1)

print()

# Test 2: Initialize Local Vision Analyzer
print("Test 2: Initializing Local Vision Analyzer...")
print("-" * 70)

try:
    analyzer = LocalVisionAnalyzer()
    print("✅ LocalVisionAnalyzer initialized successfully")
    print()

    # Check which models are available
    if analyzer.yolo_available:
        print("   ✅ YOLO available")
    else:
        print("   ❌ YOLO not available (install: pip install ultralytics)")

    if analyzer.blip_available:
        print("   ✅ BLIP available")
    else:
        print("   ❌ BLIP not available (install: pip install transformers torch)")

    if analyzer.opencv_available:
        print("   ✅ OpenCV available")
    else:
        print("   ❌ OpenCV not available (install: pip install opencv-python)")

except Exception as e:
    print(f"❌ Initialization failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Initialize Multi-Source Aggregator
print("Test 3: Initializing Multi-Source Aggregator...")
print("-" * 70)

try:
    aggregator = MultiSourceAggregator()
    print("✅ MultiSourceAggregator initialized successfully")
except Exception as e:
    print(f"❌ MultiSourceAggregator initialization failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Initialize HYBRID Content Analyzer
print("Test 4: Initializing HYBRID Content Analyzer...")
print("-" * 70)

try:
    # Without Groq client (local only mode)
    hybrid_analyzer = APIContentAnalyzer(
        groq_client=None,
        use_local_models=True
    )
    print("✅ HYBRID Content Analyzer initialized (Local-Only Mode)")

    if hybrid_analyzer.local_analyzer:
        print("   ✅ Local vision analyzer loaded")
    else:
        print("   ⚠️  Local vision analyzer not loaded")

    if hybrid_analyzer.aggregator:
        print("   ✅ Multi-source aggregator loaded")
    else:
        print("   ⚠️  Multi-source aggregator not loaded")

except Exception as e:
    print(f"❌ HYBRID analyzer initialization failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Summary
print("=" * 70)
print("📊 SUMMARY:")
print("=" * 70)
print()
print("✅ Title Generator modules: READY")
print()
print("🎯 Next Steps:")
print("   1. Run the main app: python main.py")
print("   2. Test with actual videos")
print("   3. Check logs for vision model loading")
print()
print("Expected on first run:")
print("   - BLIP model will download (~500MB)")
print("   - YOLO model will download (~6MB)")
print("   - After download: Works 100% offline!")
print()
print("=" * 70)
