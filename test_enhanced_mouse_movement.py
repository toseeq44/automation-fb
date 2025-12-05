#!/usr/bin/env python3
"""
Test Script for Enhanced Mouse Movement
Demonstrates improvements over original implementation
"""

import time
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import pyautogui
    from modules.auto_uploader.browser.mouse_controller_enhanced import EnhancedMouseController
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please install: pip install pyautogui")
    sys.exit(1)


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_user_interference_detection():
    """Test: Bot pauses when user moves mouse"""
    print_header("TEST 1: User Interference Detection")

    mouse = EnhancedMouseController(speed_factor=0.6)

    print("🖱️  Bot will move mouse in 3 seconds...")
    print("👉  TRY THIS: Move your mouse during bot movement!")
    print("     Bot should pause and wait for you to finish.")
    time.sleep(3)

    # Get screen size
    screen_width, screen_height = pyautogui.size()

    # Define movement path
    start_x, start_y = 100, 100
    end_x, end_y = screen_width - 100, screen_height - 100

    print(f"\n🎯 Moving from ({start_x},{start_y}) to ({end_x},{end_y})")
    print("⏱️  This will take ~5 seconds (slow, natural movement)")
    print("🚨 MOVE YOUR MOUSE NOW to test interference detection!\n")

    # Move slowly so user has time to interfere
    success = mouse.move_to_position(end_x, end_y, duration=5.0)

    if success:
        print("\n✅ Movement completed!")
        print("   Did the bot pause when you moved the mouse? ✓")
    else:
        print("\n❌ Movement failed")


