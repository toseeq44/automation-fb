"""
modules/video_editor/transitions.py
Video Transitions and Effects
Includes: Fade, Crossfade, Slide, Wipe, Zoom, etc.
"""

import numpy as np
from typing import List
from modules.logging.logger import get_logger

logger = get_logger(__name__)

try:
    from moviepy import VideoFileClip, CompositeVideoClip, concatenate_videoclips, vfx, VideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


# ==================== BASIC TRANSITIONS ====================

def _clamp_duration(clip1: VideoFileClip, clip2: VideoFileClip, duration: float) -> float:
    """Clamp transition duration to valid clip lengths."""
    return max(0.0, min(duration, clip1.duration, clip2.duration))

def fade_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Simple fade transition: clip1 fades out, clip2 fades in

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    # Fade out first clip
    # MoviePy 2.x: Use with_effects([vfx.FadeOut()]) instead of fx(vfx.fadeout)
    clip1 = clip1.with_effects([vfx.FadeOut(duration)])

    # Fade in second clip
    # MoviePy 2.x: Use with_effects([vfx.FadeIn()]) instead of fx(vfx.fadein)
    clip2 = clip2.with_effects([vfx.FadeIn(duration)])

    # Concatenate
    result = concatenate_videoclips([clip1, clip2], method='compose')

    logger.info(f"Fade transition applied: {duration}s")
    return result


def crossfade_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Crossfade transition: smooth blend between two clips

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    # Add crossfade
    # MoviePy 2.x: Use with_effects([vfx.CrossFadeOut()]) instead of fx(vfx.crossfadeout)
    clip1 = clip1.with_effects([vfx.CrossFadeOut(duration)])
    clip2 = clip2.with_effects([vfx.CrossFadeIn(duration)])

    # Concatenate with overlap
    result = concatenate_videoclips([clip1, clip2], method='compose', padding=-duration)

    logger.info(f"Crossfade transition applied: {duration}s")
    return result


# ==================== DIRECTIONAL TRANSITIONS ====================

def slide_transition(clip1: VideoFileClip, clip2: VideoFileClip,
                    duration: float = 1.0, direction: str = 'left'):
    """
    Slide transition: clip2 slides in over clip1

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
        direction: Slide direction ('left', 'right', 'up', 'down')
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    w, h = clip1.size

    def make_frame(t):
        """Generate frame at time t during transition"""
        # Calculate slide progress (0 to 1)
        progress = min(t / duration, 1.0)

        if direction == 'left':
            # Clip2 slides from right to left
            offset = int(w * (1 - progress))
            pos = (offset, 0)
        elif direction == 'right':
            # Clip2 slides from left to right
            offset = int(-w * (1 - progress))
            pos = (offset, 0)
        elif direction == 'up':
            # Clip2 slides from bottom to top
            offset = int(h * (1 - progress))
            pos = (0, offset)
        elif direction == 'down':
            # Clip2 slides from top to bottom
            offset = int(-h * (1 - progress))
            pos = (0, offset)
        else:
            raise ValueError(f"Invalid direction: {direction}")

        return pos

    # Create transition clip
    transition_start = clip1.duration - duration
    # MoviePy 2.x: Use with_start() and with_position() instead of set_start() and set_position()
    clip2_moving = clip2.with_start(transition_start).with_position(make_frame)

    # Composite
    result = CompositeVideoClip([clip1, clip2_moving])

    logger.info(f"Slide transition applied: {direction}, {duration}s")
    return result


def wipe_transition(clip1: VideoFileClip, clip2: VideoFileClip,
                   duration: float = 1.0, direction: str = 'left'):
    """
    Wipe transition: clip2 wipes over clip1

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
        direction: Wipe direction ('left', 'right', 'up', 'down')
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    w, h = clip1.size
    transition_start = clip1.duration - duration

    def mask_frame(t):
        """Create wipe mask"""
        if t < transition_start:
            # Before transition - show clip1
            mask = np.ones((h, w), dtype=np.uint8) * 255
        elif t >= clip1.duration:
            # After transition - show clip2
            mask = np.zeros((h, w), dtype=np.uint8)
        else:
            # During transition
            progress = (t - transition_start) / duration

            mask = np.zeros((h, w), dtype=np.uint8)

            if direction == 'left':
                # Wipe from left to right
                cutoff = int(w * progress)
                mask[:, :cutoff] = 0
                mask[:, cutoff:] = 255
            elif direction == 'right':
                # Wipe from right to left
                cutoff = int(w * (1 - progress))
                mask[:, :cutoff] = 255
                mask[:, cutoff:] = 0
            elif direction == 'up':
                # Wipe from top to bottom
                cutoff = int(h * progress)
                mask[:cutoff, :] = 0
                mask[cutoff:, :] = 255
            elif direction == 'down':
                # Wipe from bottom to top
                cutoff = int(h * (1 - progress))
                mask[:cutoff, :] = 255
                mask[cutoff:, :] = 0

        return mask

    # Apply mask to clip1 (disappearing clip)
    clip1_masked = clip1.transform(lambda gf, t: mask_frame(t) / 255.0 * gf(t), apply_to=['mask'])

    # Composite clips
    # MoviePy 2.x: Use with_start() instead of set_start()
    clip2_timed = clip2.with_start(transition_start)
    result = CompositeVideoClip([clip2_timed, clip1_masked])

    logger.info(f"Wipe transition applied: {direction}, {duration}s")
    return result


