"""
Title Generator Main Dialog
User interface for video title generation
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFileDialog, QProgressBar,
                             QTextEdit, QCheckBox, QMessageBox, QGroupBox,
                             QComboBox, QTextBrowser)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from pathlib import Path
from modules.logging.logger import get_logger
from .api_manager import APIKeyManager
from .scanner import VideoScanner
from .renamer import VideoRenamer

# Import with smart detection
from . import ENHANCED_MODE, get_generator, show_model_instructions, models_available

logger = get_logger(__name__)


class ProcessingThread(QThread):
    """Background thread for video processing with enhanced analysis"""

    progress_update = pyqtSignal(int, int, str)  # (current, total, message)
    analysis_update = pyqtSignal(str)  # detailed analysis messages
    processing_complete = pyqtSignal(dict)  # statistics

    def __init__(self, videos, generator, renamer, platform='facebook'):
        super().__init__()
        self.videos = videos
        self.generator = generator
        self.renamer = renamer
        self.platform = platform
        self._stop_requested = False

    def run(self):
        """Process all videos with enhanced analysis"""
        total = len(self.videos)

        for index, video_info in enumerate(self.videos):
            if self._stop_requested:
                break

            # Update progress
            filename = video_info['filename']
            self.progress_update.emit(index + 1, total, f"📹 Processing: {filename}")
            self.analysis_update.emit(f"\n{'='*60}")
            self.analysis_update.emit(f"VIDEO {index + 1}/{total}: {filename}")
            self.analysis_update.emit(f"{'='*60}")

            try:
                # Phase updates (only for enhanced mode)
                import inspect
                sig = inspect.signature(self.generator.generate_title)
                is_enhanced = 'platform' in sig.parameters

                if is_enhanced:
                    self.analysis_update.emit("🎙️  Phase 1: Audio analysis (language detection)...")
                    self.analysis_update.emit("👁️  Phase 2: Visual analysis (objects, scenes)...")
                    self.analysis_update.emit("📝 Phase 3: Text extraction (OCR)...")
                    self.analysis_update.emit("🔄 Phase 4: Content aggregation...")
                else:
                    self.analysis_update.emit("📝 Generating title from filename...")

                # Generate title
                if is_enhanced:
                    # Enhanced generator with platform optimization
                    new_title = self.generator.generate_title(
                        video_info,
                        platform=self.platform,
                        enable_ai=True
                    )
                else:
                    # Basic generator
                    new_title = self.generator.generate_title(video_info)

                self.analysis_update.emit(f"✨ Generated Title: {new_title}")

                # Rename file
                success, new_path, error = self.renamer.rename_video(
                    video_info['path'],
                    new_title
                )

                if success:
                    message = f"✅ {filename} → {Path(new_path).name}"
                    self.analysis_update.emit(f"✅ Successfully renamed!")
                else:
                    message = f"❌ {filename}: {error}"
                    self.analysis_update.emit(f"❌ Rename failed: {error}")

                self.progress_update.emit(index + 1, total, message)

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}", exc_info=True)
                error_msg = f"❌ {filename}: {str(e)}"
                self.progress_update.emit(index + 1, total, error_msg)
                self.analysis_update.emit(f"❌ Error: {str(e)}")

        # Send completion signal with statistics
        stats = self.renamer.get_statistics()
        self.processing_complete.emit(stats)

    def stop(self):
        """Request stop"""
        self._stop_requested = True


class TitleGeneratorDialog(QDialog):
    """Main dialog for enhanced multilingual title generation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_manager = APIKeyManager()
        self.scanner = VideoScanner()

        # Smart generator selection (auto-detects models)
        self.generator = get_generator(prefer_enhanced=True)
        self.renamer = VideoRenamer()

        self.videos = []
        self.processing_thread = None
        self.selected_platform = 'facebook'  # Default platform
        self.enhanced_mode = ENHANCED_MODE

        # LOG WHICH MODE IS ACTIVE
        logger.info("=" * 70)
        if self.enhanced_mode:
            logger.info("🚀 TITLE GENERATOR: ENHANCED MODE ACTIVE")
            logger.info(f"📂 AI Models location: {models_available.get('base_path')}")
            logger.info("✅ Content-aware, multilingual title generation enabled")
        else:
            logger.warning("⚠️  TITLE GENERATOR: BASIC MODE (Limited Features)")
            logger.warning("❌ AI models NOT found - using fallback title generation")
            logger.warning("📥 Download Whisper + CLIP to enable enhanced features")
        logger.info("=" * 70)

        self.setup_ui()

        # Show warning if basic mode
        if not self.enhanced_mode:
            dll_error = self._check_for_dll_error()
            if not dll_error:  # Only show basic warning if not DLL error
                self._show_basic_mode_warning()

    def setup_ui(self):
        """Setup UI components"""
        self.setWindowTitle("🪄 Title Generator")
        self.setMinimumSize(700, 600)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title = QLabel("AI-Powered Video Title Generator")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Mode indicator (PROMINENT)
        mode_group = QGroupBox("⚙️  Generator Mode")
        mode_layout = QVBoxLayout()

        if self.enhanced_mode:
            mode_label = QLabel("✅ ENHANCED MODE - FULL AI FEATURES")
            mode_label.setStyleSheet("""
                color: white;
                background-color: #28a745;
                font-weight: bold;
                font-size: 14pt;
                padding: 10px;
                border-radius: 5px;
            """)
            mode_label.setAlignment(Qt.AlignCenter)
            mode_layout.addWidget(mode_label)

            details_text = "🎙️  Audio Analysis + Language Detection\n"
            details_text += "👁️  Visual Content Analysis\n"
            details_text += "🌐 Multilingual Support (7+ languages)\n"
            details_text += "🎯 Content-Aware Title Generation"

            details = QLabel(details_text)
            details.setStyleSheet("padding: 10px; background-color: #e8f5e9; border-radius: 5px;")
            mode_layout.addWidget(details)
        else:
            mode_label = QLabel("🔴 BASIC MODE - LIMITED FEATURES")
            mode_label.setStyleSheet("""
                color: white;
                background-color: #dc3545;
                font-weight: bold;
                font-size: 14pt;
                padding: 10px;
                border-radius: 5px;
            """)
            mode_label.setAlignment(Qt.AlignCenter)
            mode_layout.addWidget(mode_label)

            warning_text = "⚠️  AI packages not installed\n"
            warning_text += "❌ No audio/visual analysis\n"
            warning_text += "❌ Generic titles only (OCR-based)"

            details = QLabel(warning_text)
            details.setStyleSheet("padding: 10px; background-color: #fff3cd; border-radius: 5px; color: #856404;")
            mode_layout.addWidget(details)

            # Auto-install button (primary action)
            auto_install_btn = QPushButton("🚀 AUTO-INSTALL AI Packages (One-Click Setup)")
            auto_install_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    font-weight: bold;
                    font-size: 12pt;
                    padding: 15px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """)
            auto_install_btn.clicked.connect(self.auto_install_packages)
            mode_layout.addWidget(auto_install_btn)

            # Alternative options layout
            alt_layout = QHBoxLayout()

            # Manual folder selection
            folder_btn = QPushButton("📂 Select Model Folder (Manual Install)")
            folder_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    font-weight: bold;
                    padding: 8px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
            """)
            folder_btn.clicked.connect(self.select_model_folder)
            alt_layout.addWidget(folder_btn)

            # Instructions button
            instructions_btn = QPushButton("📖 Manual Setup Guide")
            instructions_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    font-weight: bold;
                    padding: 8px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
            """)
            instructions_btn.clicked.connect(self.show_download_instructions)
            alt_layout.addWidget(instructions_btn)

            mode_layout.addLayout(alt_layout)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Folder selection group
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QVBoxLayout()

        folder_select_layout = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setWordWrap(True)
        folder_select_layout.addWidget(self.folder_label)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_folder)
        folder_select_layout.addWidget(browse_btn)

        folder_layout.addLayout(folder_select_layout)

        # Recursive option
        self.recursive_checkbox = QCheckBox("Scan nested folders (subfolders)")
        self.recursive_checkbox.setChecked(True)
        folder_layout.addWidget(self.recursive_checkbox)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Platform selection group (only in enhanced mode)
        if self.enhanced_mode:
            platform_group = QGroupBox("Platform Optimization")
            platform_layout = QHBoxLayout()

            platform_label = QLabel("Target Platform:")
            platform_layout.addWidget(platform_label)

            self.platform_combo = QComboBox()
            self.platform_combo.addItems([
                "📘 Facebook (255 chars)",
                "📱 TikTok (150 chars)",
                "📷 Instagram (125 chars)",
                "▶️ YouTube (100 chars)"
            ])
            self.platform_combo.currentIndexChanged.connect(self.on_platform_changed)
            platform_layout.addWidget(self.platform_combo)
            platform_layout.addStretch()

            platform_group.setLayout(platform_layout)
            layout.addWidget(platform_group)

        # Video count label
        self.video_count_label = QLabel("Videos found: 0")
        layout.addWidget(self.video_count_label)

        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Log text area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        self.start_btn = QPushButton("🚀 Start Processing")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def browse_folder(self):
        """Browse for folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing Videos",
            str(Path.home())
        )

        if folder:
            self.folder_label.setText(folder)
            self.scan_videos(folder)

    def scan_videos(self, folder_path: str):
        """Scan folder for videos"""
        self.log_text.append(f"📂 Scanning: {folder_path}")

        recursive = self.recursive_checkbox.isChecked()
        self.videos = self.scanner.scan_folder(folder_path, recursive=recursive)

        # Update UI
        count = len(self.videos)
        self.video_count_label.setText(f"Videos found: {count}")

        if count > 0:
            self.start_btn.setEnabled(True)
            self.log_text.append(f"✅ Found {count} videos")

            # Show statistics
            stats = self.scanner.get_statistics()
            self.log_text.append(
                f"   Total size: {stats['total_size_mb']} MB\n"
                f"   Folders: {stats['folders']}"
            )
        else:
            self.start_btn.setEnabled(False)
            self.log_text.append("❌ No videos found")

    def start_processing(self):
        """Start title generation process"""
        if not self.videos:
            QMessageBox.warning(self, "No Videos", "Please select a folder with videos")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Processing",
            f"Generate titles for {len(self.videos)} videos?\n\n"
            "This will rename the files in-place.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Disable buttons during processing
        self.start_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        # Clear log
        self.log_text.clear()
        self.log_text.append("🚀 Starting title generation...\n")

        # Start processing thread with selected platform
        self.processing_thread = ProcessingThread(
            self.videos,
            self.generator,
            self.renamer,
            platform=self.selected_platform
        )
        self.processing_thread.progress_update.connect(self.on_progress_update)
        self.processing_thread.analysis_update.connect(self.on_analysis_update)
        self.processing_thread.processing_complete.connect(self.on_processing_complete)
        self.processing_thread.start()

    def on_progress_update(self, current: int, total: int, message: str):
        """Handle progress update"""
        # Update progress bar
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)

        # Update status
        self.status_label.setText(f"Processing {current}/{total}")

        # Add to log
        self.log_text.append(message)

        # Scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def on_processing_complete(self, stats: dict):
        """Handle processing completion"""
        # Update UI
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Processing complete!")

        # Show summary
        self.log_text.append(f"\n{'='*50}")
        self.log_text.append("Summary:")
        self.log_text.append(f"  Total videos: {stats['total']}")
        self.log_text.append(f"  ✅ Successful: {stats['successful']}")
        self.log_text.append(f"  ❌ Failed: {stats['failed']}")
        self.log_text.append(f"  Success rate: {stats['success_rate']}%")
        self.log_text.append(f"{'='*50}")

        # Re-enable buttons
        self.close_btn.setEnabled(True)

        # Show completion message
        QMessageBox.information(
            self,
            "Processing Complete",
            f"✅ Title generation complete!\n\n"
            f"Successful: {stats['successful']}/{stats['total']}\n"
            f"Failed: {stats['failed']}/{stats['total']}\n\n"
            f"Videos renamed based on content analysis."
        )

    def on_platform_changed(self, index: int):
        """Handle platform selection change"""
        platforms = ['facebook', 'tiktok', 'instagram', 'youtube']
        self.selected_platform = platforms[index]
        logger.info(f"Platform selected: {self.selected_platform}")

    def on_analysis_update(self, message: str):
        """Handle analysis update messages"""
        self.log_text.append(message)

        # Scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _check_for_dll_error(self) -> bool:
        """Check if basic mode is due to DLL error and show specific fix"""
        # Try to detect DLL error by attempting torch import
        try:
            import torch
            return False  # No DLL error
        except OSError as e:
            if "DLL" in str(e) or "1114" in str(e):
                # DLL error detected - show specific fix
                msg = QMessageBox(self)
                msg.setWindowTitle("🔧 PyTorch DLL Error")
                msg.setIcon(QMessageBox.Critical)
                msg.setText("⚠️  AI Packages Installed But Cannot Load")

                fix_text = """
<b>Problem Detected:</b> PyTorch DLL initialization failed<br>
<font color="red">Error: Microsoft Visual C++ Redistributables missing or outdated</font>

<hr>

<b><font color="green">🔧 QUICK FIX (Choose One):</font></b>

<b>Option 1: Install Visual C++ Redistributables (Recommended)</b><br>
1. Download from: <a href="https://aka.ms/vs/17/release/vc_redist.x64.exe">https://aka.ms/vs/17/release/vc_redist.x64.exe</a><br>
2. Run the installer<br>
3. Restart this application<br>
<br>

<b>Option 2: Use CPU-Only PyTorch (Smaller, No Dependencies)</b><br>
1. Open Command Prompt / Terminal<br>
2. Run: <code>pip uninstall torch</code><br>
3. Run: <code>pip install torch --index-url https://download.pytorch.org/whl/cpu</code><br>
4. Restart this application<br>

<hr>

<b>After fixing, Enhanced Mode will activate automatically!</b>
                """

                msg.setInformativeText(fix_text)
                msg.setTextFormat(Qt.RichText)
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                return True  # DLL error detected
            return False
        except ImportError:
            return False  # Not installed
        except Exception:
            return False  # Other error

    def _show_basic_mode_warning(self):
        """Show warning that basic mode is active (one-time popup)"""
        msg = QMessageBox(self)
        msg.setWindowTitle("⚠️  Basic Mode Active")
        msg.setIcon(QMessageBox.Warning)
        msg.setText("🔴 LIMITED FEATURES - AI Models Not Found")

        warning_text = """
<b>Currently running in BASIC MODE with limited features:</b>

<font color="red">❌ NO audio analysis (language detection)</font><br>
<font color="red">❌ NO visual content analysis</font><br>
<font color="red">❌ NO multilingual support</font><br>
<font color="red">❌ Generic titles only (OCR-based)</font>

<hr>

<b><font color="green">To enable ENHANCED AI-POWERED features:</font></b>

<b>1. Install Required Python Packages:</b><br>
&nbsp;&nbsp;&nbsp;<code>pip install openai-whisper transformers torch</code>

<b>2. Download AI Models:</b><br>
&nbsp;&nbsp;&nbsp;• Whisper: Auto-downloads on first use<br>
&nbsp;&nbsp;&nbsp;• CLIP: Auto-downloads on first use

<b>3. Restart Application</b>

<hr>

<b><font color="blue">Enhanced features you'll unlock:</font></b>
✅ Audio transcription + language detection (20+ languages)<br>
✅ Visual object and scene detection<br>
✅ Content-aware title generation<br>
✅ Multilingual support (7+ languages)<br>
✅ Platform optimization (Facebook/TikTok/etc.)

<b>Click "Download Instructions" for detailed setup guide.</b>
        """

        msg.setInformativeText(warning_text)
        msg.setTextFormat(Qt.RichText)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Help)
        msg.button(QMessageBox.Help).setText("Download Instructions")

        result = msg.exec_()
        if result == QMessageBox.Help:
            self.show_download_instructions()

    def show_download_instructions(self):
        """Show model download instructions"""
        instructions = """
🚀 ENABLE ENHANCED AI-POWERED FEATURES

To unlock multilingual content analysis and AI-powered titles:

📥 STEP 1: Install Python Packages
   Open terminal/command prompt and run:
   pip install openai-whisper transformers torch

   This will download ~2-4GB of AI models automatically.

📂 STEP 2: Model Auto-Download
   • Whisper (Audio Analysis): Downloads on first use
   • CLIP (Visual Analysis): Downloads on first use

   Models will be saved in your user cache directory.

🔄 STEP 3: Restart Application
   The app will auto-detect models and enable Enhanced Mode

✨ ENHANCED FEATURES YOU'LL GET:
   ✅ Audio transcription + language detection (20+ languages)
   ✅ Visual object and scene detection
   ✅ Content-aware title generation
   ✅ Multilingual support (English, Portuguese, French, Spanish, Urdu, Hindi, Arabic)
   ✅ Platform optimization (Facebook/TikTok/Instagram/YouTube)
   ✅ Niche-specific templates (Cooking, Gaming, Reviews, etc.)

📝 For detailed setup instructions, see:
   modules/title_generator/README.md
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("Download AI Models")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Enable Enhanced AI Features")
        msg.setInformativeText(instructions)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def auto_install_packages(self):
        """Auto-install AI packages with progress tracking"""
        from .model_finder import get_model_finder
        from PyQt5.QtCore import QThread

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Auto-Install AI Packages",
            "This will automatically install:\n\n"
            "• openai-whisper (~500MB)\n"
            "• transformers (~500MB)\n"
            "• torch (~2GB)\n\n"
            "Total download: ~2-4GB\n"
            "Time: 10-15 minutes\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create progress dialog
        progress_dialog = QMessageBox(self)
        progress_dialog.setWindowTitle("Installing AI Packages")
        progress_dialog.setIcon(QMessageBox.Information)
        progress_dialog.setText("Installing AI packages...")
        progress_dialog.setInformativeText("Please wait, this may take 10-15 minutes...")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        progress_dialog.show()

        # Install in background thread
        class InstallThread(QThread):
            def __init__(self, parent_dialog):
                super().__init__()
                self.parent_dialog = parent_dialog
                self.result = None

            def run(self):
                def progress_callback(msg):
                    self.parent_dialog.setInformativeText(msg)

                model_finder = get_model_finder()
                self.result = model_finder.auto_install_packages(progress_callback)

        install_thread = InstallThread(progress_dialog)
        install_thread.finished.connect(lambda: self._on_install_complete(install_thread.result, progress_dialog))
        install_thread.start()

    def _on_install_complete(self, result, progress_dialog):
        """Handle installation completion"""
        progress_dialog.close()

        if result['success']:
            QMessageBox.information(
                self,
                "Success!",
                "🎉 All packages installed successfully!\n\n"
                "🔄 Please RESTART the application to enable Enhanced Mode.\n\n"
                f"✅ Installed: {', '.join(result['installed'])}"
            )
        elif result['installed']:
            QMessageBox.warning(
                self,
                "Partial Success",
                f"⚠️  Some packages installed:\n\n"
                f"✅ Installed: {', '.join(result['installed'])}\n"
                f"❌ Failed: {', '.join(result['failed'])}\n\n"
                f"Errors:\n{chr(10).join(result['errors'][:3])}"
            )
        else:
            QMessageBox.critical(
                self,
                "Installation Failed",
                "❌ No packages installed.\n\n"
                "Please check:\n"
                "• Internet connection\n"
                "• Disk space (need 5GB+)\n"
                "• Python/pip is working\n\n"
                "Try manual installation:\n"
                "pip install openai-whisper transformers torch"
            )

    def select_model_folder(self):
        """Let user select folder where they manually installed models"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select AI Models Folder",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )

        if not folder:
            return

        folder_path = Path(folder)

        # Check if folder contains models
        has_whisper = (folder_path / "whisper").exists()
        has_clip = (folder_path / "clip").exists()

        if not has_whisper and not has_clip:
            QMessageBox.warning(
                self,
                "No Models Found",
                f"No AI models found in:\n{folder}\n\n"
                "Expected structure:\n"
                f"{folder}/\n"
                "  ├── whisper/\n"
                "  │   └── base.pt\n"
                "  └── clip/\n"
                "      └── vit-base-patch32/\n\n"
                "Please select the correct folder or use Auto-Install."
            )
            return

        # Save custom path
        from .model_finder import get_model_finder
        model_finder = get_model_finder()
        model_finder.save_custom_path('custom', str(folder_path))

        # Show success message
        models_found = []
        if has_whisper:
            models_found.append("Whisper")
        if has_clip:
            models_found.append("CLIP")

        QMessageBox.information(
            self,
            "Models Found!",
            f"✅ Found models in:\n{folder}\n\n"
            f"Models detected: {', '.join(models_found)}\n\n"
            "🔄 Please RESTART the application to enable Enhanced Mode."
        )

    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop processing thread if running
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Processing is still running. Stop and close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.processing_thread.stop()
                self.processing_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