def test_slower_natural_movement():
    """Test: Slower movement with easing"""
    print_header("TEST 2: Slower, More Natural Movement")

    mouse = EnhancedMouseController(speed_factor=0.6)  # 40% slower

    screen_width, screen_height = pyautogui.size()

    print("🎯 Testing different movement speeds and patterns:\n")

    # Test 1: Short distance
    print("1️⃣  Short movement (200px) with cubic easing...")
    start = pyautogui.position()
    mouse.move_to_position(start[0] + 200, start[1], duration=1.5)
    print("   ✓ Completed (should accelerate then decelerate)")
    time.sleep(1)

    # Test 2: Medium distance
    print("\n2️⃣  Medium movement (500px) with auto-calculated duration...")
    start = pyautogui.position()
    mouse.move_to_position(start[0], start[1] + 500)
    print("   ✓ Completed (duration based on distance)")
    time.sleep(1)

    # Test 3: Long distance
    print("\n3️⃣  Long movement (diagonal) - should be slow and smooth...")
    mouse.move_to_position(screen_width // 2, screen_height // 2, duration=3.0)
    print("   ✓ Completed (notice the curved path)")
    time.sleep(1)

    print("\n✅ Natural movement test completed!")
    print("   Did you notice:")
    print("   - Movements start slow, accelerate, then slow down?")
    print("   - Curved paths (not straight lines)?")
    print("   - Variable speed along the curve?")


def test_hesitation_movement():
    """Test: Movement with human-like hesitation"""
    print_header("TEST 3: Movement with Hesitation")

    mouse = EnhancedMouseController(speed_factor=0.6)

    screen_width, screen_height = pyautogui.size()

    print("🎯 Testing hesitation (sometimes pauses mid-movement):\n")
    print("   Running 5 movements with 30% hesitation chance...")
    print("   Watch for occasional pauses/corrections!\n")

    for i in range(5):
        # Random target
        target_x = screen_width // 4 + (i * 150)
        target_y = screen_height // 4 + ((i % 2) * 200)

        print(f"   Movement {i+1}/5 → ({target_x},{target_y})...", end=" ")
        mouse.move_with_hesitation(target_x, target_y, hesitation_chance=0.3)
        print("✓")
        time.sleep(0.5)

    print("\n✅ Hesitation test completed!")
    print("   Did you see any movements pause mid-way?")


def test_circular_idle_animation():
    """Test: Circular idle movement"""
    print_header("TEST 4: Circular Idle Animation (Trust Building)")

    mouse = EnhancedMouseController(speed_factor=0.6)

    screen_width, screen_height = pyautogui.size()

    # Move to center
    center_x, center_y = screen_width // 2, screen_height // 2
    mouse.move_to_position(center_x, center_y)

    print("🎯 Watch the mouse move in a small circle for 5 seconds...")
    print("   This simulates 'thinking' during processing delays.\n")

    mouse.circular_idle_movement(duration=5.0, radius=40)

    print("\n✅ Circular idle animation completed!")
    print("   Notice:")
    print("   - Smooth circular motion")
    print("   - Slight variations in radius")
    print("   - Variable speed around the circle")


def test_micro_jitter():
    """Test: Micro-jitter during hover"""
    print_header("TEST 5: Micro-Jitter (Realistic Tremors)")

    mouse = EnhancedMouseController(speed_factor=0.6)

    screen_width, screen_height = pyautogui.size()
    target_x, target_y = screen_width // 2, screen_height // 2

    print("🎯 Moving to center and hovering for 3 seconds...")
    print("   Watch closely for tiny tremors (±1-2 pixels)\n")

    mouse.hover_over_position(target_x, target_y, hover_duration=3.0)

    print("\n✅ Micro-jitter test completed!")
    print("   Did you notice tiny vibrations during hover?")


def test_adaptive_typing():
    """Test: Adaptive typing speed"""
    print_header("TEST 6: Adaptive Typing Speed")

    mouse = EnhancedMouseController(speed_factor=0.6)

    print("🎯 Testing adaptive typing (different speeds for different characters):\n")

    test_strings = [
        ("Hello", "Normal text (fast)"),
        ("12345", "Numbers (slower)"),
        ("CAPS", "Capitals (slightly slower)"),
        ("aaa", "Repeated characters (slower)"),
    ]

    for text, description in test_strings:
        print(f"   Typing: '{text}' - {description}")
        mouse.type_text(text, interval=None)  # Adaptive
        print(f"   ✓ Completed")
        time.sleep(0.5)

    print("\n✅ Adaptive typing test completed!")
    print("   Did you notice different typing speeds?")


def demo_complete_workflow():
    """Demo: Complete realistic workflow"""
    print_header("DEMO: Complete Realistic Workflow")

    mouse = EnhancedMouseController(speed_factor=0.6)

    screen_width, screen_height = pyautogui.size()

    print("🎯 Simulating realistic user behavior:\n")

    # Step 1: Move to "login button"
    print("1️⃣  Moving to login button...")
    login_x, login_y = screen_width // 3, screen_height // 3
    mouse.move_with_hesitation(login_x, login_y)
    time.sleep(0.5)

    # Step 2: Idle animation (thinking)
    print("2️⃣  Thinking... (circular idle)")
    mouse.circular_idle_movement(duration=2.0, radius=30)

    # Step 3: Move to "email field"
    print("3️⃣  Moving to email field...")
    email_x, email_y = screen_width // 2, screen_height // 2
    mouse.move_to_position(email_x, email_y, duration=1.5)
    time.sleep(0.3)

    # Step 4: Type email
    print("4️⃣  Typing email address...")
    mouse.type_text("user@example.com", interval=None)
    time.sleep(0.5)

    # Step 5: Random fidgeting
    print("5️⃣  Brief fidgeting...")
    mouse.random_idle_movement(duration=1.5, max_distance=50)

    # Step 6: Final position
    print("6️⃣  Moving to submit button...")
    submit_x, submit_y = screen_width // 2, screen_height - 200
    mouse.move_to_position(submit_x, submit_y, duration=2.0)

    print("\n✅ Complete workflow demo finished!")
    print("   This demonstrates realistic human-like behavior!")


def print_improvements_summary():
    """Print summary of improvements"""
    print("\n" + "=" * 70)
    print("  IMPROVEMENTS SUMMARY")
    print("=" * 70 + "\n")

    improvements = [
        ("🚨 User Interference Detection", "Bot pauses when user moves mouse, waits 1-4s after user stops"),
        ("🐢 Slower Movement (40%)", "More natural speed, harder to detect as bot"),
        ("📈 Easing Functions", "Cubic in-out: accelerates at start, decelerates at end"),
        ("🎲 Micro-Jitter", "±1-2px tremors during movement (realistic hand tremors)"),
        ("⏸️  Hesitation", "15% chance to pause mid-movement (very human-like)"),
        ("🎯 Adaptive Control Points", "Variance scales with distance (not fixed ±100px)"),
        ("🔄 Variable Speed", "Speed varies throughout movement (not constant)"),
        ("💭 Micro-Pauses", "10% chance of tiny pauses during movement"),
        ("⌨️  Adaptive Typing", "Different speeds: numbers slow, letters fast"),
        ("🎨 Circular Animation", "Randomized radius and speed (not mechanical)"),
        ("🖱️  Canvas Fingerprint", "Less predictable patterns evade detection"),
    ]

    for i, (feature, description) in enumerate(improvements, 1):
        print(f"{i:2d}. {feature}")
        print(f"    {description}\n")

    print("=" * 70)
    print("\n🎯 KEY FEATURES:")
    print("  ✓ Detects and handles user mouse interference")
    print("  ✓ Slower, more natural movements")
    print("  ✓ Multiple easing functions")
    print("  ✓ Micro-jitter and hesitation")
    print("  ✓ Canvas fingerprinting evasion")
    print("  ✓ Backward compatible (drop-in replacement)")
    print("\n" + "=" * 70 + "\n")


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "ENHANCED MOUSE MOVEMENT TESTS" + " " * 24 + "║")
    print("╚" + "═" * 68 + "╝")

    print("\n⚠️  IMPORTANT NOTES:")
    print("   - Tests will move your mouse cursor")
    print("   - Move mouse to top-left corner to abort (FAILSAFE)")
    print("   - Try moving mouse during TEST 1 to see interference detection")
    print("\n" + "=" * 70)

    input("\n👉 Press ENTER to start tests... ")

    try:
        # Run all tests
        test_user_interference_detection()
        time.sleep(2)

        test_slower_natural_movement()
        time.sleep(2)

        test_hesitation_movement()
        time.sleep(2)

        test_circular_idle_animation()
        time.sleep(2)

        test_micro_jitter()
        time.sleep(2)

        test_adaptive_typing()
        time.sleep(2)

        demo_complete_workflow()
        time.sleep(2)

        # Show summary
        print_improvements_summary()

        print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY! 🎉\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during tests: {e}")


if __name__ == "__main__":
    main()