# ==================== ZOOM TRANSITIONS ====================

def zoom_in_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Zoom in transition: clip1 zooms in, then clip2 appears

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    def zoom_effect(get_frame, t):
        """Apply zoom effect"""
        if t < clip1.duration - duration:
            # Normal playback
            return get_frame(t)
        else:
            # Zoom in during transition
            frame = get_frame(t)
            progress = (t - (clip1.duration - duration)) / duration
            scale = 1.0 + progress * 0.5  # Zoom from 1.0x to 1.5x

            h, w = frame.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)

            # Resize and center crop
            try:
                from PIL import Image
                img = Image.fromarray(frame)
                img = img.resize((new_w, new_h), Image.LANCZOS)

                # Center crop
                left = (new_w - w) // 2
                top = (new_h - h) // 2
                img = img.crop((left, top, left + w, top + h))

                return np.array(img)
            except ImportError:
                return frame

    clip1_zoomed = clip1.transform(zoom_effect)
    clip1_zoomed = clip1_zoomed.with_effects([vfx.CrossFadeOut(duration)])
    clip2_faded = clip2.with_effects([vfx.CrossFadeIn(duration)])

    result = concatenate_videoclips([clip1_zoomed, clip2_faded], method='compose', padding=-duration)

    logger.info(f"Zoom in transition applied: {duration}s")
    return result


def zoom_out_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Zoom out transition: clip1 zooms out, then clip2 appears

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    def zoom_effect(get_frame, t):
        """Apply zoom out effect"""
        if t < clip1.duration - duration:
            return get_frame(t)
        else:
            frame = get_frame(t)
            progress = (t - (clip1.duration - duration)) / duration
            scale = 1.0 - progress * 0.3  # Zoom from 1.0x to 0.7x

            h, w = frame.shape[:2]
            new_h, new_w = max(1, int(h * scale)), max(1, int(w * scale))

            try:
                from PIL import Image
                img = Image.fromarray(frame)
                img = img.resize((new_w, new_h), Image.LANCZOS)

                # Pad to original size
                result = np.zeros((h, w, 3), dtype=np.uint8)
                top = (h - new_h) // 2
                left = (w - new_w) // 2
                result[top:top+new_h, left:left+new_w] = np.array(img)

                return result
            except ImportError:
                return frame

    clip1_zoomed = clip1.transform(zoom_effect)
    clip1_zoomed = clip1_zoomed.with_effects([vfx.CrossFadeOut(duration)])
    clip2_faded = clip2.with_effects([vfx.CrossFadeIn(duration)])

    result = concatenate_videoclips([clip1_zoomed, clip2_faded], method='compose', padding=-duration)

    logger.info(f"Zoom out transition applied: {duration}s")
    return result


# ==================== DISSOLVE TRANSITIONS ====================

