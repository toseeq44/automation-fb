"""
Logging System for OneSoul
Provides comprehensive logging for debugging and monitoring
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class ContentFlowLogger:
    """
    Centralized logging system for the application
    """

    def __init__(self, name: str = "OneSoul", log_dir: Path = None):
        """
        Initialize logger

        Args:
            name: Logger name
            log_dir: Directory to store log files (default: ~/.onesoul/logs/)
        """
        self.name = name
        self.log_dir = log_dir or (Path.home() / ".onesoul" / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        simple_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )

        # File Handler - Daily rotating logs
        log_file = self.log_dir / f"onesoul_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)

        # Console Handler (guard against missing/ASCII-only stdout)
        if sys.stdout:
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(simple_formatter)
            self.logger.addHandler(console_handler)

        # Error File Handler - Separate file for errors only
        error_file = self.log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(error_handler)

    def debug(self, message: str, module: str = None):
        """Log debug message"""
        if module:
            self.logger.debug(f"[{module}] {message}")
        else:
            self.logger.debug(message)

    def info(self, message: str, module: str = None):
        """Log info message"""
        if module:
            self.logger.info(f"[{module}] {message}")
        else:
            self.logger.info(message)

    def warning(self, message: str, module: str = None):
        """Log warning message"""
        if module:
            self.logger.warning(f"[{module}] {message}")
        else:
            self.logger.warning(message)

    def error(self, message: str, module: str = None, exc_info: bool = False):
        """Log error message"""
        if module:
            self.logger.error(f"[{module}] {message}", exc_info=exc_info)
        else:
            self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str, module: str = None, exc_info: bool = False):
        """Log critical message"""
        if module:
            self.logger.critical(f"[{module}] {message}", exc_info=exc_info)
        else:
            self.logger.critical(message, exc_info=exc_info)

    def exception(self, message: str, module: str = None):
        """Log exception with traceback"""
        if module:
            self.logger.exception(f"[{module}] {message}")
        else:
            self.logger.exception(message)

    def cleanup_old_logs(self, days: int = 30):
        """
        Clean up log files older than specified days

        Args:
            days: Number of days to keep logs
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            for log_file in self.log_dir.glob("*.log"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    self.info(f"Deleted old log file: {log_file.name}", "Logger")

        except Exception as e:
            self.error(f"Failed to cleanup old logs: {e}", "Logger")

    def export_logs(self, output_path: Path = None) -> Path:
        """
        Export all logs to a single file

        Args:
            output_path: Where to save the exported logs

        Returns:
            Path to exported log file
        """
        try:
            if not output_path:
                output_path = Path.home() / "Desktop" / f"contentflow_logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            with open(output_path, 'w', encoding='utf-8') as outfile:
                outfile.write(f"OneSoul - Log Export\n")
                outfile.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                outfile.write("=" * 80 + "\n\n")

                # Combine all log files
                for log_file in sorted(self.log_dir.glob("*.log")):
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f"File: {log_file.name}\n")
                    outfile.write(f"{'='*80}\n\n")

                    with open(log_file, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                        outfile.write("\n\n")

            self.info(f"Logs exported to: {output_path}", "Logger")
            return output_path

        except Exception as e:
            self.error(f"Failed to export logs: {e}", "Logger")
            raise


# Global logger instance
_global_logger = None


def get_logger(name: str = "ContentFlowPro") -> ContentFlowLogger:
    """
    Get or create global logger instance

    Args:
        name: Logger name

    Returns:
        ContentFlowLogger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ContentFlowLogger(name)
        _global_logger.info("OneSoul application started", "App")
        _global_logger.cleanup_old_logs(days=30)
    return _global_logger


# Convenience functions
def log_info(message: str, module: str = None):
    """Convenience function for info logging"""
    get_logger().info(message, module)


def log_error(message: str, module: str = None, exc_info: bool = False):
    """Convenience function for error logging"""
    get_logger().error(message, module, exc_info)


def log_warning(message: str, module: str = None):
    """Convenience function for warning logging"""
    get_logger().warning(message, module)


def log_debug(message: str, module: str = None):
    """Convenience function for debug logging"""
    get_logger().debug(message, module)


# Test function
if __name__ == '__main__':
    logger = get_logger("TestLogger")

    logger.info("Application started")
    logger.debug("Debug message", "TestModule")
    logger.warning("Warning message", "TestModule")
    logger.error("Error message", "TestModule")

    try:
        raise ValueError("Test exception")
    except Exception:
        logger.exception("Exception occurred", "TestModule")

    print(f"\nLog files location: {logger.log_dir}")
    print("Check log files for detailed output")