def dissolve_transition(clip1: VideoFileClip, clip2: VideoFileClip,
                       duration: float = 1.0, pattern: str = 'random'):
    """
    Dissolve transition: pixels fade from clip1 to clip2

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
        pattern: Dissolve pattern ('random', 'grid', 'radial')
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    w, h = clip1.size
    transition_start = clip1.duration - duration

    # Create dissolve mask pattern
    if pattern == 'random':
        # Random pixel dissolve
        mask_pattern = np.random.random((h, w))
    elif pattern == 'grid':
        # Grid pattern
        grid_size = 10
        mask_pattern = np.zeros((h, w))
        for i in range(0, h, grid_size):
            for j in range(0, w, grid_size):
                mask_pattern[i:i+grid_size, j:j+grid_size] = np.random.random()
    elif pattern == 'radial':
        # Radial from center
        center_y, center_x = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]
        distance = np.sqrt((X - center_x) ** 2 + (Y - center_y) ** 2)
        max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
        mask_pattern = distance / max_dist
    else:
        raise ValueError(f"Invalid pattern: {pattern}")

    def make_frame(t):
        """Composite frames with dissolve"""
        if t < transition_start:
            return clip1.get_frame(t)
        elif t >= clip1.duration:
            return clip2.get_frame(t - clip1.duration)
        else:
            # During transition
            progress = (t - transition_start) / duration

            # Get frames
            frame1 = clip1.get_frame(t)
            frame2 = clip2.get_frame(t - transition_start)

            # Create blend mask based on progress
            blend_mask = (mask_pattern < progress).astype(np.float32)
            blend_mask = np.stack([blend_mask] * 3, axis=-1)

            # Blend frames
            result = frame1 * (1 - blend_mask) + frame2 * blend_mask

            return result.astype(np.uint8)

    result = VideoClip(make_frame, duration=clip1.duration + clip2.duration - duration)
    result = result.with_fps(clip1.fps)

    if clip1.audio:
        result = result.with_audio(clip1.audio)

    logger.info(f"Dissolve transition applied: {pattern}, {duration}s")
    return result


# ==================== SPECIAL TRANSITIONS ====================

def rotate_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Rotate transition: clip1 rotates out, clip2 rotates in

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    def rotate_out(get_frame, t):
        """Rotate out effect"""
        if t < clip1.duration - duration:
            return get_frame(t)
        else:
            progress = (t - (clip1.duration - duration)) / duration
            angle = progress * 90  # Rotate 90 degrees

            frame = get_frame(t)
            # Simple rotation simulation (would need proper implementation)
            return frame

    clip1_rotated = clip1.transform(rotate_out)
    clip1_rotated = clip1_rotated.with_effects([vfx.CrossFadeOut(duration)])

    clip2_faded = clip2.with_effects([vfx.CrossFadeIn(duration)])

    result = concatenate_videoclips([clip1_rotated, clip2_faded], method='compose', padding=-duration)

    logger.info(f"Rotate transition applied: {duration}s")
    return result


def blur_transition(clip1: VideoFileClip, clip2: VideoFileClip, duration: float = 1.0):
    """
    Blur transition: clip1 blurs out, clip2 blurs in

    Args:
        clip1: First video clip
        clip2: Second video clip
        duration: Transition duration in seconds
    """
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        logger.warning("scipy not available, using simple fade instead")
        return crossfade_transition(clip1, clip2, duration)

    duration = _clamp_duration(clip1, clip2, duration)
    if duration == 0:
        return concatenate_videoclips([clip1, clip2], method='compose')

    def blur_out(get_frame, t):
        """Blur out effect"""
        if t < clip1.duration - duration:
            return get_frame(t)
        else:
            frame = get_frame(t)
            progress = (t - (clip1.duration - duration)) / duration
            blur_amount = progress * 10  # Max blur radius

            blurred = np.zeros_like(frame)
            for i in range(3):
                blurred[:, :, i] = gaussian_filter(frame[:, :, i], sigma=blur_amount)

            return blurred.astype(np.uint8)

    def blur_in(get_frame, t):
        """Blur in effect"""
        if t > duration:
            return get_frame(t)
        else:
            frame = get_frame(t)
            progress = t / duration
            blur_amount = (1 - progress) * 10

            blurred = np.zeros_like(frame)
            for i in range(3):
                blurred[:, :, i] = gaussian_filter(frame[:, :, i], sigma=blur_amount)

            return blurred.astype(np.uint8)

    clip1_blurred = clip1.transform(blur_out)
    clip2_blurred = clip2.transform(blur_in)
    clip1_blurred = clip1_blurred.with_effects([vfx.CrossFadeOut(duration)])
    clip2_blurred = clip2_blurred.with_effects([vfx.CrossFadeIn(duration)])

    result = concatenate_videoclips([clip1_blurred, clip2_blurred], method='compose', padding=-duration)

    logger.info(f"Blur transition applied: {duration}s")
    return result


# ==================== TRANSITION MANAGER ====================

class TransitionManager:
    """Manage transitions between multiple clips"""

    TRANSITIONS = {
        'fade': fade_transition,
        'crossfade': crossfade_transition,
        'slide_left': lambda c1, c2, d: slide_transition(c1, c2, d, 'left'),
        'slide_right': lambda c1, c2, d: slide_transition(c1, c2, d, 'right'),
        'slide_up': lambda c1, c2, d: slide_transition(c1, c2, d, 'up'),
        'slide_down': lambda c1, c2, d: slide_transition(c1, c2, d, 'down'),
        'wipe_left': lambda c1, c2, d: wipe_transition(c1, c2, d, 'left'),
        'wipe_right': lambda c1, c2, d: wipe_transition(c1, c2, d, 'right'),
        'wipe_up': lambda c1, c2, d: wipe_transition(c1, c2, d, 'up'),
        'wipe_down': lambda c1, c2, d: wipe_transition(c1, c2, d, 'down'),
        'zoom_in': zoom_in_transition,
        'zoom_out': zoom_out_transition,
        'dissolve_random': lambda c1, c2, d: dissolve_transition(c1, c2, d, 'random'),
        'dissolve_grid': lambda c1, c2, d: dissolve_transition(c1, c2, d, 'grid'),
        'dissolve_radial': lambda c1, c2, d: dissolve_transition(c1, c2, d, 'radial'),
        'rotate': rotate_transition,
        'blur': blur_transition
    }

    @classmethod
    def apply_transition(cls, clip1: VideoFileClip, clip2: VideoFileClip,
                        transition: str, duration: float = 1.0):
        """
        Apply transition between two clips

        Args:
            clip1: First video clip
            clip2: Second video clip
            transition: Transition type (see TRANSITIONS dict)
            duration: Transition duration in seconds
        """
        if transition not in cls.TRANSITIONS:
            available = ', '.join(cls.TRANSITIONS.keys())
            raise ValueError(f"Unknown transition: {transition}. Available: {available}")

        transition_func = cls.TRANSITIONS[transition]
        return transition_func(clip1, clip2, duration)

    @classmethod
    def merge_with_transitions(cls, clips: List[VideoFileClip],
                              transitions: List[str] = None,
                              duration: float = 1.0):
        """
        Merge multiple clips with transitions

        Args:
            clips: List of video clips
            transitions: List of transition names (one less than clips)
                        If None, uses 'crossfade' for all
            duration: Transition duration in seconds
        """
        if len(clips) < 2:
            raise ValueError("Need at least 2 clips to merge")

        # Default to crossfade if not specified
        if transitions is None:
            transitions = ['crossfade'] * (len(clips) - 1)

        if len(transitions) != len(clips) - 1:
            raise ValueError(f"Need {len(clips) - 1} transitions for {len(clips)} clips")

        # Start with first clip
        result = clips[0]

        # Apply transitions sequentially
        for i, (clip, transition) in enumerate(zip(clips[1:], transitions)):
            logger.info(f"Applying transition {i+1}/{len(transitions)}: {transition}")
            result = cls.apply_transition(result, clip, transition, duration)

        return result

    @classmethod
    def list_transitions(cls):
        """List all available transitions"""
        return list(cls.TRANSITIONS.keys())


# ==================== HELPER FUNCTIONS ====================

def apply_transition(clip1: VideoFileClip, clip2: VideoFileClip,
                    transition: str = 'crossfade', duration: float = 1.0):
    """
    Convenience function to apply transition

    Args:
        clip1: First video clip
        clip2: Second video clip
        transition: Transition type
        duration: Transition duration in seconds
    """
    return TransitionManager.apply_transition(clip1, clip2, transition, duration)


def merge_videos_with_transitions(video_paths: List[str],
                                  output_path: str,
                                  transitions: List[str] = None,
                                  duration: float = 1.0):
    """
    Merge multiple videos with transitions

    Args:
        video_paths: List of video file paths
        output_path: Output file path
        transitions: List of transition names
        duration: Transition duration in seconds
    """
    # Load clips
    clips = [VideoFileClip(path) for path in video_paths]

    # Merge with transitions
    result = TransitionManager.merge_with_transitions(clips, transitions, duration)

    # Export
    result.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # Cleanup
    for clip in clips:
        clip.close()
    result.close()

    logger.info(f"Videos merged with transitions: {output_path}")
    return output_path
